"""Shared Blender-side geometry and RGB-D export core.

This package is intentionally independent of the doctor annotation UI, MCP bridge,
and batch runner.  Callers are responsible for composing their final labels schema.
"""

from .camera_geometry import (
    CameraIntrinsics,
    backproject_pixel,
    camera_intrinsics,
    project_world_point,
    world_to_opencv_camera,
)
from .render_buffers import RenderBuffersResult, render_scene_buffers
from .sample_export import SampleExportResult, export_sample
from .surface_binding import SurfaceSample, sample_surface_binding
from .visibility import VisibilityResult, evaluate_visibility

__all__ = [
    "CameraIntrinsics",
    "RenderBuffersResult",
    "SampleExportResult",
    "SurfaceSample",
    "VisibilityResult",
    "backproject_pixel",
    "camera_intrinsics",
    "evaluate_visibility",
    "export_sample",
    "project_world_point",
    "render_scene_buffers",
    "sample_surface_binding",
    "world_to_opencv_camera",
]

