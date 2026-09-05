"""Blender-side independent scene/evaluated-mesh/ray probe.

Run only through verify_sample.py.  This script intentionally does not enable or
import any project add-on.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


def _arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--ray-request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _topology_signature(mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update(",".join(str(int(index)) for index in polygon.vertices).encode("ascii"))
        digest.update(b";")
    return digest.hexdigest()


def _vector(values) -> Vector:
    return Vector(tuple(float(value) for value in values))


def _maximum_error(a: Vector, b: Vector) -> float:
    return max(abs(float(a[index] - b[index])) for index in range(len(a)))


def _first_rendered_hit(scene, depsgraph, origin: Vector, direction: Vector, distance: float):
    """Ray-cast while skipping objects explicitly excluded from rendering."""
    travelled = 0.0
    current = origin.copy()
    for _ in range(32):
        remaining = max(0.0, distance - travelled)
        if remaining <= 0.0:
            return False, None, None, None, None, None
        hit, location, normal, face, obj, matrix = scene.ray_cast(
            depsgraph, current, direction, distance=remaining
        )
        if not hit:
            return hit, location, normal, face, obj, matrix
        original = bpy.data.objects.get(obj.name) if obj else None
        if obj is not None and not bool(original and original.hide_render):
            return hit, location, normal, face, obj, matrix
        step = max(1.0e-5, (location - current).length + 1.0e-5)
        travelled += step
        current = current + direction * step
    raise RuntimeError("Too many hidden-render ray intersections")


def _point_probe(scene, depsgraph, target, mesh, labels: dict) -> list[dict]:
    camera_data = labels["camera"]
    world_to_cv = Matrix(camera_data["world_to_opencv_camera"])
    camera_to_world = world_to_cv.inverted()
    camera_origin = camera_to_world.translation
    results = []
    for point in labels.get("points", []):
        face_index = int(point["face_index"])
        bary = [float(value) for value in point["barycentric"]]
        stored_vertices = tuple(int(value) for value in point["vertex_indices"])
        result = {"point_id": point.get("point_id"), "face_index": face_index}
        if not 0 <= face_index < len(mesh.polygons):
            result.update({"passed": False, "error": "face index out of range"})
            results.append(result)
            continue
        polygon = mesh.polygons[face_index]
        evaluated_vertices = tuple(int(value) for value in polygon.vertices)
        result["evaluated_vertex_indices"] = list(evaluated_vertices)
        if len(evaluated_vertices) != 3 or evaluated_vertices != stored_vertices:
            result.update({"passed": False, "error": "triangle vertex indices differ"})
            results.append(result)
            continue
        world_vertices = [target.matrix_world @ mesh.vertices[index].co for index in evaluated_vertices]
        point_world = sum((world_vertices[index] * bary[index] for index in range(3)), Vector((0.0, 0.0, 0.0)))
        geometric_normal = (world_vertices[1] - world_vertices[0]).cross(world_vertices[2] - world_vertices[0]).normalized()
        stored_world = _vector(point["xyz_world_blender_m"])
        stored_normal = _vector(point["world_normal"])
        xyz_error = _maximum_error(point_world, stored_world)
        normal_direct_error = _maximum_error(geometric_normal, stored_normal)
        normal_error = normal_direct_error

        direction = point_world - camera_origin
        point_distance = direction.length
        direction.normalize()
        hit, location, _normal, face, hit_object, _matrix = _first_rendered_hit(
            scene, depsgraph, camera_origin, direction, point_distance + 1.0e-4
        )
        ray_error = (location - point_world).length if hit else None
        hit_name = hit_object.name if hit and hit_object else None
        expected_visible = bool(point.get("visible"))
        expected_hit_name = point.get("ray_hit_object")
        expected_hit_face = point.get("ray_hit_face_index")
        visibility_matches = (
            expected_visible
            == bool(
                hit
                and hit_name == target.name
                and ray_error is not None
                and ray_error <= float(point.get("ray_tolerance_m", 1.0e-4))
            )
            and (expected_hit_name is None or expected_hit_name == hit_name)
            and (expected_hit_face is None or int(expected_hit_face) == int(face))
        )
        passed = xyz_error <= 1.0e-6 and normal_error <= 1.0e-5 and visibility_matches
        result.update(
            {
                "passed": passed,
                "xyz_world_recomputed": list(point_world),
                "xyz_max_abs_error_m": xyz_error,
                "geometric_normal": list(geometric_normal),
                "normal_max_abs_error": normal_error,
                "ray_hit": bool(hit),
                "ray_hit_object": hit_name,
                "ray_hit_face_index": int(face) if hit else None,
                "ray_error_m": ray_error,
                "visibility_matches": visibility_matches,
            }
        )
        results.append(result)
    return results


def _pixel_rays(scene, depsgraph, labels: dict, requests: list[dict]) -> list[dict]:
    camera_data = labels["camera"]
    intrinsics = camera_data["intrinsics"]
    fx, fy = float(intrinsics["fx"]), float(intrinsics["fy"])
    cx, cy = float(intrinsics["cx"]), float(intrinsics["cy"])
    world_to_cv = Matrix(camera_data["world_to_opencv_camera"])
    camera_to_world = world_to_cv.inverted()
    origin = camera_to_world.translation
    rotation_c2w = camera_to_world.to_3x3()
    results = []
    for request in requests:
        u, v = float(request["u_center"]), float(request["v_center"])
        direction_cv = Vector(((u - cx) / fx, (v - cy) / fy, 1.0))
        direction_world = (rotation_c2w @ direction_cv).normalized()
        hit, location, normal, face, hit_object, _matrix = _first_rendered_hit(
            scene, depsgraph, origin, direction_world, 1000.0
        )
        item = {"request": request, "hit": bool(hit)}
        if hit:
            hit_cv = world_to_cv @ location.to_4d()
            item.update(
                {
                    "hit_object": hit_object.name if hit_object else None,
                    "hit_face_index": int(face),
                    "hit_world": list(location),
                    "hit_normal_world": list(normal),
                    "hit_camera_xyz": [float(hit_cv[0]), float(hit_cv[1]), float(hit_cv[2])],
                    "hit_zc_m": float(hit_cv[2]),
                }
            )
        results.append(item)
    return results


def main() -> None:
    args = _arguments()
    labels = _load(args.labels)
    ray_request = _load(args.ray_request)
    target_name = str(labels["model"]["object_name"])
    target = bpy.data.objects.get(target_name)
    if target is None or target.type != "MESH":
        raise RuntimeError(f"Target mesh not found: {target_name}")
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    evaluated_target = target.evaluated_get(depsgraph)
    mesh = evaluated_target.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        base_topology = _topology_signature(target.data)
        evaluated_topology = _topology_signature(mesh)
        expected_model = labels["model"]
        model_checks = {
            "base_vertex_count": len(target.data.vertices),
            "base_polygon_count": len(target.data.polygons),
            "evaluated_vertex_count": len(mesh.vertices),
            "evaluated_polygon_count": len(mesh.polygons),
            "base_topology_sha256": base_topology,
            "evaluated_topology_sha256": evaluated_topology,
            "expected_topology_sha256": expected_model["topology_signature_sha256"],
        }
        model_ok = (
            len(target.data.vertices) == int(expected_model["vertex_count"])
            and len(target.data.polygons) == int(expected_model["polygon_count"])
            and len(mesh.vertices) == int(expected_model["vertex_count"])
            and len(mesh.polygons) == int(expected_model["polygon_count"])
            and base_topology == expected_model["topology_signature_sha256"]
            and evaluated_topology == expected_model["topology_signature_sha256"]
        )
        point_results = _point_probe(scene, depsgraph, evaluated_target, mesh, labels)
        point_ok = bool(point_results) and all(item.get("passed") for item in point_results)
        output = {
            "schema": "independent-blender-scene-probe-v1",
            "blender_version": bpy.app.version_string,
            "blend_path": bpy.data.filepath,
            "blend_dirty": bpy.data.is_dirty,
            "target_object": target.name,
            "camera_intrinsics": {
                "fx": float(labels["camera"]["intrinsics"]["fx"]),
                "fy": float(labels["camera"]["intrinsics"]["fy"]),
                "cx": float(labels["camera"]["intrinsics"]["cx"]),
                "cy": float(labels["camera"]["intrinsics"]["cy"]),
            },
            "scene_unit_scale_length": float(scene.unit_settings.scale_length),
            "model_checks": model_checks,
            "point_results": point_results,
            "pixel_rays": _pixel_rays(scene, depsgraph, labels, ray_request.get("pixels", [])),
            "point_pixel_rays": _pixel_rays(
                scene,
                depsgraph,
                labels,
                [
                    {
                        **item,
                        "u_center": float(item["column"]) + 0.5,
                        "v_center": float(item["row"]) + 0.5,
                    }
                    for item in ray_request.get("point_pixels", [])
                ],
            ),
            "scene_geometry_passed": bool(model_ok and point_ok),
            "scene_geometry_summary": {"model_ok": model_ok, "point_ok": point_ok, "point_count": len(point_results)},
        }
    finally:
        evaluated_target.to_mesh_clear()
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
