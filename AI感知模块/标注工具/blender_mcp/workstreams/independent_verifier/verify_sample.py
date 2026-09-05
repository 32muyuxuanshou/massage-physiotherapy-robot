#!/usr/bin/env python3
"""Independent SKEL RGB/RGB-D sample verifier.

This module intentionally does not import the sample generator, Blender MCP bridge,
or the acupoint annotation add-on.  Scalar camera math, image/depth validation,
and Blender scene probing are kept on a separate implementation path.
"""

from __future__ import annotations

import argparse
import ast
from array import array
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

from PIL import Image, ImageChops


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROTECTED_MANIFEST = SCRIPT_DIR / "protected_assets.json"
DEFAULT_BLENDER_PROBE = SCRIPT_DIR / "blender_scene_probe.py"

EPS_MATRIX = 1.0e-6
EPS_XYZ_M = 1.0e-6
EPS_UV_PX = 1.0e-3
EPS_BARY_SUM = 1.0e-6
EPS_NORMAL = 1.0e-5
EPS_DEPTH_ZERO_M = 1.0e-7
DEPTH_RAY_ABS_TOL_M = 0.002
DEPTH_RAY_REL_TOL = 0.001
POINT_PIXEL_DEPTH_TOL_M = 0.010


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _max_abs(values: list[float]) -> float:
    return max((abs(float(value)) for value in values), default=0.0)


def _sub(a: list[float], b: list[float]) -> list[float]:
    return [float(x) - float(y) for x, y in zip(a, b)]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def _mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(float(a) * float(b) for a, b in zip(row, vector)) for row in matrix]


def _mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(float(a[i][k]) * float(b[k][j]) for k in range(len(b))) for j in range(len(b[0]))]
        for i in range(len(a))
    ]


def _invert_rigid4(matrix: list[list[float]]) -> list[list[float]]:
    rotation = [[float(matrix[i][j]) for j in range(3)] for i in range(3)]
    translation = [float(matrix[i][3]) for i in range(3)]
    rotation_t = [[rotation[j][i] for j in range(3)] for i in range(3)]
    inverse_translation = [-_dot(row, translation) for row in rotation_t]
    return [
        rotation_t[0] + [inverse_translation[0]],
        rotation_t[1] + [inverse_translation[1]],
        rotation_t[2] + [inverse_translation[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _is_matrix(value: Any, rows: int, cols: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == rows
        and all(isinstance(row, list) and len(row) == cols for row in value)
    )


class Recorder:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.capabilities: dict[str, str] = {}

    def add(
        self,
        check_id: str,
        status: str,
        message: str,
        *,
        severity: str = "P1",
        metrics: dict[str, Any] | None = None,
    ) -> None:
        item: dict[str, Any] = {
            "id": check_id,
            "status": status,
            "severity_if_failed": severity,
            "message": message,
        }
        if metrics is not None:
            item["metrics"] = metrics
        self.checks.append(item)

    def passed(self) -> bool:
        return not any(check["status"] == "FAIL" for check in self.checks)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _locate_sample(path: Path) -> tuple[Path, Path]:
    path = path.resolve()
    if (path / "labels.json").is_file():
        return path, path / "labels.json"
    candidate = path / "sample_000001"
    if (candidate / "labels.json").is_file():
        return candidate, candidate / "labels.json"
    raise FileNotFoundError(f"Cannot find labels.json under {path}")


def _read_npy_2d(path: Path) -> tuple[tuple[int, int], array]:
    """Read a C-order 2-D little-endian float32/float64 .npy without NumPy."""
    with path.open("rb") as handle:
        if handle.read(6) != b"\x93NUMPY":
            raise ValueError("not a NumPy .npy file")
        major, minor = handle.read(2)
        if (major, minor) == (1, 0):
            header_length = struct.unpack("<H", handle.read(2))[0]
        elif major in (2, 3):
            header_length = struct.unpack("<I", handle.read(4))[0]
        else:
            raise ValueError(f"unsupported .npy version {major}.{minor}")
        header = ast.literal_eval(handle.read(header_length).decode("latin1").strip())
        shape = tuple(int(v) for v in header["shape"])
        if len(shape) != 2 or header.get("fortran_order"):
            raise ValueError("depth must be a C-order 2-D array")
        descriptor = str(header["descr"])
        if descriptor not in ("<f4", "=f4", "|f4", "<f8", "=f8", "|f8"):
            raise ValueError(f"depth dtype must be float32/float64, got {descriptor}")
        typecode = "f" if descriptor.endswith("f4") else "d"
        values = array(typecode)
        values.frombytes(handle.read())
        if descriptor.startswith(">") and sys.byteorder == "little":
            values.byteswap()
        expected = shape[0] * shape[1]
        if len(values) != expected:
            raise ValueError(f"depth payload length {len(values)} != {expected}")
        return (shape[0], shape[1]), values


def _npy_descriptor(path: Path) -> str:
    with path.open("rb") as handle:
        if handle.read(6) != b"\x93NUMPY":
            raise ValueError("not a NumPy .npy file")
        major, minor = handle.read(2)
        if (major, minor) == (1, 0):
            header_length = struct.unpack("<H", handle.read(2))[0]
        elif major in (2, 3):
            header_length = struct.unpack("<I", handle.read(4))[0]
        else:
            raise ValueError(f"unsupported .npy version {major}.{minor}")
        header = ast.literal_eval(handle.read(header_length).decode("latin1").strip())
        return str(header["descr"])


def _image_luma_bytes(path: Path) -> tuple[tuple[int, int], bytes]:
    with Image.open(path) as image:
        gray = image.convert("L")
        return (gray.height, gray.width), gray.tobytes()


def _protected_checks(recorder: Recorder, manifest_path: Path) -> dict[str, Any]:
    evidence: dict[str, Any] = {"manifest": str(manifest_path), "assets": []}
    if not manifest_path.is_file():
        recorder.add("protected_manifest", "FAIL", f"Protected manifest missing: {manifest_path}", severity="P0")
        return evidence
    manifest = _load_json(manifest_path)
    all_match = True
    for entry in manifest.get("files", []):
        path = Path(entry["path"])
        expected = str(entry["sha256"]).lower()
        exists = path.is_file()
        actual = _sha256(path) if exists else None
        matches = exists and actual == expected
        all_match &= matches
        evidence["assets"].append(
            {
                "name": entry.get("name", path.name),
                "path": str(path),
                "exists": exists,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "matches": matches,
            }
        )
    recorder.add(
        "protected_assets_unchanged",
        "PASS" if all_match else "FAIL",
        "All protected files match the frozen baseline." if all_match else "One or more protected files changed or are missing.",
        severity="P0",
        metrics={"asset_count": len(evidence["assets"]), "all_match": all_match},
    )
    return evidence


def _verify_camera_and_points(recorder: Recorder, labels: dict[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {"points": []}
    camera = labels.get("camera") or {}
    intrinsics = camera.get("intrinsics") or {}
    k = intrinsics.get("K")
    w2cv = camera.get("world_to_opencv_camera")
    w2bl = camera.get("world_to_blender_camera")
    if not _is_matrix(k, 3, 3) or not _is_matrix(w2cv, 4, 4):
        recorder.add("camera_matrices_present", "FAIL", "K or world_to_opencv_camera is missing/invalid.", severity="P0")
        return evidence
    recorder.add("camera_matrices_present", "PASS", "K and world_to_opencv_camera have valid dimensions.")

    rigid_bottom_error = _max_abs(_sub([float(v) for v in w2cv[3]], [0.0, 0.0, 0.0, 1.0]))
    rotation = [[float(w2cv[i][j]) for j in range(3)] for i in range(3)]
    rr_t = _mat_mul(rotation, [[rotation[j][i] for j in range(3)] for i in range(3)])
    orthogonality_error = _max_abs(
        [rr_t[i][j] - (1.0 if i == j else 0.0) for i in range(3) for j in range(3)]
    )
    recorder.add(
        "camera_rigid_transform",
        "PASS" if max(rigid_bottom_error, orthogonality_error) <= EPS_MATRIX else "FAIL",
        "world_to_opencv_camera is a rigid homogeneous transform.",
        metrics={"bottom_row_error": rigid_bottom_error, "rotation_orthogonality_error": orthogonality_error},
    )

    if _is_matrix(w2bl, 4, 4):
        axis_flip = [[1.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        expected_cv = _mat_mul(axis_flip, w2bl)
        convention_error = _max_abs(
            [expected_cv[i][j] - float(w2cv[i][j]) for i in range(4) for j in range(4)]
        )
        recorder.add(
            "blender_to_opencv_axis_convention",
            "PASS" if convention_error <= EPS_MATRIX else "FAIL",
            "OpenCV matrix equals diag(1,-1,-1,1) times Blender camera matrix.",
            metrics={"max_abs_error": convention_error},
        )
    else:
        recorder.add("blender_to_opencv_axis_convention", "SKIP", "world_to_blender_camera is absent.", severity="P2")

    width = int(intrinsics.get("width", 0))
    height = int(intrinsics.get("height", 0))
    fx = float(intrinsics.get("fx", 0.0))
    fy = float(intrinsics.get("fy", 0.0))
    cx = float(intrinsics.get("cx", 0.0))
    cy = float(intrinsics.get("cy", 0.0))
    k_field_error = _max_abs(
        [float(k[0][0]) - fx, float(k[1][1]) - fy, float(k[0][2]) - cx, float(k[1][2]) - cy]
    )
    intrinsics_ok = width > 0 and height > 0 and fx > 0 and fy > 0 and k_field_error <= EPS_MATRIX
    recorder.add(
        "intrinsics_consistency",
        "PASS" if intrinsics_ok else "FAIL",
        "K agrees with scalar intrinsics and image size is positive.",
        metrics={"width": width, "height": height, "k_field_error": k_field_error},
    )

    c2w = _invert_rigid4(w2cv)
    camera_origin = [c2w[i][3] for i in range(3)]
    all_points_ok = True
    for point in labels.get("points") or []:
        point_id = str(point.get("point_id", ""))
        world = [float(v) for v in point.get("xyz_world_blender_m", [])]
        stored_camera = [float(v) for v in point.get("xyz_camera_opencv_m", [])]
        stored_uv = [float(v) for v in point.get("uv_pixel_opencv", [])]
        bary = [float(v) for v in point.get("barycentric", [])]
        normal = [float(v) for v in point.get("world_normal", [])]
        valid_shape = all(len(value) == length for value, length in ((world, 3), (stored_camera, 3), (stored_uv, 2), (bary, 3), (normal, 3)))
        if not valid_shape:
            all_points_ok = False
            evidence["points"].append({"point_id": point_id, "valid": False, "reason": "invalid vector length"})
            continue
        camera_h = _mat_vec(w2cv, world + [1.0])
        camera_xyz = camera_h[:3]
        z = camera_xyz[2]
        projected_uv = [fx * camera_xyz[0] / z + cx, fy * camera_xyz[1] / z + cy] if z != 0.0 else [math.inf, math.inf]
        camera_error = _max_abs(_sub(camera_xyz, stored_camera))
        uv_error = _max_abs(_sub(projected_uv, stored_uv))
        bary_sum_error = abs(sum(bary) - 1.0)
        normal_norm_error = abs(_norm(normal) - 1.0)
        in_front = z > 0.0
        in_frame = in_front and 0.0 <= projected_uv[0] < width and 0.0 <= projected_uv[1] < height
        to_camera = [camera_origin[i] - world[i] for i in range(3)]
        front_facing = _dot(normal, to_camera) > 0.0
        booleans_match = (
            bool(point.get("in_front")) == in_front
            and bool(point.get("in_frame")) == in_frame
            and bool(point.get("front_facing")) == front_facing
        )
        point_ok = (
            camera_error <= EPS_XYZ_M
            and uv_error <= EPS_UV_PX
            and bary_sum_error <= EPS_BARY_SUM
            and normal_norm_error <= EPS_NORMAL
            and booleans_match
        )
        all_points_ok &= point_ok
        evidence["points"].append(
            {
                "point_id": point_id,
                "valid": point_ok,
                "recomputed_xyz_camera": camera_xyz,
                "recomputed_uv": projected_uv,
                "xyz_camera_max_abs_error_m": camera_error,
                "uv_max_abs_error_px": uv_error,
                "barycentric_sum_error": bary_sum_error,
                "normal_norm_error": normal_norm_error,
                "booleans_match": booleans_match,
            }
        )
    recorder.add(
        "independent_camera_projection",
        "PASS" if all_points_ok and bool(evidence["points"]) else "FAIL",
        "All points pass independent world-to-camera, projection, barycentric, normal and flag checks.",
        metrics={"point_count": len(evidence["points"]), "all_points_ok": all_points_ok},
    )
    evidence["camera_origin_world"] = camera_origin
    return evidence


def _verify_images_and_depth(
    recorder: Recorder,
    sample_dir: Path,
    labels: dict[str, Any],
    require_rgbd: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    evidence: dict[str, Any] = {}
    intrinsics = labels["camera"]["intrinsics"]
    width, height = int(intrinsics["width"]), int(intrinsics["height"])
    expected_hw = (height, width)

    rgb_path = sample_dir / "rgb.png"
    if not rgb_path.is_file():
        recorder.add("rgb_present", "FAIL", "rgb.png is missing.", severity="P0")
    else:
        with Image.open(rgb_path) as rgb:
            rgb_hw = (rgb.height, rgb.width)
            evidence["rgb"] = {"path": str(rgb_path), "sha256": _sha256(rgb_path), "height_width": rgb_hw}
        recorder.add(
            "rgb_alignment",
            "PASS" if rgb_hw == expected_hw else "FAIL",
            "RGB dimensions match camera intrinsics." if rgb_hw == expected_hw else "RGB dimensions differ from camera intrinsics.",
            severity="P0",
            metrics={"rgb_hw": rgb_hw, "expected_hw": expected_hw},
        )

    depth_path = sample_dir / "scene_depth_z.npy"
    skin_path = sample_dir / "skin_mask.png"
    valid_path = sample_dir / "depth_valid_mask.png"
    components = [depth_path.is_file(), skin_path.is_file(), valid_path.is_file()]
    if not any(components):
        status = "FAIL" if require_rgbd else "SKIP"
        recorder.add(
            "rgbd_present",
            status,
            "RGB-D verification requested but scene_depth_z.npy/skin_mask.png/depth_valid_mask.png are missing."
            if require_rgbd
            else "RGB-only sample: RGB-D checks are not applicable.",
            severity="P0" if require_rgbd else "P2",
        )
        recorder.capabilities["rgbd_semantics"] = "NOT_EVALUATED"
        return evidence, None
    if not all(components):
        recorder.add("rgbd_present", "FAIL", "RGB-D output is partial; all three files are mandatory.", severity="P0")
        recorder.capabilities["rgbd_semantics"] = "FAILED_PARTIAL_OUTPUT"
        return evidence, None

    buffers = labels.get("buffers")
    expected_buffers = {
        "scene_depth_z": {
            "file": "scene_depth_z.npy",
            "dtype": "float32",
            "unit": "m",
            "meaning": "OPENCV_CAMERA_Z_FIRST_VISIBLE_SCENE_SURFACE",
            "background_value": 0.0,
        },
        "depth_valid_mask": {
            "file": "depth_valid_mask.png",
            "dtype": "uint8",
            "values": [0, 255],
        },
        "skin_mask": {
            "file": "skin_mask.png",
            "dtype": "uint8",
            "meaning": "VISIBLE_SKEL_SKIN_FIRST_SURFACE",
            "values": [0, 255],
        },
    }
    contract_errors: list[str] = []
    if not isinstance(buffers, dict):
        contract_errors.append("labels.buffers missing or not an object")
    else:
        for buffer_name, expected in expected_buffers.items():
            declared = buffers.get(buffer_name)
            if not isinstance(declared, dict):
                contract_errors.append(f"buffers.{buffer_name} missing or not an object")
                continue
            for key, expected_value in expected.items():
                actual_value = declared.get(key)
                if key == "background_value":
                    try:
                        matches = float(actual_value) == float(expected_value)
                    except (TypeError, ValueError):
                        matches = False
                else:
                    matches = actual_value == expected_value
                if not matches:
                    contract_errors.append(
                        f"buffers.{buffer_name}.{key}: expected {expected_value!r}, got {actual_value!r}"
                    )
    recorder.add(
        "labels_buffers_contract",
        "PASS" if not contract_errors else "FAIL",
        "labels.buffers exactly declares the frozen depth/mask file and semantic contract.",
        severity="P0",
        metrics={"errors": contract_errors, "expected": expected_buffers},
    )

    depth_descriptor = _npy_descriptor(depth_path)
    depth_hw, depth = _read_npy_2d(depth_path)
    with Image.open(skin_path) as skin_image:
        skin_png_format = skin_image.format
        skin_png_mode = skin_image.mode
    with Image.open(valid_path) as valid_image:
        valid_png_format = valid_image.format
        valid_png_mode = valid_image.mode
    skin_hw, skin = _image_luma_bytes(skin_path)
    valid_hw, valid = _image_luma_bytes(valid_path)
    file_types_ok = (
        depth_descriptor in ("<f4", "=f4", "|f4")
        and skin_png_format == "PNG"
        and valid_png_format == "PNG"
        and skin_png_mode in ("L", "LA", "RGB", "RGBA")
        and valid_png_mode in ("L", "LA", "RGB", "RGBA")
    )
    recorder.add(
        "rgbd_file_types",
        "PASS" if file_types_ok else "FAIL",
        "Depth is float32 NPY and both masks are 8-bit PNG images.",
        severity="P0",
        metrics={
            "depth_npy_descriptor": depth_descriptor,
            "skin_png_format": skin_png_format,
            "skin_png_mode": skin_png_mode,
            "valid_png_format": valid_png_format,
            "valid_png_mode": valid_png_mode,
        },
    )
    aligned = depth_hw == skin_hw == valid_hw == expected_hw
    recorder.add(
        "rgb_depth_mask_alignment",
        "PASS" if aligned else "FAIL",
        "RGB, depth, valid mask and skin mask use the same frame dimensions.",
        severity="P0",
        metrics={"depth_hw": depth_hw, "skin_hw": skin_hw, "valid_hw": valid_hw, "expected_hw": expected_hw},
    )
    if not aligned:
        return evidence, None

    allowed_skin = set(skin).issubset({0, 255})
    allowed_valid = set(valid).issubset({0, 255})
    finite_nonnegative = all(math.isfinite(float(value)) and float(value) >= 0.0 for value in depth)
    invalid_nonzero = 0
    valid_nonpositive = 0
    skin_without_depth = 0
    for index, value in enumerate(depth):
        is_valid = valid[index] == 255
        is_skin = skin[index] == 255
        if not is_valid and abs(float(value)) > EPS_DEPTH_ZERO_M:
            invalid_nonzero += 1
        if is_valid and float(value) <= EPS_DEPTH_ZERO_M:
            valid_nonpositive += 1
        if is_skin and not is_valid:
            skin_without_depth += 1
    encoding_ok = (
        allowed_skin
        and allowed_valid
        and finite_nonnegative
        and invalid_nonzero == 0
        and valid_nonpositive == 0
        and skin_without_depth == 0
    )
    recorder.add(
        "depth_mask_encoding",
        "PASS" if encoding_ok else "FAIL",
        "Depth/mask background and validity encoding is internally consistent.",
        metrics={
            "skin_binary": allowed_skin,
            "valid_binary": allowed_valid,
            "depth_finite_nonnegative": finite_nonnegative,
            "invalid_nonzero_pixels": invalid_nonzero,
            "valid_nonpositive_pixels": valid_nonpositive,
            "skin_without_valid_depth_pixels": skin_without_depth,
        },
    )
    evidence["depth"] = {
        "path": str(depth_path),
        "sha256": _sha256(depth_path),
        "shape": depth_hw,
        "valid_count": sum(value == 255 for value in valid),
        "skin_count": sum(value == 255 for value in skin),
    }
    evidence["skin_mask"] = {"path": str(skin_path), "sha256": _sha256(skin_path)}
    evidence["depth_valid_mask"] = {"path": str(valid_path), "sha256": _sha256(valid_path)}

    def deterministic_indices(predicate: Any, limit: int = 32) -> list[int]:
        candidates = [index for index in range(len(depth)) if predicate(index)]
        if len(candidates) <= limit:
            return candidates
        return [candidates[round(i * (len(candidates) - 1) / (limit - 1))] for i in range(limit)]

    groups = {
        "skin": deterministic_indices(lambda i: skin[i] == 255 and valid[i] == 255),
        "non_skin_surface": deterministic_indices(lambda i: skin[i] == 0 and valid[i] == 255),
        "background": deterministic_indices(lambda i: valid[i] == 0),
    }
    requested: list[dict[str, Any]] = []
    seen: set[int] = set()
    for group, indices in groups.items():
        for index in indices:
            if index in seen:
                continue
            seen.add(index)
            row, column = divmod(index, width)
            requested.append(
                {
                    "group": group,
                    "row": row,
                    "column": column,
                    "u_center": column + 0.5,
                    "v_center": row + 0.5,
                    "depth_z_m": float(depth[index]),
                    "depth_valid": valid[index] == 255,
                    "skin_mask": skin[index] == 255,
                }
            )
    point_pixels: list[dict[str, Any]] = []
    for point in labels.get("points") or []:
        uv = point.get("uv_pixel_opencv") or []
        if len(uv) != 2:
            continue
        column = min(width - 1, max(0, int(math.floor(float(uv[0])))))
        row = min(height - 1, max(0, int(math.floor(float(uv[1])))))
        index = row * width + column
        point_pixels.append(
            {
                "point_id": point.get("point_id"),
                "row": row,
                "column": column,
                "depth_z_m": float(depth[index]),
                "depth_valid": valid[index] == 255,
                "skin_mask": skin[index] == 255,
                "point_zc_m": float((point.get("xyz_camera_opencv_m") or [0.0, 0.0, 0.0])[2]),
                "visible": bool(point.get("visible")),
                "visibility_reason": point.get("visibility_reason"),
                "expected_ray_hit_object": point.get("ray_hit_object"),
            }
        )
    request = {"pixels": requested, "point_pixels": point_pixels}
    evidence["ray_sample_groups"] = {name: len(indices) for name, indices in groups.items()}
    recorder.capabilities["rgbd_semantics"] = "READY_FOR_SCENE_RAY_VERIFICATION"
    return evidence, request


def _run_blender_probe(
    blender_exe: Path,
    scene_blend: Path,
    labels_path: Path,
    ray_request: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="acu_independent_verify_") as temp:
        temp_dir = Path(temp)
        output_path = temp_dir / "probe.json"
        request_path = temp_dir / "ray_request.json"
        request_path.write_text(json.dumps(ray_request or {}, ensure_ascii=False), encoding="utf-8")
        command = [
            str(blender_exe),
            "--background",
            str(scene_blend),
            "--python",
            str(DEFAULT_BLENDER_PROBE),
            "--",
            "--labels",
            str(labels_path),
            "--ray-request",
            str(request_path),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        process = {
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
        if completed.returncode != 0 or not output_path.is_file():
            raise RuntimeError(f"Blender probe failed: {process}")
        return _load_json(output_path), process


def _assess_scene_probe(recorder: Recorder, report: dict[str, Any], ray_request: dict[str, Any] | None) -> None:
    scene_ok = bool(report.get("scene_geometry_passed"))
    recorder.add(
        "blender_scene_geometry",
        "PASS" if scene_ok else "FAIL",
        "Reopened Blender scene independently reproduces topology, evaluated barycentric point, normal and ray visibility.",
        severity="P0",
        metrics=report.get("scene_geometry_summary") or {},
    )
    if ray_request is None:
        recorder.add("scene_depth_raycast", "SKIP", "No RGB-D buffers were present, so per-pixel ray/depth checks were skipped.", severity="P1")
        return
    probes = report.get("pixel_rays") or []
    mismatch_count = 0
    depth_errors: list[float] = []
    backprojection_errors: list[float] = []
    non_target_surface_samples = 0
    background_samples = 0
    target_name = str(report.get("target_object", ""))
    for probe in probes:
        source = probe.get("request") or {}
        hit = bool(probe.get("hit")) and float(probe.get("hit_zc_m", -1.0)) > 0.0
        expected_valid = bool(source.get("depth_valid"))
        expected_skin = bool(source.get("skin_mask"))
        stored_depth = float(source.get("depth_z_m", 0.0))
        if hit:
            error = abs(stored_depth - float(probe["hit_zc_m"]))
            depth_errors.append(error)
            tolerance = max(DEPTH_RAY_ABS_TOL_M, DEPTH_RAY_REL_TOL * float(probe["hit_zc_m"]))
            intrinsics = report.get("camera_intrinsics") or {}
            fx, fy = float(intrinsics.get("fx", 0.0)), float(intrinsics.get("fy", 0.0))
            cx, cy = float(intrinsics.get("cx", 0.0)), float(intrinsics.get("cy", 0.0))
            u_center, v_center = float(source["u_center"]), float(source["v_center"])
            backprojected = [
                (u_center - cx) * stored_depth / fx if fx else math.inf,
                (v_center - cy) * stored_depth / fy if fy else math.inf,
                stored_depth,
            ]
            hit_camera = [float(value) for value in probe.get("hit_camera_xyz", [])]
            backprojection_error = (
                max(abs(backprojected[i] - hit_camera[i]) for i in range(3))
                if len(hit_camera) == 3
                else math.inf
            )
            backprojection_errors.append(backprojection_error)
            correct_depth = expected_valid and error <= tolerance and backprojection_error <= tolerance
            correct_skin = expected_skin == (str(probe.get("hit_object")) == target_name)
            if str(probe.get("hit_object")) != target_name:
                non_target_surface_samples += 1
            if not (correct_depth and correct_skin):
                mismatch_count += 1
        else:
            background_samples += 1
            if expected_valid or expected_skin or abs(stored_depth) > EPS_DEPTH_ZERO_M:
                mismatch_count += 1
    recorder.add(
        "scene_depth_raycast",
        "PASS" if probes and mismatch_count == 0 else "FAIL",
        "Stored scene Z-depth and visible-skin mask agree with independent scene.ray_cast samples.",
        severity="P0",
        metrics={
            "probe_count": len(probes),
            "mismatch_count": mismatch_count,
            "max_depth_error_m": max(depth_errors, default=0.0),
            "max_backprojection_error_m": max(backprojection_errors, default=0.0),
            "non_target_surface_hit_samples": non_target_surface_samples,
            "background_ray_samples": background_samples,
        },
    )

    point_results = report.get("point_pixel_rays") or []
    point_mismatches = 0
    assessed_points = 0
    verified_external_occluders = 0
    for result in point_results:
        source = result.get("request") or {}
        if source.get("visible"):
            assessed_points += 1
            if not source.get("depth_valid") or not source.get("skin_mask"):
                point_mismatches += 1
            elif abs(float(source.get("depth_z_m", 0.0)) - float(source.get("point_zc_m", 0.0))) > POINT_PIXEL_DEPTH_TOL_M:
                point_mismatches += 1
            elif not result.get("hit") or str(result.get("hit_object")) != target_name:
                point_mismatches += 1
        elif source.get("visibility_reason") == "EXTERNAL_OCCLUDED":
            assessed_points += 1
            independent_hit_ok = (
                bool(result.get("hit"))
                and str(result.get("hit_object")) == str(source.get("expected_ray_hit_object"))
                and str(result.get("hit_object")) != target_name
                and float(result.get("hit_zc_m", math.inf)) < float(source.get("point_zc_m", -math.inf))
                and abs(float(source.get("depth_z_m", 0.0)) - float(result.get("hit_zc_m", math.inf)))
                <= max(DEPTH_RAY_ABS_TOL_M, DEPTH_RAY_REL_TOL * float(result.get("hit_zc_m", 0.0)))
            )
            if not source.get("depth_valid") or source.get("skin_mask"):
                point_mismatches += 1
            elif float(source.get("depth_z_m", math.inf)) >= float(source.get("point_zc_m", -math.inf)):
                point_mismatches += 1
            elif not independent_hit_ok:
                point_mismatches += 1
            else:
                verified_external_occluders += 1
    recorder.add(
        "point_depth_semantics",
        "PASS" if assessed_points and point_mismatches == 0 else ("FAIL" if assessed_points else "SKIP"),
        "Visible/external-occluded point pixels follow the declared depth and mask semantics.",
        severity="P1",
        metrics={"point_pixel_count": len(point_results), "assessed_point_count": assessed_points, "mismatch_count": point_mismatches, "tolerance_m": POINT_PIXEL_DEPTH_TOL_M},
    )
    if verified_external_occluders:
        recorder.add(
            "external_occlusion_exercised",
            "PASS",
            "An EXTERNAL_OCCLUDED point was independently confirmed against its named foreground object, Z-depth and skin-mask semantics.",
            metrics={"verified_point_count": verified_external_occluders},
        )
    else:
        recorder.add(
            "external_occlusion_exercised",
            "SKIP",
            "No EXTERNAL_OCCLUDED labelled point was independently confirmed; generic bed/bone/non-target rays do not prove the external-occluder branch.",
            severity="P1",
        )


def _compare_samples(
    recorder: Recorder,
    sample_dir: Path,
    other_path: Path,
    require_rgbd: bool,
) -> dict[str, Any]:
    other_dir, other_labels_path = _locate_sample(other_path)
    labels_a = _load_json(sample_dir / "labels.json")
    labels_b = _load_json(other_labels_path)
    volatile = {"created_at", "source_blend", "source_blend_dirty"}

    def normalized(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: normalized(child) for key, child in value.items() if key not in volatile}
        if isinstance(value, list):
            return [normalized(child) for child in value]
        return value

    labels_equal = normalized(labels_a) == normalized(labels_b)
    rgb_a, rgb_b = sample_dir / "rgb.png", other_dir / "rgb.png"
    rgb_pixels_equal = False
    if rgb_a.is_file() and rgb_b.is_file():
        with Image.open(rgb_a) as image_a, Image.open(rgb_b) as image_b:
            rgb_pixels_equal = image_a.size == image_b.size and ImageChops.difference(image_a.convert("RGBA"), image_b.convert("RGBA")).getbbox() is None
    rgbd_equal: bool | None = None
    rgbd_metrics: dict[str, Any] = {}
    rgbd_names = ("scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png")
    rgbd_present_a = all((sample_dir / name).is_file() for name in rgbd_names)
    rgbd_present_b = all((other_dir / name).is_file() for name in rgbd_names)
    if rgbd_present_a and rgbd_present_b:
        shape_a, depth_a = _read_npy_2d(sample_dir / "scene_depth_z.npy")
        shape_b, depth_b = _read_npy_2d(other_dir / "scene_depth_z.npy")
        descriptor_a = _npy_descriptor(sample_dir / "scene_depth_z.npy")
        descriptor_b = _npy_descriptor(other_dir / "scene_depth_z.npy")
        depth_element_equal = shape_a == shape_b and descriptor_a == descriptor_b and len(depth_a) == len(depth_b) and all(float(a) == float(b) for a, b in zip(depth_a, depth_b))
        max_depth_difference = max((abs(float(a) - float(b)) for a, b in zip(depth_a, depth_b)), default=0.0) if shape_a == shape_b else math.inf
        valid_shape_a, valid_a = _image_luma_bytes(sample_dir / "depth_valid_mask.png")
        valid_shape_b, valid_b = _image_luma_bytes(other_dir / "depth_valid_mask.png")
        skin_shape_a, skin_a = _image_luma_bytes(sample_dir / "skin_mask.png")
        skin_shape_b, skin_b = _image_luma_bytes(other_dir / "skin_mask.png")
        valid_pixels_equal = valid_shape_a == valid_shape_b and valid_a == valid_b
        skin_pixels_equal = skin_shape_a == skin_shape_b and skin_a == skin_b
        rgbd_equal = depth_element_equal and valid_pixels_equal and skin_pixels_equal
        rgbd_metrics = {
            "depth_shape_equal": shape_a == shape_b,
            "depth_dtype_equal": descriptor_a == descriptor_b,
            "depth_element_equal": depth_element_equal,
            "max_depth_difference_m": max_depth_difference,
            "depth_valid_mask_pixels_equal": valid_pixels_equal,
            "skin_mask_pixels_equal": skin_pixels_equal,
        }
    elif require_rgbd:
        rgbd_equal = False
        rgbd_metrics = {"first_rgbd_complete": rgbd_present_a, "second_rgbd_complete": rgbd_present_b}
    comparison_ok = labels_equal and rgb_pixels_equal and (rgbd_equal is not False)
    recorder.add(
        "reexport_consistency",
        "PASS" if comparison_ok else "FAIL",
        "Two independently supplied exports match after removing explicitly volatile fields; RGB-D arrays/masks are compared element-for-element when required.",
        metrics={"labels_equal": labels_equal, "rgb_pixels_equal": rgb_pixels_equal, "rgbd_equal": rgbd_equal, **rgbd_metrics},
    )
    return {"other_sample": str(other_dir), "labels_equal": labels_equal, "rgb_pixels_equal": rgb_pixels_equal, "rgbd_equal": rgbd_equal, **rgbd_metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent verifier for SKEL RGB/RGB-D training samples")
    parser.add_argument("--sample", required=True, type=Path, help="Delivery root or sample directory")
    parser.add_argument("--scene-blend", type=Path, help="Exact frozen scene snapshot or canonical Blend for scene probing")
    parser.add_argument("--blender-exe", type=Path, help="Portable Blender executable")
    parser.add_argument("--protected-manifest", type=Path, default=DEFAULT_PROTECTED_MANIFEST)
    parser.add_argument("--compare-sample", type=Path, help="Second export for reopen/re-export consistency")
    parser.add_argument("--require-rgbd", action="store_true", help="Fail if RGB-D buffers are absent")
    parser.add_argument("--output", required=True, type=Path, help="Verification report JSON path")
    args = parser.parse_args()

    recorder = Recorder()
    sample_dir, labels_path = _locate_sample(args.sample)
    labels = _load_json(labels_path)
    report: dict[str, Any] = {
        "schema": "independent-skel-sample-verification-v1",
        "created_at": _utc_now(),
        "independence_statement": "Does not import or call generator, MCP bridge, or annotation add-on functions.",
        "sample_dir": str(sample_dir),
        "labels_path": str(labels_path),
        "labels_sha256": _sha256(labels_path),
        "thresholds": {
            "matrix_max_abs": EPS_MATRIX,
            "xyz_m": EPS_XYZ_M,
            "uv_px": EPS_UV_PX,
            "barycentric_sum": EPS_BARY_SUM,
            "normal_norm": EPS_NORMAL,
            "depth_zero_m": EPS_DEPTH_ZERO_M,
            "depth_ray_abs_m": DEPTH_RAY_ABS_TOL_M,
            "depth_ray_relative": DEPTH_RAY_REL_TOL,
            "point_pixel_depth_m": POINT_PIXEL_DEPTH_TOL_M,
        },
    }
    report["protected_assets"] = _protected_checks(recorder, args.protected_manifest.resolve())
    report["camera_and_points"] = _verify_camera_and_points(recorder, labels)
    image_evidence, ray_request = _verify_images_and_depth(recorder, sample_dir, labels, args.require_rgbd)
    report["images_and_depth"] = image_evidence

    if args.scene_blend and args.blender_exe:
        if not args.scene_blend.is_file() or not args.blender_exe.is_file():
            recorder.add("scene_probe_available", "FAIL", "Blender executable or scene Blend does not exist.", severity="P0")
        else:
            scene_hash = _sha256(args.scene_blend.resolve())
            declared_scene_hash = str(
                labels.get("source_scene_snapshot_sha256")
                or (labels.get("scene") or {}).get("snapshot_sha256")
                or ""
            ).lower()
            if declared_scene_hash:
                recorder.add(
                    "scene_snapshot_identity",
                    "PASS" if scene_hash == declared_scene_hash else "FAIL",
                    "Provided scene Blend matches the sample-declared frozen snapshot hash.",
                    severity="P0",
                    metrics={"declared_sha256": declared_scene_hash, "actual_sha256": scene_hash},
                )
            else:
                recorder.add(
                    "scene_snapshot_identity",
                    "FAIL" if args.require_rgbd else "SKIP",
                    "The sample does not declare a frozen scene snapshot SHA-256. Exact replay of rendered occluders cannot be proven."
                    if not args.require_rgbd
                    else "Full RGB-D verification requires source_scene_snapshot_sha256 (or scene.snapshot_sha256).",
                    severity="P0" if args.require_rgbd else "P1",
                )
            first, first_process = _run_blender_probe(args.blender_exe.resolve(), args.scene_blend.resolve(), labels_path, ray_request)
            second, second_process = _run_blender_probe(args.blender_exe.resolve(), args.scene_blend.resolve(), labels_path, ray_request)
            _assess_scene_probe(recorder, first, ray_request)
            deterministic = first == second
            recorder.add(
                "scene_reopen_determinism",
                "PASS" if deterministic else "FAIL",
                "Two fresh Blender processes produced identical independent geometry/ray reports.",
                severity="P1",
            )
            report["blender_scene_probe"] = {
                "scene_blend": str(args.scene_blend.resolve()),
                "scene_blend_sha256": scene_hash,
                "first": first,
                "second_equal": deterministic,
                "processes": [first_process, second_process],
            }
    else:
        recorder.add(
            "scene_probe_available",
            "SKIP",
            "Both --scene-blend and --blender-exe are required for evaluated-mesh and scene.ray_cast verification.",
            severity="P1",
        )

    if args.compare_sample:
        report["sample_comparison"] = _compare_samples(recorder, sample_dir, args.compare_sample, args.require_rgbd)
    else:
        recorder.add(
            "reexport_consistency",
            "SKIP",
            "No independent second exported sample was supplied; generator re-export consistency was not evaluated.",
            severity="P1",
        )

    report["capabilities"] = recorder.capabilities
    report["checks"] = recorder.checks
    report["passed"] = recorder.passed()
    report["summary"] = {
        "pass": sum(check["status"] == "PASS" for check in recorder.checks),
        "fail": sum(check["status"] == "FAIL" for check in recorder.checks),
        "skip": sum(check["status"] == "SKIP" for check in recorder.checks),
        "warn": sum(check["status"] == "WARN" for check in recorder.checks),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "summary": report["summary"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
