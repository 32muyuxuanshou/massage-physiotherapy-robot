"""HuMMan Point RGB-D geometry utilities.

Coordinate contract used here:
  X_camera = R_world_to_camera @ X_world + T_world_to_camera
  depth PNG values are millimetre Z-depth (Open3D/HuMMan default scale=1000)
  pixel coordinates refer to pixel centres and use the OpenCV pinhole model

The public release does not provide distortion coefficients. This code therefore
uses the released images and K matrices as-is and records that assumption in every
prepared observation.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


DEPTH_SCALE = 1000.0


def load_cameras(path: Path) -> dict[str, dict[str, np.ndarray]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {name: {key: np.asarray(value, np.float64) for key, value in item.items()}
            for name, item in raw.items()}


def read_video_frame(path: Path, frame_id: int) -> np.ndarray:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"cannot open video: {path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
    ok, bgr = cap.read()
    cap.release()
    if not ok:
        raise IndexError(f"cannot read frame {frame_id} from {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def read_image(path: Path, flags: int) -> np.ndarray | None:
    """Read images on Windows paths that may contain non-ASCII characters."""
    if not path.is_file():
        return None
    encoded = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(encoded, flags)


def world_to_camera(points: np.ndarray, camera: dict[str, np.ndarray]) -> np.ndarray:
    return points @ camera["R"].T + camera["T"]


def camera_to_world(points: np.ndarray, camera: dict[str, np.ndarray]) -> np.ndarray:
    return (points - camera["T"]) @ camera["R"]


def transform_camera(points: np.ndarray, src: dict[str, np.ndarray],
                     dst: dict[str, np.ndarray]) -> np.ndarray:
    return world_to_camera(camera_to_world(points, src), dst)


def unproject_z_depth(depth_mm: np.ndarray, K: np.ndarray,
                      min_depth_m: float = 0.1, max_depth_m: float = 5.0,
                      stride: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Return camera-space points and their source pixels (u,v)."""
    if depth_mm.ndim != 2 or depth_mm.dtype != np.uint16:
        raise ValueError(f"expected uint16 HxW depth, got {depth_mm.dtype} {depth_mm.shape}")
    v, u = np.mgrid[0:depth_mm.shape[0]:stride, 0:depth_mm.shape[1]:stride]
    z = depth_mm[::stride, ::stride].astype(np.float64) / DEPTH_SCALE
    valid = np.isfinite(z) & (z > min_depth_m) & (z < max_depth_m)
    u, v, z = u[valid], v[valid], z[valid]
    x = (u - K[0, 2]) * z / K[0, 0]
    y = (v - K[1, 2]) * z / K[1, 1]
    return np.column_stack((x, y, z)), np.column_stack((u, v))


def project(points: np.ndarray, K: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(points).all(axis=1) & (points[:, 2] > 1e-6)
    uv = np.full((len(points), 2), np.nan, np.float64)
    uv[valid, 0] = K[0, 0] * points[valid, 0] / points[valid, 2] + K[0, 2]
    uv[valid, 1] = K[1, 1] * points[valid, 1] / points[valid, 2] + K[1, 2]
    return uv, valid


def registered_person_points(depth_mm: np.ndarray, mask_depth: np.ndarray,
                             depth_camera: dict[str, np.ndarray],
                             color_camera: dict[str, np.ndarray],
                             color_shape: tuple[int, int],
                             stride: int = 1) -> tuple[np.ndarray, np.ndarray, dict]:
    """Select the depth-space person mask, then register its points to color."""
    points_depth, source_uv = unproject_z_depth(depth_mm, depth_camera["K"], stride=stride)
    if mask_depth.shape != depth_mm.shape:
        raise ValueError(f"mask/depth shape mismatch: {mask_depth.shape} vs {depth_mm.shape}")
    source_ui = source_uv[:, 0].astype(np.int64)
    source_vi = source_uv[:, 1].astype(np.int64)
    person_source = mask_depth[source_vi, source_ui] > 0
    points_depth = points_depth[person_source]
    points_color = transform_camera(points_depth, depth_camera, color_camera)
    uv, positive = project(points_color, color_camera["K"])
    ui = np.rint(uv[:, 0]).astype(np.int64, casting="unsafe")
    vi = np.rint(uv[:, 1]).astype(np.int64, casting="unsafe")
    height, width = color_shape
    inside = (positive & (ui >= 0) & (ui < width) & (vi >= 0) & (vi < height))
    # Multiple depth pixels can land on one color pixel. Keep only the front
    # surface so background geometry behind a person-mask pixel cannot enter fit.
    zbuffer = np.full((height, width), np.inf, np.float64)
    np.minimum.at(zbuffer, (vi[inside], ui[inside]), points_color[inside, 2])
    front = np.zeros(len(points_color), dtype=bool)
    front[inside] = points_color[inside, 2] <= zbuffer[vi[inside], ui[inside]] + 0.005
    on_person = front
    mask_color_projected = np.zeros((height, width), np.uint8)
    mask_color_projected[vi[on_person], ui[on_person]] = 255
    mask_color_projected = cv2.dilate(mask_color_projected, np.ones((5, 5), np.uint8))
    report = {
        "raw_valid_person_depth_points": int(len(points_depth)),
        "projected_inside_color_image": int(inside.sum()),
        "projected_person_points_after_front_surface_filter": int(on_person.sum()),
        "visibility_filter": "frontmost projected depth within 5 mm per color pixel",
        "person_points_retained_after_projection": int(on_person.sum()),
        "mask_coordinate_frame": "paired Kinect depth image (640x576 in inspected files)",
        "depth_unit": "millimetre_uint16_converted_to_metre",
        "depth_definition": "z_depth",
        "extrinsic_convention": "X_camera=R_world_to_camera@X_world+T_world_to_camera",
        "distortion": "coefficients_absent_in_public_release; released image/K used as-is",
    }
    return points_color[on_person].astype(np.float32), mask_color_projected, report


def mask_bbox(mask: np.ndarray, padding: float = 0.05) -> np.ndarray:
    y, x = np.nonzero(mask > 0)
    if not len(x):
        raise ValueError("empty person mask")
    x0, x1, y0, y1 = x.min(), x.max() + 1, y.min(), y.max() + 1
    pad = padding * max(x1 - x0, y1 - y0)
    return np.asarray([max(0, x0 - pad), max(0, y0 - pad),
                       min(mask.shape[1], x1 + pad), min(mask.shape[0], y1 + pad)],
                      np.float32)


def load_humman_view(root: Path, sequence: str, device: str, frame_id: int) -> dict:
    seq = root / sequence
    cameras = load_cameras(seq / "cameras.json")
    suffix = device.removeprefix("kinect_")
    color_name, depth_name = f"kinect_color_{suffix}", f"kinect_depth_{suffix}"
    rgb = read_video_frame(seq / "kinect_color" / f"{device}.mp4", frame_id)
    depth = read_image(seq / "kinect_depth" / device / f"{frame_id:06d}.png",
                       cv2.IMREAD_UNCHANGED)
    mask = read_image(seq / "kinect_mask" / device / f"{frame_id:06d}.png",
                      cv2.IMREAD_GRAYSCALE)
    if depth is None or mask is None:
        raise FileNotFoundError(f"missing depth or mask for {sequence}/{device}/{frame_id:06d}")
    points, mask_color, registration = registered_person_points(
        depth, mask, cameras[depth_name], cameras[color_name], rgb.shape[:2])
    return {"rgb": rgb, "depth": depth, "mask": mask_color, "mask_depth": mask,
            "points_color": points, "bbox": mask_bbox(mask_color), "color_camera": cameras[color_name],
            "depth_camera": cameras[depth_name], "registration": registration}
