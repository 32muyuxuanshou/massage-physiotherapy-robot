"""Independent geometry/projection probe for one frozen prone pose snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


TARGET_NAME = "SKEL-skin-female"
CAMERA_NAME = "ACU_PRONE_BACK_CAMERA"


def _arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=1024)
    return parser.parse_args(argv)


def _topology_signature(mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update((",".join(str(int(value)) for value in polygon.vertices) + ";").encode("ascii"))
    return digest.hexdigest()


def _matrix_rows(matrix) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def main() -> None:
    args = _arguments()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8-sig"))
    target = bpy.data.objects.get(TARGET_NAME)
    camera = bpy.data.objects.get(CAMERA_NAME)
    bed = bpy.data.objects.get("ACU_PRONE_BED")
    if target is None or camera is None or bed is None:
        raise RuntimeError("prone target/camera/bed missing")
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        world_vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        w2b = camera.matrix_world.inverted()
        w2cv = Matrix.Diagonal((1.0, -1.0, -1.0, 1.0)) @ w2b
        fx = float(camera.data.lens) / float(camera.data.sensor_width) * args.width
        fy = fx
        cx, cy = args.width / 2.0, args.height / 2.0
        camera_origin = camera.matrix_world.translation.copy()
        points = []
        for frozen in fixture["anchors"]:
            face_index = int(frozen["face_index"])
            polygon = mesh.polygons[face_index]
            vertices = [int(value) for value in polygon.vertices]
            weights = [float(value) for value in frozen["barycentric"]]
            point = sum((world_vertices[index] * weight for index, weight in zip(vertices, weights)), Vector((0.0, 0.0, 0.0)))
            normal = (world_vertices[vertices[1]] - world_vertices[vertices[0]]).cross(world_vertices[vertices[2]] - world_vertices[vertices[0]]).normalized()
            camera_point = w2cv @ point.to_4d()
            z = float(camera_point.z)
            uv = [fx * float(camera_point.x) / z + cx, fy * float(camera_point.y) / z + cy]
            to_camera = camera_origin - point
            front_facing = normal.dot(to_camera.normalized()) > 0.0
            direction = point - camera_origin
            distance = direction.length
            direction.normalize()
            hit, location, _hit_normal, hit_face, hit_object, _matrix = scene.ray_cast(depsgraph, camera_origin, direction, distance=distance + 1e-4)
            ray_error = float((location - point).length) if hit else None
            visible = bool(hit and hit_object and hit_object.name == target.name and ray_error is not None and ray_error <= 1e-4 and front_facing)
            points.append({
                "point_id": frozen["point_id"],
                "surface": frozen["surface"],
                "face_index": face_index,
                "vertex_indices": vertices,
                "barycentric": weights,
                "xyz_world_m": list(point),
                "world_normal": list(normal),
                "xyz_camera_opencv_m": [float(camera_point.x), float(camera_point.y), z],
                "uv_pixel_opencv": uv,
                "front_facing": front_facing,
                "visible": visible,
                "ray_hit_object": hit_object.name if hit and hit_object else None,
                "ray_hit_face_index": int(hit_face) if hit else None,
                "ray_error_m": ray_error,
            })
        output = {
            "schema": "skel-native-prone-pose-probe-v1",
            "blend": bpy.data.filepath,
            "scene_contract": str(scene.get("acu_training_scene_contract") or ""),
            "pose_profile_sha256": str(scene.get("skel_pose_profile_sha256") or ""),
            "pose_degrees": dict(scene.get("skel_pose_degrees", {})),
            "betas": [float(value) for value in scene.get("skel_betas", [])],
            "model": {
                "vertex_count": len(mesh.vertices),
                "polygon_count": len(mesh.polygons),
                "topology_signature_sha256": _topology_signature(mesh),
                "target_matrix_world": _matrix_rows(target.matrix_world),
            },
            "camera": {"world_to_opencv": _matrix_rows(w2cv), "fx": fx, "fy": fy, "cx": cx, "cy": cy, "width": args.width, "height": args.height},
            "bed": {"top_z_m": float(bed.location.z + bed.dimensions.z * 0.5), "location": list(bed.location), "dimensions": list(bed.dimensions)},
            "bounds_world_m": {
                "min": [min(float(vertex[i]) for vertex in world_vertices) for i in range(3)],
                "max": [max(float(vertex[i]) for vertex in world_vertices) for i in range(3)],
            },
            "world_vertices_m": [list(vertex) for vertex in world_vertices],
            "points": points,
        }
    finally:
        evaluated.to_mesh_clear()
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_POSE_SNAPSHOT_PROBE=PASS")


if __name__ == "__main__":
    main()
