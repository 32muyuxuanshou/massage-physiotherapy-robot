"""High-level single-sample orchestration without imposing a final labels schema."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import bpy
from mathutils import Vector

from .camera_geometry import project_world_point
from .render_buffers import RenderBuffersResult, render_scene_buffers
from .surface_binding import sample_surface_binding
from .visibility import evaluate_visibility


@dataclass
class SampleExportResult:
    buffers: RenderBuffersResult
    points: list[dict[str, Any]]
    ray_tolerance_m: float
    mask_depth_tolerance_m: float


def export_sample(
    *,
    scene: bpy.types.Scene,
    depsgraph: bpy.types.Depsgraph,
    camera: bpy.types.Object,
    skin_object: bpy.types.Object,
    bindings: Iterable[Mapping[str, Any]],
    output_dir: str | Path,
    frame: int | None = None,
    width: int | None = None,
    height: int | None = None,
    render_engine: str = "BLENDER_EEVEE_NEXT",
    ray_tolerance_m: float = 1e-4,
    mask_depth_tolerance_m: float = 1e-4,
    debug_keep_intermediates: bool = False,
) -> SampleExportResult:
    """Resolve bindings, classify visibility, then export aligned render buffers.

    Each binding must contain ``face_index`` and ``barycentric``.  Optional
    ``vertex_indices`` enforces the frozen topology, while any additional fields
    are copied into the returned point record.  The caller owns final labels.json
    composition and model/topology signature validation.
    """

    requested_frame = int(scene.frame_current if frame is None else frame)
    requested_width = int(
        width
        if width is not None
        else round(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
    )
    requested_height = int(
        height
        if height is not None
        else round(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)
    )
    if scene.unit_settings.system != "METRIC" or abs(scene.unit_settings.scale_length - 1.0) > 1e-9:
        raise ValueError("export_sample requires METRIC units with scale_length == 1.0")
    if requested_frame != int(scene.frame_current):
        raise ValueError(
            "export_sample requires scene.frame_current to match frame so evaluated bindings, "
            "visibility, and rendered pixels describe the same instant"
        )

    points: list[dict[str, Any]] = []
    for binding in bindings:
        surface = sample_surface_binding(
            skin_object,
            int(binding["face_index"]),
            binding["barycentric"],
            depsgraph=depsgraph,
            expected_vertex_indices=binding.get("vertex_indices"),
        )
        point_world = Vector(surface.xyz_world_m)
        world_normal = Vector(surface.world_normal)
        projection = project_world_point(
            scene,
            camera,
            point_world,
            width=requested_width,
            height=requested_height,
        )
        visibility = evaluate_visibility(
            scene=scene,
            depsgraph=depsgraph,
            camera=camera,
            target_object=skin_object,
            point_world=point_world,
            world_normal=world_normal,
            ray_tolerance_m=ray_tolerance_m,
            width=requested_width,
            height=requested_height,
        )
        passthrough = {
            key: value
            for key, value in binding.items()
            if key not in {"face_index", "vertex_indices", "barycentric"}
        }
        points.append(
            {
                **passthrough,
                **surface.to_dict(),
                "xyz_camera_opencv_m": projection["xyz_camera_opencv_m"],
                "uv_pixel_opencv": projection["uv_pixel_opencv"],
                "camera_depth_z_m": projection["camera_depth_z_m"],
                "ray_tolerance_m": float(ray_tolerance_m),
                **visibility.to_dict(),
            }
        )

    buffers = render_scene_buffers(
        source_scene=scene,
        camera=camera,
        skin_object=skin_object,
        output_dir=output_dir,
        frame=requested_frame,
        width=requested_width,
        height=requested_height,
        render_engine=render_engine,
        mask_depth_tolerance_m=mask_depth_tolerance_m,
        debug_keep_intermediates=debug_keep_intermediates,
    )
    return SampleExportResult(
        buffers=buffers,
        points=points,
        ray_tolerance_m=float(ray_tolerance_m),
        mask_depth_tolerance_m=float(mask_depth_tolerance_m),
    )
