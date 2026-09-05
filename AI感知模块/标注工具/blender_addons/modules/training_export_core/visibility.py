"""Scene-level ray visibility for evaluated surface points."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import bpy
from mathutils import Vector

from .camera_geometry import project_world_point


@dataclass(frozen=True)
class VisibilityResult:
    in_front: bool
    in_frame: bool
    front_facing: bool
    visible: bool
    visibility_reason: str
    ray_hit_object: str | None
    ray_hit_face_index: int | None
    ray_error_m: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def _same_object(hit_object: bpy.types.Object | None, target_object: bpy.types.Object) -> bool:
    if hit_object is None:
        return False
    if hit_object == target_object:
        return True
    hit_original = getattr(hit_object, "original", None)
    target_original = getattr(target_object, "original", None)
    return hit_original == target_object or hit_object == target_original or (
        hit_original is not None and target_original is not None and hit_original == target_original
    )


def _hidden_for_render(obj: bpy.types.Object) -> bool:
    if bool(obj.hide_render):
        return True
    original = getattr(obj, "original", None)
    return original is not None and bool(original.hide_render)


def evaluate_visibility(
    *,
    scene: bpy.types.Scene,
    depsgraph: bpy.types.Depsgraph,
    camera: bpy.types.Object,
    target_object: bpy.types.Object,
    point_world: Vector,
    world_normal: Vector,
    ray_tolerance_m: float = 1e-4,
    width: int | None = None,
    height: int | None = None,
) -> VisibilityResult:
    """Classify a point using projection, front-face test, and ``scene.ray_cast``."""

    projection = project_world_point(
        scene, camera, point_world, width=width, height=height
    )
    in_front = bool(projection["in_front"])
    in_frame = bool(projection["in_frame"])
    camera_origin = camera.matrix_world.translation.copy()
    to_camera = camera_origin - point_world
    front_facing = to_camera.length_squared > 0.0 and world_normal.dot(to_camera.normalized()) > 0.0

    if not in_front:
        return VisibilityResult(False, False, front_facing, False, "BEHIND_CAMERA", None, None, None)
    if not in_frame:
        return VisibilityResult(True, False, front_facing, False, "OUT_OF_FRAME", None, None, None)
    if not front_facing:
        return VisibilityResult(True, True, False, False, "BACK_FACING", None, None, None)

    point_distance = (point_world - camera_origin).length
    if point_distance <= 0.0:
        raise ValueError("point coincides with camera origin")
    direction = (point_world - camera_origin).normalized()
    remaining = point_distance + float(ray_tolerance_m)
    cast_origin = camera_origin.copy()
    hit = False
    location = None
    face_index = -1
    hit_object = None
    skip_epsilon = max(1e-6, float(ray_tolerance_m) * 0.1)
    for _attempt in range(64):
        hit, location, _normal, face_index, hit_object, _matrix = scene.ray_cast(
            depsgraph,
            cast_origin,
            direction,
            distance=remaining,
        )
        if not hit or hit_object is None:
            break
        if not _hidden_for_render(hit_object):
            break
        travelled = float((location - cast_origin).length)
        remaining -= travelled + skip_epsilon
        if remaining <= 0.0:
            hit = False
            hit_object = None
            break
        cast_origin = location + direction * skip_epsilon
    else:
        raise RuntimeError("scene.ray_cast exceeded 64 hidden-render-object skips")

    if not hit or hit_object is None or location is None:
        raise RuntimeError("scene.ray_cast found no render-visible surface for an in-frame front-facing point")

    ray_error = float((location - point_world).length)
    same_target = _same_object(hit_object, target_object)
    visible = same_target and ray_error <= float(ray_tolerance_m)
    if visible:
        reason = "VISIBLE"
    elif same_target:
        reason = "SELF_OCCLUDED"
    else:
        reason = "EXTERNAL_OCCLUDED"
    return VisibilityResult(
        in_front=True,
        in_frame=True,
        front_facing=True,
        visible=visible,
        visibility_reason=reason,
        ray_hit_object=hit_object.name,
        ray_hit_face_index=int(face_index),
        ray_error_m=ray_error,
    )
