"""Legacy RGB-only/v1 verifier; superseded by workstreams/independent_verifier."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import bpy
import acupoint_blender_mcp_bridge as bridge
from mathutils import Matrix, Vector


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def vector_error(first, second) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(first, second)))


def normalized_labels(payload: dict) -> dict:
    result = json.loads(json.dumps(payload))
    result.pop("created_at", None)
    return result


atlas_path = os.environ["ACU_DELIVERY_ATLAS"]
labels_path = Path(os.environ["ACU_DELIVERY_LABELS"])
rgb_path = Path(os.environ["ACU_DELIVERY_RGB"])
replay_dir = Path(os.environ["ACU_DELIVERY_REPLAY_DIR"])
result_path = Path(os.environ["ACU_DELIVERY_VERIFY_RESULT"])

labels = json.loads(labels_path.read_text(encoding="utf-8-sig"))
assert labels["schema_version"] == "acupoint-training-sample-v1"
assert len(labels["points"]) == 1
recorded = labels["points"][0]
assert recorded["point_id"] == "11_MIDLINE"

validation = bridge.command_validate_atlas({"atlas_path": atlas_path})
assert validation["valid"], validation
camera_result = bridge.command_set_camera_view(
    {
        "preset": "front",
        "distance_scale": 1.0,
        "focal_length_mm": 55.0,
        "camera_name": "ACU_TRAIN_CAMERA_TEST",
    }
)
camera = bpy.data.objects[camera_result["camera"]]
target = next(
    obj
    for obj in bpy.context.scene.objects
    if obj.type == "MESH" and str(obj.get("skel_role") or "") == "skin"
)

face_index = int(recorded["face_index"])
weights = tuple(float(value) for value in recorded["barycentric"])
base_polygon = target.data.polygons[face_index]
base_vertex_indices = tuple(int(value) for value in base_polygon.vertices)

depsgraph = bpy.context.evaluated_depsgraph_get()
evaluated = target.evaluated_get(depsgraph)
evaluated_mesh = evaluated.to_mesh()
try:
    evaluated_polygon = evaluated_mesh.polygons[face_index]
    evaluated_vertex_indices = tuple(int(value) for value in evaluated_polygon.vertices)
    local_point = Vector((0.0, 0.0, 0.0))
    for weight, vertex_index in zip(weights, evaluated_vertex_indices):
        local_point += evaluated_mesh.vertices[vertex_index].co * weight
    world_point = evaluated.matrix_world @ local_point
    normal_matrix = evaluated.matrix_world.inverted().transposed().to_3x3()
    world_normal = (normal_matrix @ evaluated_polygon.normal).normalized()
finally:
    evaluated.to_mesh_clear()

world_to_opencv = Matrix(labels["camera"]["world_to_opencv_camera"])
camera_point = world_to_opencv @ world_point
intrinsics = labels["camera"]["intrinsics"]
independent_u = intrinsics["fx"] * camera_point.x / camera_point.z + intrinsics["cx"]
independent_v = intrinsics["fy"] * camera_point.y / camera_point.z + intrinsics["cy"]
independent_uv = [float(independent_u), float(independent_v)]
independent_in_front = bool(camera_point.z > 0.0)
independent_in_frame = bool(
    independent_in_front
    and 0.0 <= independent_u <= intrinsics["width"]
    and 0.0 <= independent_v <= intrinsics["height"]
)

camera_origin = camera.matrix_world.translation
to_point = world_point - camera_origin
distance = to_point.length
direction = to_point.normalized()
independent_front_facing = bool(world_normal.dot(-direction) > 0.0)
tolerance = max(1e-4, distance * 1e-5)
hit, hit_location, _hit_normal, hit_face_index, hit_object, _matrix = bpy.context.scene.ray_cast(
    depsgraph, camera_origin, direction, distance=distance + tolerance
)
hit_original = getattr(hit_object, "original", hit_object) if hit_object is not None else None
hit_name = hit_original.name if hit_original is not None else None
ray_error = float((hit_location - world_point).length) if hit else None
visible_on_target = bool(hit and hit_name == target.name and ray_error is not None and ray_error <= tolerance)
if not independent_in_front:
    independent_reason = "BEHIND_CAMERA"
elif not independent_in_frame:
    independent_reason = "OUT_OF_FRAME"
elif not independent_front_facing:
    independent_reason = "BACK_FACING"
elif visible_on_target:
    independent_reason = "VISIBLE"
elif hit_name == target.name:
    independent_reason = "SELF_OCCLUDED"
elif hit_name:
    independent_reason = "EXTERNAL_OCCLUDED"
else:
    raise AssertionError("independent ray cast did not hit any object")
independent_visible = independent_reason == "VISIBLE"

xyz_error_m = vector_error(world_point, recorded["xyz_world_blender_m"])
normal_error = vector_error(world_normal, recorded["world_normal"])
uv_error_px = vector_error(independent_uv, recorded["uv_pixel_opencv"])

replay = bridge.command_export_training_sample(
    {
        "atlas_path": atlas_path,
        "output_dir": str(replay_dir),
        "point_ids": ["11_MIDLINE"],
        "camera_name": camera.name,
        "width": 1024,
        "height": 1024,
    }
)
replay_labels_path = Path(replay["labels_path"])
replay_labels = json.loads(replay_labels_path.read_text(encoding="utf-8-sig"))

checks = {
    "face_index_exact": face_index == 13745,
    "vertex_indices_exact": list(base_vertex_indices) == recorded["vertex_indices"],
    "evaluated_vertex_indices_exact": list(evaluated_vertex_indices) == recorded["vertex_indices"],
    "barycentric_sum_error": abs(sum(weights) - 1.0),
    "xyz_world_error_m": xyz_error_m,
    "world_normal_error": normal_error,
    "uv_error_px": uv_error_px,
    "in_front_exact": independent_in_front == recorded["in_front"],
    "in_frame_exact": independent_in_frame == recorded["in_frame"],
    "front_facing_exact": independent_front_facing == recorded["front_facing"],
    "visible_exact": independent_visible == recorded["visible"],
    "visibility_reason_exact": independent_reason == recorded["visibility_reason"],
    "ray_hit_object_exact": hit_name == recorded["ray_hit_object"],
    "ray_hit_face_index_exact": int(hit_face_index) == int(recorded["ray_hit_face_index"]),
    "reopen_reexport_labels_equal_ignoring_created_at": normalized_labels(labels) == normalized_labels(replay_labels),
    "reopen_reexport_rgb_sha256_equal": sha256(rgb_path) == sha256(Path(replay["rgb_path"])),
}
passed = bool(
    checks["face_index_exact"]
    and checks["vertex_indices_exact"]
    and checks["evaluated_vertex_indices_exact"]
    and checks["barycentric_sum_error"] < 1e-7
    and checks["xyz_world_error_m"] < 1e-6
    and checks["world_normal_error"] < 1e-6
    and checks["uv_error_px"] < 1e-3
    and checks["in_front_exact"]
    and checks["in_frame_exact"]
    and checks["front_facing_exact"]
    and checks["visible_exact"]
    and checks["visibility_reason_exact"]
    and checks["ray_hit_object_exact"]
    and checks["ray_hit_face_index_exact"]
    and checks["reopen_reexport_labels_equal_ignoring_created_at"]
)
result = {
    "passed": passed,
    "independent_path": "manual evaluated mesh barycentric + K projection + scene.ray_cast",
    "checks": checks,
    "independent_values": {
        "face_index": face_index,
        "vertex_indices": list(base_vertex_indices),
        "barycentric": list(weights),
        "xyz_world_blender_m": [float(value) for value in world_point],
        "world_normal": [float(value) for value in world_normal],
        "xyz_camera_opencv_m": [float(value) for value in camera_point[:3]],
        "uv_pixel_opencv": independent_uv,
        "in_front": independent_in_front,
        "in_frame": independent_in_frame,
        "front_facing": independent_front_facing,
        "visible": independent_visible,
        "visibility_reason": independent_reason,
        "ray_hit_object": hit_name,
        "ray_hit_face_index": int(hit_face_index),
        "ray_error_m": ray_error,
    },
    "replay": replay,
    "blend_saved_by_verifier": False,
}
result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
assert passed, result
print("ACU_DELIVERY_VERIFY=PASS")
