"""Blender-side native SKEL A/B/C/D/R geometry regression.

The input Blend is never saved.  Only vertex coordinates on the in-memory
SKEL skin are replaced, matching the current SKEL controls' update contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--scenario-meshes", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(args)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def topology_signature(obj) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(obj.data.vertices)};p={len(obj.data.polygons)};".encode("ascii"))
    for polygon in obj.data.polygons:
        digest.update(",".join(str(int(index)) for index in polygon.vertices).encode("ascii"))
        digest.update(b";")
    return digest.hexdigest()


def read_obj_vertices(path: Path):
    vertices = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("v "):
                values = line.split()
                vertices.append(Vector((float(values[1]), float(values[2]), float(values[3]))))
    return vertices


def replace_vertices(target, obj_path: Path) -> None:
    vertices = read_obj_vertices(obj_path)
    if len(vertices) != len(target.data.vertices):
        raise RuntimeError(f"vertex mismatch: {len(vertices)} != {len(target.data.vertices)}")
    for vertex, coordinate in zip(target.data.vertices, vertices):
        vertex.co = coordinate
    target.data.update()
    bpy.context.view_layer.update()


def base_vertices(target):
    return [vertex.co.copy() for vertex in target.data.vertices]


def vertex_delta_metrics(left, right):
    if len(left) != len(right):
        raise RuntimeError("vertex metric inputs differ in length")
    distances = [(a - b).length for a, b in zip(left, right)]
    return {
        "max_m": float(max(distances, default=0.0)),
        "rms_m": float(math.sqrt(sum(value * value for value in distances) / max(1, len(distances)))),
        "finite": bool(all(math.isfinite(component) for vertex in right for component in vertex)),
    }


def make_camera(scene, target):
    corners = [target.matrix_world @ Vector(corner) for corner in target.bound_box]
    minimum = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    maximum = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    center = (minimum + maximum) * 0.5
    extent = maximum - minimum
    distance = max(extent.x, extent.z) * 1.8 + 1.0
    data = bpy.data.cameras.new("__SKEL_REGRESSION_CAMERA_DATA__")
    camera = bpy.data.objects.new("__SKEL_REGRESSION_CAMERA__", data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((0.0, -distance, 0.0))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 55.0
    camera.data.sensor_width = 36.0
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.clip_start = 0.01
    camera.data.clip_end = 100.0
    scene.camera = camera
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    bpy.context.view_layer.update()
    return camera, center


def evaluated_points(target, fixture_points):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        output = []
        for fixture in fixture_points:
            face_index = int(fixture["face_index"])
            polygon = evaluated_mesh.polygons[face_index]
            vertex_ids = [int(value) for value in polygon.vertices]
            weights = [float(value) for value in fixture["barycentric"]]
            local_vertices = [evaluated_mesh.vertices[index].co.copy() for index in vertex_ids]
            world_vertices = [evaluated.matrix_world @ value for value in local_vertices]
            point = sum((value * weight for value, weight in zip(world_vertices, weights)), Vector())
            cross = (world_vertices[1] - world_vertices[0]).cross(world_vertices[2] - world_vertices[0])
            normal = cross.normalized() if cross.length > 1e-12 else Vector((0.0, 0.0, 0.0))
            output.append(
                {
                    "point_id": fixture["point_id"],
                    "face_index": face_index,
                    "vertex_indices": vertex_ids,
                    "fixture_vertex_indices": [int(value) for value in fixture["vertex_indices"]],
                    "barycentric": weights,
                    "barycentric_sum": sum(weights),
                    "xyz_world_m": [float(value) for value in point],
                    "world_normal": [float(value) for value in normal],
                    "_point": point,
                    "_normal": normal,
                }
            )
        return output, len(evaluated_mesh.vertices), len(evaluated_mesh.polygons)
    finally:
        evaluated.to_mesh_clear()


def project(scene, camera, point):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    width = scene.render.resolution_x
    height = scene.render.resolution_y
    projection = camera.calc_matrix_camera(
        depsgraph,
        x=width,
        y=height,
        scale_x=scene.render.pixel_aspect_x,
        scale_y=scene.render.pixel_aspect_y,
    )
    camera_point = camera.matrix_world.inverted() @ point
    clip = projection @ camera_point.to_4d()
    if abs(clip.w) < 1e-12:
        return {"uv_px": None, "camera_depth_m": -float(camera_point.z), "in_front": False, "in_frame": False}
    ndc_x = clip.x / clip.w
    ndc_y = clip.y / clip.w
    u = (ndc_x + 1.0) * 0.5 * width
    v = (1.0 - ndc_y) * 0.5 * height
    depth = -float(camera_point.z)
    return {
        "uv_px": [float(u), float(v)],
        "camera_depth_m": depth,
        "in_front": depth > 0.0,
        "in_frame": depth > 0.0 and 0.0 <= u < width and 0.0 <= v < height,
    }


def ray_result(scene, camera, target, point, normal):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    origin = camera.matrix_world.translation.copy()
    vector = point - origin
    distance = vector.length
    direction = vector.normalized()
    tolerance = max(1e-5, distance * 1e-6)
    hit, location, hit_normal, face_index, hit_object, _matrix = scene.ray_cast(
        depsgraph, origin, direction, distance=distance + tolerance
    )
    hit_name = hit_object.name if hit and hit_object else None
    original = hit_object.original if hit and hit_object and hasattr(hit_object, "original") else hit_object
    same_target = bool(hit and original == target)
    point_error = float((location - point).length) if hit else None
    front_facing = float(normal.dot((origin - point).normalized())) > 0.0
    return {
        "hit": bool(hit),
        "hit_object": hit_name,
        "hit_face_index": int(face_index) if hit else None,
        "point_error_m": point_error,
        "visible_on_target": bool(same_target and point_error is not None and point_error <= 1e-4),
        "front_facing": front_facing,
        "hit_location_world_m": [float(value) for value in location] if hit else None,
        "hit_normal_world": [float(value) for value in hit_normal] if hit else None,
    }


def add_occluder(scene, camera, point):
    origin = camera.matrix_world.translation.copy()
    center = origin.lerp(point, 0.82)
    bpy.ops.mesh.primitive_cube_add(size=0.04, location=center)
    occluder = bpy.context.object
    occluder.name = "__SKEL_REGRESSION_EXTERNAL_OCCLUDER__"
    occluder["regression_external_occluder"] = True
    bpy.context.view_layer.update()
    return occluder


def make_material(name, rgba, emission=False):
    material = bpy.data.materials.new(name)
    material.diffuse_color = rgba
    material.use_nodes = True
    node = material.node_tree.nodes.get("Principled BSDF")
    if node:
        node.inputs["Base Color"].default_value = rgba
        node.inputs["Roughness"].default_value = 0.55
        if emission:
            node.inputs["Emission Color"].default_value = rgba
            node.inputs["Emission Strength"].default_value = 2.5
    return material


def render_overlay(scene, camera, target, points, output_path: Path, occluder=None):
    previous_resolution = (
        scene.render.resolution_x,
        scene.render.resolution_y,
        scene.render.resolution_percentage,
    )
    previous_filepath = scene.render.filepath
    marker_material = make_material("__SKEL_REGRESSION_MARKER_MAT__", (1.0, 0.02, 0.02, 1.0), emission=True)
    occluder_material = make_material("__SKEL_REGRESSION_OCCLUDER_MAT__", (0.03, 0.25, 1.0, 1.0))
    markers = []
    for index, point in enumerate(points):
        world = Vector(point["xyz_world_m"])
        normal = Vector(point["world_normal"])
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.012, location=world + normal * 0.006)
        marker = bpy.context.object
        marker.name = f"__SKEL_REGRESSION_MARKER_{index:02d}__"
        marker.data.materials.append(marker_material)
        markers.append(marker)
    if occluder is not None:
        occluder.data.materials.clear()
        occluder.data.materials.append(occluder_material)

    lights = []
    for index, (location, energy) in enumerate(
        [((-2.5, -3.0, 3.0), 900.0), ((2.5, -2.0, 1.0), 650.0), ((0.0, 1.5, 2.0), 500.0)]
    ):
        data = bpy.data.lights.new(f"__SKEL_REGRESSION_LIGHT_DATA_{index}__", type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = 4.0
        light = bpy.data.objects.new(f"__SKEL_REGRESSION_LIGHT_{index}__", data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (Vector((0.0, 0.0, 0.0)) - light.location).to_track_quat("-Z", "Y").to_euler()
        lights.append(light)
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output_path)
    scene.render.film_transparent = False
    scene.world.color = (0.04, 0.04, 0.04)
    scene.camera = camera
    bpy.ops.render.render(write_still=True)
    for obj in markers + lights:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.materials.remove(marker_material)
    bpy.data.materials.remove(occluder_material)
    scene.render.resolution_x = previous_resolution[0]
    scene.render.resolution_y = previous_resolution[1]
    scene.render.resolution_percentage = previous_resolution[2]
    scene.render.filepath = previous_filepath
    bpy.context.view_layer.update()


def scenario_record(label, target, fixture_points, scene, camera):
    points, evaluated_vertices, evaluated_polygons = evaluated_points(target, fixture_points)
    clean_points = []
    for point in points:
        world = point.pop("_point")
        normal = point.pop("_normal")
        point["projection"] = project(scene, camera, world)
        point["ray"] = ray_result(scene, camera, target, world, normal)
        clean_points.append(point)
    return {
        "label": label,
        "base_vertex_count": len(target.data.vertices),
        "base_polygon_count": len(target.data.polygons),
        "evaluated_vertex_count": evaluated_vertices,
        "evaluated_polygon_count": evaluated_polygons,
        "topology_signature_sha256": topology_signature(target),
        "object_matrix_world": [[float(value) for value in row] for row in target.matrix_world],
        "points": clean_points,
    }


def main():
    args = parse_args()
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    meshes = json.loads(Path(args.scenario_meshes).read_text(encoding="utf-8"))
    output = Path(args.output)
    scene = bpy.context.scene
    target = bpy.data.objects.get(fixture["target"]["object_name"])
    if target is None or target.type != "MESH":
        raise RuntimeError("canonical SKEL target mesh missing")
    camera, look_at = make_camera(scene, target)

    initial_topology = topology_signature(target)
    canonical_vertices = base_vertices(target)
    canonical_modifiers = [modifier.type for modifier in target.modifiers]
    canonical_shape_keys = (
        [block.name for block in target.data.shape_keys.key_blocks]
        if target.data.shape_keys is not None
        else []
    )
    canonical_scale = [float(value) for value in target.matrix_world.to_scale()]
    base_polygon_vertices = [[int(value) for value in polygon.vertices] for polygon in target.data.polygons]
    scenarios = {}
    scenario_vertices = {}
    for label in ("A", "B", "C"):
        replace_vertices(target, Path(meshes[label]))
        scenario_vertices[label] = base_vertices(target)
        scenarios[label] = scenario_record(label, target, fixture["points"], scene, camera)

    replace_vertices(target, Path(meshes["A"]))
    render_overlay(scene, camera, target, scenarios["A"]["points"], output / "A_overlay.png")

    replace_vertices(target, Path(meshes["A"]))
    base_d_points, _, _ = evaluated_points(target, fixture["points"])
    occluder = add_occluder(scene, camera, base_d_points[0]["_point"])
    scenarios["D"] = scenario_record("D", target, fixture["points"], scene, camera)
    render_overlay(
        scene,
        camera,
        target,
        scenarios["D"]["points"],
        output / "D_external_occlusion_overlay.png",
        occluder=occluder,
    )
    bpy.data.objects.remove(occluder, do_unlink=True)
    bpy.context.view_layer.update()

    replace_vertices(target, Path(meshes["R"]))
    scenario_vertices["R"] = base_vertices(target)
    scenarios["R"] = scenario_record("R", target, fixture["points"], scene, camera)

    for label, scenario in scenarios.items():
        for point in scenario["points"]:
            a_point = next(item for item in scenarios["A"]["points"] if item["point_id"] == point["point_id"])
            point["delta_from_A_m"] = math.dist(point["xyz_world_m"], a_point["xyz_world_m"])

    expected_topology = fixture["target"]["topology_signature_sha256"]
    all_topology = all(value["topology_signature_sha256"] == expected_topology for value in scenarios.values())
    all_counts = all(
        value["base_vertex_count"] == 6890
        and value["base_polygon_count"] == 13776
        and value["evaluated_vertex_count"] == 6890
        and value["evaluated_polygon_count"] == 13776
        for value in scenarios.values()
    )
    all_fixture_faces = all(
        point["vertex_indices"] == point["fixture_vertex_indices"]
        and abs(point["barycentric_sum"] - 1.0) <= 1e-6
        for value in scenarios.values()
        for point in value["points"]
    )
    a_visible = all(point["ray"]["visible_on_target"] for point in scenarios["A"]["points"])
    b_visible = all(point["ray"]["visible_on_target"] for point in scenarios["B"]["points"])
    c_visible = all(point["ray"]["visible_on_target"] for point in scenarios["C"]["points"])
    r_visible = all(point["ray"]["visible_on_target"] for point in scenarios["R"]["points"])
    d_first = scenarios["D"]["points"][0]["ray"]
    d_external = d_first["hit"] and d_first["hit_object"] == "__SKEL_REGRESSION_EXTERNAL_OCCLUDER__" and not d_first["visible_on_target"]
    d_others_visible = all(point["ray"]["visible_on_target"] for point in scenarios["D"]["points"][1:])
    max_b_change = max(point["delta_from_A_m"] for point in scenarios["B"]["points"])
    max_c_change = max(point["delta_from_A_m"] for point in scenarios["C"]["points"])
    max_r_error = max(point["delta_from_A_m"] for point in scenarios["R"]["points"])
    a_canonical_vertex_metrics = vertex_delta_metrics(canonical_vertices, scenario_vertices["A"])
    b_vertex_metrics = vertex_delta_metrics(scenario_vertices["A"], scenario_vertices["B"])
    c_vertex_metrics = vertex_delta_metrics(scenario_vertices["A"], scenario_vertices["C"])
    r_vertex_metrics = vertex_delta_metrics(scenario_vertices["A"], scenario_vertices["R"])
    polygon_order_unchanged_in_memory = base_polygon_vertices == [
        [int(value) for value in polygon.vertices] for polygon in target.data.polygons
    ]

    checks = {
        "canonical_topology_matches_fixture": initial_topology == expected_topology,
        "all_scenarios_topology_stable": all_topology,
        "base_and_evaluated_counts_stable": all_counts,
        "fixture_face_vertices_and_barycentric_valid": all_fixture_faces,
        "A_points_visible_on_target": a_visible,
        "B_points_visible_on_target": b_visible,
        "C_points_visible_on_target": c_visible,
        "D_first_point_externally_occluded": d_external,
        "D_other_points_remain_visible": d_others_visible,
        "R_points_visible_on_target": r_visible,
        "B_native_shape_changes_frozen_points": max_b_change >= 1e-3,
        "C_native_pose_changes_frozen_points": max_c_change >= 1e-3,
        "R_restores_A_within_1e-7_m": max_r_error <= 1e-7,
        "canonical_A_full_mesh_match_within_1e-7_m": a_canonical_vertex_metrics["max_m"] <= 1e-7,
        "B_full_mesh_finite_and_changed": b_vertex_metrics["finite"] and b_vertex_metrics["max_m"] >= 1e-3,
        "C_full_mesh_finite_and_changed": c_vertex_metrics["finite"] and c_vertex_metrics["max_m"] >= 1e-3,
        "R_full_mesh_restores_A_within_1e-7_m": r_vertex_metrics["finite"] and r_vertex_metrics["max_m"] <= 1e-7,
        "polygon_order_unchanged_in_memory": polygon_order_unchanged_in_memory,
        "blend_not_saved_by_script": True,
    }
    passed = all(checks.values())
    report = {
        "schema": "skel-native-abcd-regression-report-v1",
        "status_without_post_hash_check": "PASS" if passed else "FAIL",
        "passed_without_post_hash_check": passed,
        "medical_status": fixture["medical_status"],
        "scope": "Native SKEL surface binding, evaluated mesh, camera ray visibility, external occlusion, restoration",
        "limitations": [
            "Three frozen engineering points all lie on the front torso; this run does not exercise a frozen self-occluded back point.",
            "B is one small combined beta probe, not a validated population sampling distribution.",
            "C is one moderate pose probe, not a medical propagation validation or a prone-treatment pose.",
            "Topology preservation is partly guaranteed by the tested update method replacing coordinates only; it does not prove arbitrary future modifiers preserve face indices.",
            "The canonical object has its recorded transform/modifier/shape-key state only; arbitrary non-uniform object scaling or topology-changing modifiers are not covered.",
            "SKEL is a structural prior, not patient CT ground truth.",
        ],
        "blend_runtime": bpy.app.version_string,
        "blend_filepath_opened_read_only_by_convention": bpy.data.filepath,
        "blend_is_dirty_at_end": bool(bpy.data.is_dirty),
        "camera": {
            "name": camera.name,
            "location_world_m": [float(value) for value in camera.location],
            "look_at_world_m": [float(value) for value in look_at],
            "lens_mm": float(camera.data.lens),
            "sensor_width_mm": float(camera.data.sensor_width),
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        },
        "canonical_object_state": {
            "modifiers": canonical_modifiers,
            "shape_keys": canonical_shape_keys,
            "matrix_world_scale": canonical_scale,
        },
        "metrics": {
            "max_B_point_change_from_A_m": max_b_change,
            "max_C_point_change_from_A_m": max_c_change,
            "max_R_point_error_from_A_m": max_r_error,
            "max_A_vertex_error_from_canonical_m": a_canonical_vertex_metrics["max_m"],
            "rms_A_vertex_error_from_canonical_m": a_canonical_vertex_metrics["rms_m"],
            "max_B_vertex_change_from_A_m": b_vertex_metrics["max_m"],
            "rms_B_vertex_change_from_A_m": b_vertex_metrics["rms_m"],
            "max_C_vertex_change_from_A_m": c_vertex_metrics["max_m"],
            "rms_C_vertex_change_from_A_m": c_vertex_metrics["rms_m"],
            "max_R_vertex_error_from_A_m": r_vertex_metrics["max_m"],
            "rms_R_vertex_error_from_A_m": r_vertex_metrics["rms_m"],
        },
        "checks": checks,
        "scenarios": scenarios,
    }
    write_json(output / "skel_native_regression_report.json", report)
    print(f"BLENDER_SKEL_NATIVE_REGRESSION={'PASS' if passed else 'FAIL'}")
    # Deliberately no bpy.ops.wm.save_* call.


if __name__ == "__main__":
    main()
