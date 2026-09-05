"""Probe one multi-beta SKEL case using measurement-contract V2."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector


TARGET = "SKEL-skin-female"
CAMERA = "ACU_PRONE_BACK_CAMERA"
BED = "ACU_PRONE_BED"
EXPECTED_TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"


def arguments():
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--native-parameters", required=True, type=Path)
    parser.add_argument("--core-parent", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=1024)
    return parser.parse_args(values)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def topology_signature(mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update((",".join(str(int(v)) for v in polygon.vertices) + ";").encode("ascii"))
    return digest.hexdigest()


def rows(matrix):
    return [[float(value) for value in row] for row in matrix]


def main() -> None:
    args = arguments()
    sys.path.insert(0, str(args.core_parent.resolve()))
    from training_export_core.camera_geometry import project_world_point, world_to_opencv_camera
    from training_export_core.surface_binding import sample_surface_binding
    from training_export_core.visibility import evaluate_visibility

    atlas, contract = read_json(args.atlas), read_json(args.contract)
    profile, native = read_json(args.profile), read_json(args.native_parameters)
    requested = [float(value) for value in profile["betas"]]
    effective = [float(value) for value in native["betas"]]
    recorded = [float(value) for value in bpy.context.scene.get("skel_betas", [])]
    if not (len(requested) == len(effective) == len(recorded) == 10):
        raise ValueError("all beta vectors must contain 10 values")
    if requested != effective or effective != recorded:
        raise ValueError(f"beta control mismatch: {requested} / {effective} / {recorded}")

    scene = bpy.context.scene
    target, camera, bed = (bpy.data.objects.get(name) for name in (TARGET, CAMERA, BED))
    if target is None or target.type != "MESH" or camera is None or camera.type != "CAMERA" or bed is None:
        raise RuntimeError("frozen SKEL/camera/bed scene is incomplete")
    scene.camera = camera
    scene.frame_set(1)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        signature = topology_signature(mesh)
        if signature != EXPECTED_TOPOLOGY or contract["topology_signature_sha256"] != signature:
            raise RuntimeError(f"topology mismatch: {signature}")
        local_vertices = [vertex.co.copy() for vertex in mesh.vertices]
        polygons = [[int(value) for value in polygon.vertices] for polygon in mesh.polygons]
        world_vertices = [evaluated.matrix_world @ coordinate for coordinate in local_vertices]
        vertex_digest = hashlib.sha256()
        for coordinate in local_vertices:
            vertex_digest.update(struct.pack("<fff", float(coordinate.x), float(coordinate.y), float(coordinate.z)))

        def extent(indices, axis):
            values = [float(local_vertices[int(index)][axis]) for index in indices]
            return max(values) - min(values)

        measurements = {}
        for name, definition in contract["measurements"].items():
            if "reference_vertex_sets" in definition:
                sets = list(definition["reference_vertex_sets"].values())
                if len(sets) != 2:
                    raise ValueError(f"{name} requires exactly two frozen vertex sets")
                means = [sum(float(local_vertices[int(index)].y) for index in indices) / len(indices) for indices in sets]
                measurements[name] = abs(means[0] - means[1])
            else:
                axis = 1 if definition["axis"] in {"body_longitudinal_y", "body_longitudinal_axis"} else (2 if definition["axis"] == "body_ventral_dorsal_z" else 0)
                measurements[name] = extent(definition["frozen_vertex_indices"], axis)

        evaluated.to_mesh_clear()
        mesh = None
        rotation_cv = world_to_opencv_camera(camera).to_3x3()
        point_records = []
        for annotation in atlas["annotations"]:
            face_index = int(annotation["face_index"])
            expected_vertices = [int(value) for value in annotation["vertex_indices"]]
            if polygons[face_index] != expected_vertices:
                raise ValueError(f"face order mismatch for {annotation['point_id']}")
            weights = [float(value) for value in annotation["barycentric"]]
            if abs(sum(weights) - 1.0) > 1e-6:
                raise ValueError(f"invalid barycentric sum for {annotation['point_id']}")
            local = sum((local_vertices[index] * weight for index, weight in zip(expected_vertices, weights)), Vector())
            surface = sample_surface_binding(target, face_index, weights, depsgraph=depsgraph, expected_vertex_indices=expected_vertices)
            world = Vector(surface.xyz_world_m)
            normal_world = Vector(surface.world_normal).normalized()
            projection = project_world_point(scene, camera, world, width=args.width, height=args.height)
            visibility = evaluate_visibility(
                scene=scene, depsgraph=depsgraph, camera=camera, target_object=target,
                point_world=world, world_normal=normal_world, width=args.width,
                height=args.height, ray_tolerance_m=1e-4,
            )
            tri = [local_vertices[index] for index in expected_vertices]
            point_records.append({
                "point_id": annotation["point_id"], "code": annotation.get("code"),
                "side": annotation.get("side"), "body_region": annotation.get("body_region"),
                "face_index": face_index, "vertex_indices": expected_vertices, "barycentric": weights,
                "xyz_body_local_m": list(local), "xyz_world_m": list(surface.xyz_world_m),
                "xyz_camera_opencv_m": projection["xyz_camera_opencv_m"],
                "uv_pixel_opencv": projection["uv_pixel_opencv"],
                "camera_depth_z_m": projection["camera_depth_z_m"],
                "normal_world": list(normal_world),
                "normal_camera_opencv": list((rotation_cv @ normal_world).normalized()),
                "triangle_area_m2": float((tri[1] - tri[0]).cross(tri[2] - tri[0]).length * 0.5),
                "triangle_edge_lengths_m": [float((tri[1] - tri[0]).length), float((tri[2] - tri[1]).length), float((tri[0] - tri[2]).length)],
                **visibility.to_dict(),
            })

        local_min = [min(float(v[i]) for v in local_vertices) for i in range(3)]
        local_max = [max(float(v[i]) for v in local_vertices) for i in range(3)]
        world_min = [min(float(v[i]) for v in world_vertices) for i in range(3)]
        world_max = [max(float(v[i]) for v in world_vertices) for i in range(3)]
        bed_top = max(float((bed.matrix_world @ Vector(corner)).z) for corner in bed.bound_box)
        clearance = world_min[2] - bed_top
        lights = [{
            "name": item.name, "type": item.data.type, "matrix_world": rows(item.matrix_world),
            "energy": float(item.data.energy), "color": [float(v) for v in item.data.color],
        } for item in sorted((obj for obj in scene.objects if obj.type == "LIGHT"), key=lambda value: value.name)]
        payload = {
            "schema": "candidate-shape-combination-probe-v1", "medical_truth": False,
            "source_blend": str(Path(bpy.data.filepath).resolve()), "source_blend_sha256": sha256(Path(bpy.data.filepath).resolve()),
            "atlas_sha256": sha256(args.atlas), "measurement_contract_sha256": sha256(args.contract),
            "profile_sha256": sha256(args.profile), "native_parameters_sha256": sha256(args.native_parameters),
            "requested_betas": requested, "effective_betas": effective, "scene_recorded_betas": recorded,
            "beta_control_chain_verified": requested == effective == recorded,
            "pose_degrees": dict(scene.get("skel_pose_degrees", {})),
            "model": {
                "object_name": target.name, "vertex_count": len(local_vertices), "face_count": len(polygons),
                "topology_signature_sha256": signature,
                "evaluated_local_vertices_float32_sha256": vertex_digest.hexdigest(),
                "matrix_world": rows(evaluated.matrix_world),
                "bounds_body_local_m": {"min": local_min, "max": local_max},
                "bounds_world_m": {"min": world_min, "max": world_max},
            },
            "camera": {"name": camera.name, "matrix_world": rows(camera.matrix_world), "world_to_opencv": rows(world_to_opencv_camera(camera)), "resolution": [args.width, args.height]},
            "bed": {"name": bed.name, "matrix_world": rows(bed.matrix_world), "top_z_m": bed_top, "minimum_body_clearance_m": clearance, "penetration_depth_m": max(0.0, -clearance)},
            "scene_invariants": {"frame": scene.frame_current, "unit_scale_length": float(scene.unit_settings.scale_length), "render_engine": scene.render.engine, "target_matrix_world": rows(target.matrix_world), "lights": lights},
            "measurements_m": measurements, "points": point_records,
        }
    finally:
        if mesh is not None:
            evaluated.to_mesh_clear()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_SHAPE_COMBINATION_PROBE=PASS")


if __name__ == "__main__":
    main()
