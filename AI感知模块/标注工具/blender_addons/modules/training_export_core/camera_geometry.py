"""Camera intrinsics and OpenCV-coordinate projection helpers for Blender 4.5."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import bpy
from mathutils import Matrix, Vector


@dataclass(frozen=True)
class CameraIntrinsics:
    """Pinhole intrinsics for top-left-origin OpenCV pixel coordinates."""

    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    lens_mm: float
    sensor_width_mm: float
    sensor_height_mm: float
    sensor_fit: str
    pixel_aspect_x: float
    pixel_aspect_y: float
    shift_x: float
    shift_y: float

    @property
    def K(self) -> list[list[float]]:
        return [[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["K"] = self.K
        return payload


def camera_intrinsics(
    scene: bpy.types.Scene,
    camera: bpy.types.Object,
    *,
    width: int | None = None,
    height: int | None = None,
) -> CameraIntrinsics:
    """Return Blender camera intrinsics using actual render size and sensor fit.

    The returned principal point follows Blender shift conventions but uses OpenCV
    image coordinates: +X right, +Y down, origin at the top-left image edge.
    """

    if camera.type != "CAMERA" or camera.data.type != "PERSP":
        raise ValueError("camera must be a perspective CAMERA object")

    width = int(
        width
        if width is not None
        else round(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
    )
    height = int(
        height
        if height is not None
        else round(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)
    )
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid render resolution: {width}x{height}")

    pixel_aspect_x = float(scene.render.pixel_aspect_x)
    pixel_aspect_y = float(scene.render.pixel_aspect_y)
    if pixel_aspect_x <= 0.0 or pixel_aspect_y <= 0.0:
        raise ValueError("pixel aspect values must be positive")
    pixel_aspect_ratio = pixel_aspect_y / pixel_aspect_x

    data = camera.data
    sensor_fit = data.sensor_fit
    if sensor_fit == "AUTO":
        sensor_fit = "HORIZONTAL" if width >= height * pixel_aspect_ratio else "VERTICAL"

    if sensor_fit == "VERTICAL":
        sensor_size_mm = float(data.sensor_height)
        view_fac_px = height * pixel_aspect_ratio
    else:
        sensor_size_mm = float(data.sensor_width)
        view_fac_px = float(width)
    if data.lens <= 0.0 or sensor_size_mm <= 0.0 or view_fac_px <= 0.0:
        raise ValueError("camera lens, sensor size, and view factor must be positive")

    pixel_size_mm = sensor_size_mm / float(data.lens) / view_fac_px
    fx = 1.0 / pixel_size_mm
    fy = fx / pixel_aspect_ratio
    cx = width * 0.5 - float(data.shift_x) * view_fac_px
    cy = height * 0.5 + float(data.shift_y) * view_fac_px / pixel_aspect_ratio
    return CameraIntrinsics(
        width=width,
        height=height,
        fx=float(fx),
        fy=float(fy),
        cx=float(cx),
        cy=float(cy),
        lens_mm=float(data.lens),
        sensor_width_mm=float(data.sensor_width),
        sensor_height_mm=float(data.sensor_height),
        sensor_fit=str(sensor_fit),
        pixel_aspect_x=pixel_aspect_x,
        pixel_aspect_y=pixel_aspect_y,
        shift_x=float(data.shift_x),
        shift_y=float(data.shift_y),
    )


def world_to_opencv_camera(camera: bpy.types.Object) -> Matrix:
    """Return world-to-camera with OpenCV axes (+X right, +Y down, +Z forward)."""

    if camera.type != "CAMERA":
        raise ValueError("camera must be a CAMERA object")
    blender_to_opencv = Matrix(
        (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, -1.0, 0.0, 0.0),
            (0.0, 0.0, -1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    return blender_to_opencv @ camera.matrix_world.inverted()


def project_world_point(
    scene: bpy.types.Scene,
    camera: bpy.types.Object,
    point_world: Vector,
    *,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Project one world point to OpenCV camera coordinates and top-left pixels."""

    intrinsics = camera_intrinsics(scene, camera, width=width, height=height)
    camera_point = world_to_opencv_camera(camera) @ point_world
    x, y, z = float(camera_point.x), float(camera_point.y), float(camera_point.z)
    if z == 0.0:
        u = float("inf")
        v = float("inf")
    else:
        u = intrinsics.fx * x / z + intrinsics.cx
        v = intrinsics.fy * y / z + intrinsics.cy
    in_front = z > 0.0
    in_frame = in_front and 0.0 <= u < intrinsics.width and 0.0 <= v < intrinsics.height
    return {
        "xyz_camera_opencv_m": [x, y, z],
        "uv_pixel_opencv": [float(u), float(v)],
        "camera_depth_z_m": z,
        "in_front": bool(in_front),
        "in_frame": bool(in_frame),
        "intrinsics": intrinsics,
    }


def backproject_pixel(u: float, v: float, depth_z: float, intrinsics: CameraIntrinsics) -> Vector:
    """Back-project top-left-origin pixel coordinates and camera Z to OpenCV XYZ."""

    if depth_z <= 0.0:
        raise ValueError("depth_z must be positive")
    x = (float(u) - intrinsics.cx) * float(depth_z) / intrinsics.fx
    y = (float(v) - intrinsics.cy) * float(depth_z) / intrinsics.fy
    return Vector((x, y, float(depth_z)))


def matrix_rows(matrix: Matrix) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]
