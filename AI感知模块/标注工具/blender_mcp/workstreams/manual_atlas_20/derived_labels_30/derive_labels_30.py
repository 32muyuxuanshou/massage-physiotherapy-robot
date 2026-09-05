#!/usr/bin/env python3
"""Derive labels/overlays for the frozen 30 snapshots from a schema-v5 Atlas.

Existing RGB, Depth, masks, snapshots and parent metadata are immutable inputs.
Every snapshot is opened in a fresh background Blender process; only point
surface bindings, projection and visibility are recomputed.
"""

from __future__ import annotations

import argparse
import array
import ast
import hashlib
import json
import math
import os
import shutil
import subprocess
import struct
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


WORKSTREAM = Path(__file__).resolve().parent
AI_ROOT = Path(__file__).resolve().parents[5]
CORE_PARENT = AI_ROOT / "标注工具" / "blender_addons" / "modules"
BLENDER_SIDE = WORKSTREAM / "recompute_snapshot_labels.py"
DEFAULT_PARENT = AI_ROOT / "outputs" / "交付文件" / "2026-08-28_20-21-54"
DEFAULT_BLENDER = (
    AI_ROOT
    / "发布"
    / "医生穴位标注工作台_v2.3.0_完整版"
    / "医生穴位标注工作台_v2.3.0_完整版"
    / "runtime"
    / "blender"
    / "blender.exe"
)
DEFAULT_USER_RESOURCES = DEFAULT_BLENDER.parents[2] / "user_resources"
EXPECTED_MODEL = {
    "family": "SKEL",
    "gender": "female",
    "template_id": "skel-female-trunk-limb-v2.3",
    "object_name": "SKEL-skin-female",
    "vertex_count": 6890,
    "polygon_count": 13776,
    "topology_signature_sha256": "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733",
}
REUSED_ASSETS = (
    "rgb.png",
    "scene_depth_z.npy",
    "depth_valid_mask.png",
    "skin_mask.png",
    "render_metadata.json",
)
ALLOWED_VISIBILITY = {
    "VISIBLE",
    "OUT_OF_FRAME",
    "BEHIND_CAMERA",
    "BACK_FACING",
    "SELF_OCCLUDED",
    "EXTERNAL_OCCLUDED",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--parent-delivery", type=Path, default=DEFAULT_PARENT)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blender-exe", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--asset-mode", choices=("auto", "hardlink", "copy"), default="auto")
    parser.add_argument(
        "--supersedes",
        type=Path,
        help="Optional earlier derived delivery retained in place but declared superseded by this run.",
    )
    parser.add_argument(
        "--truth-status",
        choices=("engineering_reference", "doctor_confirmed"),
        default="engineering_reference",
    )
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate all immutable inputs without creating output or launching Blender.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_template_id(value: str) -> str:
    return str(value).strip().lower().replace("_", "-")


def validate_atlas(path: Path) -> tuple[dict, list[dict]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = read_json(path)
    if payload.get("schema_version") != "smpl-acupoint-annotation-v5":
        raise ValueError("Atlas must use schema_version smpl-acupoint-annotation-v5")
    model = payload.get("model") or {}
    for key in ("family", "gender"):
        if str(model.get(key, "")).lower() != str(EXPECTED_MODEL[key]).lower():
            raise ValueError(f"Atlas model {key} mismatch: {model.get(key)!r}")
    if normalize_template_id(model.get("template_id", "")) != normalize_template_id(EXPECTED_MODEL["template_id"]):
        raise ValueError(f"Atlas template_id mismatch: {model.get('template_id')!r}")
    for key in ("vertex_count", "polygon_count"):
        if int(model.get(key, -1)) != EXPECTED_MODEL[key]:
            raise ValueError(f"Atlas model {key} mismatch: {model.get(key)!r}")
    if str(model.get("topology_signature_sha256", "")).lower() != EXPECTED_MODEL["topology_signature_sha256"]:
        raise ValueError("Atlas topology signature does not match frozen female SKEL")

    annotations = payload.get("annotations")
    if not isinstance(annotations, list) or len(annotations) != 20:
        raise ValueError("Atlas must contain exactly 20 annotations")
    point_ids: set[str] = set()
    code_sides: set[tuple[str, str]] = set()
    annotation_ids: set[str] = set()
    for index, annotation in enumerate(annotations):
        label = f"annotations[{index}]"
        point_id = str(annotation.get("point_id", "")).strip()
        code = str(annotation.get("code", "")).strip()
        side = str(annotation.get("side", "")).strip().upper()
        annotation_id = str(annotation.get("id", "")).strip()
        if not point_id or point_id in point_ids:
            raise ValueError(f"{label} has missing/duplicate point_id {point_id!r}")
        if not code or (code, side) in code_sides:
            raise ValueError(f"{label} has missing/duplicate code+side {(code, side)!r}")
        if not annotation_id or annotation_id in annotation_ids:
            raise ValueError(f"{label} has missing/duplicate id {annotation_id!r}")
        point_ids.add(point_id)
        code_sides.add((code, side))
        annotation_ids.add(annotation_id)
        if side not in {"MIDLINE", "LEFT", "RIGHT"}:
            raise ValueError(f"{label} invalid side: {side!r}")
        if str(annotation.get("target_mesh", EXPECTED_MODEL["object_name"])) != EXPECTED_MODEL["object_name"]:
            raise ValueError(f"{label} targets a different mesh")
        face_index = int(annotation.get("face_index", -1))
        if not 0 <= face_index < EXPECTED_MODEL["polygon_count"]:
            raise ValueError(f"{label} face_index outside frozen topology")
        vertices = annotation.get("vertex_indices")
        if not isinstance(vertices, list) or len(vertices) != 3 or len(set(map(int, vertices))) != 3:
            raise ValueError(f"{label} must contain three distinct vertex_indices")
        if any(not 0 <= int(value) < EXPECTED_MODEL["vertex_count"] for value in vertices):
            raise ValueError(f"{label} vertex index outside frozen topology")
        bary = annotation.get("barycentric")
        if not isinstance(bary, list) or len(bary) != 3:
            raise ValueError(f"{label} barycentric must contain three values")
        weights = [float(value) for value in bary]
        if not all(math.isfinite(value) and -1e-7 <= value <= 1.0 + 1e-7 for value in weights):
            raise ValueError(f"{label} invalid barycentric weights")
        if not math.isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-4):
            raise ValueError(f"{label} barycentric sum is not one")
    return payload, annotations


def validate_parent(parent: Path) -> tuple[list[dict], dict[str, dict[str, dict]]]:
    parent = parent.resolve()
    index_path = parent / "dataset_index.json"
    if not index_path.is_file():
        raise FileNotFoundError(index_path)
    index = read_json(index_path)
    if not isinstance(index, list) or len(index) != 30:
        raise ValueError("Parent delivery must contain exactly 30 indexed snapshots")
    seen_samples: set[str] = set()
    inventory: dict[str, dict[str, dict]] = {}
    for entry in index:
        sample_id = str(entry.get("sample_id", ""))
        if not sample_id or sample_id in seen_samples:
            raise ValueError(f"duplicate/missing parent sample_id: {sample_id!r}")
        seen_samples.add(sample_id)
        snapshot = parent / entry["snapshot"]
        sample = parent / "samples" / sample_id
        if not snapshot.is_file() or sha256(snapshot) != entry.get("snapshot_sha256"):
            raise ValueError(f"parent snapshot hash mismatch: {sample_id}")
        parent_labels = sample / "labels.json"
        if not parent_labels.is_file():
            raise FileNotFoundError(parent_labels)
        labels = read_json(parent_labels)
        model = labels.get("model") or {}
        for key in ("family", "gender", "object_name", "vertex_count", "polygon_count", "topology_signature_sha256"):
            expected = EXPECTED_MODEL[key]
            actual = model.get(key)
            if str(actual).lower() != str(expected).lower():
                raise ValueError(f"parent {sample_id} model {key} mismatch: {actual!r}")
        sample_inventory: dict[str, dict] = {
            "parent_labels.json": {
                "source_path": str(parent_labels),
                "size_bytes": parent_labels.stat().st_size,
                "sha256": sha256(parent_labels),
            }
        }
        for name in REUSED_ASSETS:
            source = sample / name
            if not source.is_file():
                raise FileNotFoundError(source)
            sample_inventory[name] = {
                "source_path": str(source),
                "size_bytes": source.stat().st_size,
                "sha256": sha256(source),
            }
        inventory[sample_id] = sample_inventory
    return index, inventory


def reuse_asset(source: Path, destination: Path, mode: str) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    if mode in {"auto", "hardlink"}:
        try:
            os.link(source, destination)
            return "hardlink"
        except OSError:
            if mode == "hardlink":
                raise
    shutil.copy2(source, destination)
    return "copy"


def blender_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "BLENDER_USER_RESOURCES": str(DEFAULT_USER_RESOURCES),
            "ACUPOINT_MCP_PROJECT_ROOT": str(AI_ROOT),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return environment


def run_blender(
    blender: Path,
    snapshot: Path,
    atlas: Path,
    parent_sample: Path,
    output_sample: Path,
    result: Path,
    truth_status: str,
    timeout: int,
) -> dict:
    command = [
        str(blender),
        "--background",
        str(snapshot),
        "--python",
        str(BLENDER_SIDE),
        "--",
        "--atlas",
        str(atlas),
        "--parent-labels",
        str(parent_sample / "labels.json"),
        "--render-metadata",
        str(parent_sample / "render_metadata.json"),
        "--output-labels",
        str(output_sample / "labels.json"),
        "--result",
        str(result),
        "--core-parent",
        str(CORE_PARENT),
        "--truth-status",
        truth_status,
    ]
    completed = subprocess.run(
        command,
        cwd=str(WORKSTREAM),
        env=blender_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    combined = completed.stdout + "\n" + completed.stderr
    if completed.returncode != 0 or "ACU_DERIVE_LABELS_ONLY=PASS" not in combined:
        raise RuntimeError(combined[-16000:])
    return read_json(result)


def make_overlay(rgb_path: Path, labels_path: Path, output_path: Path) -> None:
    labels = read_json(labels_path)
    with Image.open(rgb_path) as source:
        canvas = source.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    font_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc"
    try:
        font = ImageFont.truetype(str(font_path), 16) if font_path.is_file() else ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()
    for point in labels["points"]:
        uv = point["uv_pixel_opencv"]
        if not point["in_frame"] or not all(math.isfinite(float(value)) for value in uv):
            continue
        x, y = map(float, uv)
        visible = bool(point["visible"])
        color = (32, 220, 92, 255) if visible else (245, 72, 72, 255)
        radius = 6
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline="white", width=2)
        label = str(point.get("code") or point["point_id"])
        draw.text((x + 9, y - 10), label, fill="white", font=font, stroke_width=2, stroke_fill=(0, 0, 0, 220))
    canvas.convert("RGB").save(output_path, format="PNG")


def read_float32_npy_2d(path: Path) -> tuple[int, int, array.array]:
    """Read the fixed little-endian C-order float32 depth contract without NumPy."""
    with path.open("rb") as handle:
        if handle.read(6) != b"\x93NUMPY":
            raise ValueError(f"not an NPY file: {path}")
        major, _minor = handle.read(2)
        header_length_size = 2 if major == 1 else 4
        header_length = struct.unpack(
            "<H" if major == 1 else "<I", handle.read(header_length_size)
        )[0]
        header = ast.literal_eval(handle.read(header_length).decode("latin1"))
        if header.get("descr") != "<f4" or header.get("fortran_order"):
            raise ValueError("Depth must be little-endian C-order float32")
        shape = header.get("shape")
        if not isinstance(shape, tuple) or len(shape) != 2:
            raise ValueError("Depth must be a two-dimensional NPY array")
        height, width = map(int, shape)
        values = array.array("f")
        values.frombytes(handle.read())
        if sys.byteorder != "little":
            values.byteswap()
        if len(values) != height * width:
            raise ValueError("Depth payload size mismatch")
        return height, width, values


def qc_sample(sample: Path, annotations: list[dict], thresholds: dict) -> dict:
    labels = read_json(sample / "labels.json")
    points = labels.get("points") or []
    height, width, depth = read_float32_npy_2d(sample / "scene_depth_z.npy")
    with Image.open(sample / "depth_valid_mask.png") as image:
        valid_image = image.convert("L").copy()
    with Image.open(sample / "skin_mask.png") as image:
        skin_image = image.convert("L").copy()
    checks = {
        "point_count_20": len(points) == 20,
        "resolution_alignment": valid_image.size == (width, height) == skin_image.size,
        "atlas_binding_order": len(points) == len(annotations),
        "visibility_contract": True,
        "visible_depth_contract": True,
    }
    details = []
    max_z_error = 0.0
    max_xyz_error = 0.0
    intrinsics = labels["camera"]["intrinsics"]
    z_limit = float(thresholds.get("visible_point_depth_error_m", 0.003))
    xyz_limit = float(thresholds.get("visible_point_backprojection_error_m", 0.003))
    for index, (point, annotation) in enumerate(zip(points, annotations)):
        binding_ok = all(
            point.get(key) == annotation.get(key)
            for key in ("point_id", "face_index", "vertex_indices", "barycentric", "side")
        )
        reason = point.get("visibility_reason")
        visible = bool(point.get("visible"))
        visibility_ok = reason in ALLOWED_VISIBILITY and visible == (reason == "VISIBLE")
        if visible:
            visibility_ok = visibility_ok and all(
                bool(point.get(key)) for key in ("in_front", "in_frame", "front_facing")
            )
            visibility_ok = visibility_ok and point.get("ray_hit_object") == EXPECTED_MODEL["object_name"]
        uv = [float(value) for value in point["uv_pixel_opencv"]]
        finite_uv = all(math.isfinite(value) for value in uv)
        depth_ok = True
        z_error = None
        xyz_error = None
        pixel = None
        if visible:
            col, row = int(uv[0]), int(uv[1])
            pixel = [col, row]
            if not finite_uv or not (0 <= col < width and 0 <= row < height):
                depth_ok = False
            else:
                observed = float(depth[row * width + col])
                xyz = [float(value) for value in point["xyz_camera_opencv_m"]]
                lifted = [
                    (uv[0] - float(intrinsics["cx"])) * observed / float(intrinsics["fx"]),
                    (uv[1] - float(intrinsics["cy"])) * observed / float(intrinsics["fy"]),
                    observed,
                ]
                z_error = abs(observed - xyz[2])
                xyz_error = math.dist(lifted, xyz)
                max_z_error = max(max_z_error, z_error)
                max_xyz_error = max(max_xyz_error, xyz_error)
                depth_ok = (
                    observed > 0.0
                    and valid_image.getpixel((col, row)) == 255
                    and skin_image.getpixel((col, row)) == 255
                    and z_error <= z_limit
                    and xyz_error <= xyz_limit
                )
        checks["atlas_binding_order"] &= binding_ok
        checks["visibility_contract"] &= visibility_ok
        checks["visible_depth_contract"] &= depth_ok
        details.append(
            {
                "point_id": point.get("point_id"),
                "visible": visible,
                "visibility_reason": reason,
                "pixel_col_row": pixel,
                "binding_ok": binding_ok,
                "visibility_ok": visibility_ok,
                "visible_depth_ok": depth_ok,
                "depth_error_m": z_error,
                "backprojection_error_m": xyz_error,
            }
        )
    passed = all(checks.values())
    return {
        "passed": bool(passed),
        "checks": checks,
        "point_count": len(points),
        "visible_count": sum(bool(point.get("visible")) for point in points),
        "visibility_reason_counts": dict(Counter(point.get("visibility_reason") for point in points)),
        "max_visible_point_depth_error_m": max_z_error,
        "max_visible_point_backprojection_error_m": max_xyz_error,
        "thresholds_m": {"depth": z_limit, "backprojection": xyz_limit},
        "points": details,
        "note": "Depth/backprojection checks apply only to actually visible points; invisible branches are retained and validated, not forced to pass as visible.",
    }


def write_manifest(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    args = arguments()
    atlas_path = args.atlas.resolve()
    parent = args.parent_delivery.resolve()
    output = args.output.resolve()
    supersedes = args.supersedes.resolve() if args.supersedes else None
    if not BLENDER_SIDE.is_file() or not CORE_PARENT.is_dir():
        raise FileNotFoundError("label-only implementation or training_export_core is missing")
    atlas, annotations = validate_atlas(atlas_path)
    atlas_input_sha256 = sha256(atlas_path)
    index, parent_inventory = validate_parent(parent)
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "passed": True,
                    "atlas_sha256": atlas_input_sha256,
                    "point_count": len(annotations),
                    "parent_delivery": str(parent),
                    "parent_sample_count": len(index),
                    "output_created": False,
                },
                ensure_ascii=False,
            )
        )
        return
    blender = args.blender_exe.resolve()
    if not blender.is_file():
        raise FileNotFoundError(blender)
    if output.exists():
        raise FileExistsError(f"output must be a new directory: {output}")
    if output == parent or parent in output.parents:
        raise ValueError("output must not equal or be nested inside the immutable parent delivery")
    if supersedes is not None:
        if not supersedes.is_dir():
            raise FileNotFoundError(f"superseded delivery does not exist: {supersedes}")
        if supersedes == output:
            raise ValueError("superseded delivery cannot be the new output")
    output.mkdir(parents=True, exist_ok=False)
    (output / "samples").mkdir()
    (output / "qc_reports").mkdir()
    (output / "blender_results").mkdir()
    frozen_atlas = output / "source_atlas_v5.json"
    shutil.copy2(atlas_path, frozen_atlas)
    if sha256(frozen_atlas) != atlas_input_sha256:
        raise ValueError("frozen Atlas copy hash mismatch")

    config_path = parent / "dataset_config_v1.json"
    thresholds = read_json(config_path).get("qc_thresholds", {}) if config_path.is_file() else {}
    derived_index = []
    aggregate_reasons: Counter[str] = Counter()
    try:
        for number, entry in enumerate(index, start=1):
            sample_id = entry["sample_id"]
            parent_sample = parent / "samples" / sample_id
            snapshot = parent / entry["snapshot"]
            output_sample = output / "samples" / sample_id
            output_sample.mkdir()
            reused = {}
            for name in REUSED_ASSETS:
                source = parent_sample / name
                destination = output_sample / name
                used_mode = reuse_asset(source, destination, args.asset_mode)
                actual_hash = sha256(destination)
                expected_hash = parent_inventory[sample_id][name]["sha256"]
                if actual_hash != expected_hash:
                    raise ValueError(f"reused asset changed during transfer: {sample_id}/{name}")
                reused[name] = {
                    **parent_inventory[sample_id][name],
                    "reuse_mode": used_mode,
                    "derived_path": str(destination.relative_to(output)),
                    "derived_sha256": actual_hash,
                }
            result_path = output / "blender_results" / f"{sample_id}.json"
            blender_result = run_blender(
                blender,
                snapshot,
                frozen_atlas,
                parent_sample,
                output_sample,
                result_path,
                args.truth_status,
                args.timeout_seconds,
            )
            if sha256(snapshot) != entry["snapshot_sha256"]:
                raise ValueError(f"snapshot was modified: {sample_id}")
            for name in REUSED_ASSETS:
                if sha256(parent_sample / name) != parent_inventory[sample_id][name]["sha256"]:
                    raise ValueError(f"parent asset was modified: {sample_id}/{name}")
            make_overlay(output_sample / "rgb.png", output_sample / "labels.json", output_sample / "overlay.png")
            qc = qc_sample(output_sample, annotations, thresholds)
            write_json(output / "qc_reports" / f"{sample_id}.json", qc)
            aggregate_reasons.update(qc["visibility_reason_counts"])
            derived_entry = {
                **entry,
                "parent_delivery": str(parent),
                "parent_sample": str(parent_sample),
                "parent_labels_sha256": parent_inventory[sample_id]["parent_labels.json"]["sha256"],
                "source_snapshot_sha256_after": sha256(snapshot),
                "reused_assets": reused,
                "derived_labels": str((output_sample / "labels.json").relative_to(output)),
                "derived_labels_sha256": sha256(output_sample / "labels.json"),
                "derived_overlay": str((output_sample / "overlay.png").relative_to(output)),
                "derived_overlay_sha256": sha256(output_sample / "overlay.png"),
                "blender_result": blender_result,
                "qc": {key: value for key, value in qc.items() if key != "points"},
                "passed": bool(qc["passed"]),
            }
            derived_index.append(derived_entry)
            write_json(output / "derived_dataset_index.json", derived_index)
            print(
                f"DERIVED {number:02d}/30 {entry['case']}: "
                f"{'PASS' if qc['passed'] else 'FAIL'} visible={qc['visible_count']}/20",
                flush=True,
            )

        # A final immutable-input pass catches any accidental writes after earlier checks.
        _index_after, parent_after = validate_parent(parent)
        parent_unchanged = parent_after == parent_inventory
        atlas_input_unchanged = sha256(atlas_path) == atlas_input_sha256
        sample_passes = [bool(item["passed"]) for item in derived_index]
        report = {
            "schema": "atlas-v5-derived-labels-30-qc-v1",
            "created_at": utc_now(),
            "passed": (
                len(derived_index) == 30
                and all(sample_passes)
                and parent_unchanged
                and atlas_input_unchanged
            ),
            "truth_status": args.truth_status,
            "medical_truth": args.truth_status == "doctor_confirmed",
            "atlas": {
                "path": str(atlas_path),
                "sha256": atlas_input_sha256,
                "frozen_copy": str(frozen_atlas),
                "frozen_copy_sha256": sha256(frozen_atlas),
                "input_unchanged_after_run": atlas_input_unchanged,
                "schema_version": atlas["schema_version"],
                "point_count": len(annotations),
            },
            "parent_delivery": {
                "path": str(parent),
                "dataset_index_sha256": sha256(parent / "dataset_index.json"),
                "sample_count": len(index),
                "unchanged_after_run": parent_unchanged,
            },
            "supersedes": (
                {
                    "path": str(supersedes),
                    "retained_in_place": True,
                    "reason": "A corrected Atlas was used for this newer label-only derivation.",
                }
                if supersedes is not None
                else None
            ),
            "derived_sample_count": len(derived_index),
            "pass_count": sum(sample_passes),
            "fail_count": sum(not value for value in sample_passes),
            "visible_instance_count": sum(item["qc"]["visible_count"] for item in derived_index),
            "invisible_instance_count": 600 - sum(item["qc"]["visible_count"] for item in derived_index),
            "visibility_reason_counts": dict(aggregate_reasons),
            "max_visible_point_depth_error_m": max(
                item["qc"]["max_visible_point_depth_error_m"] for item in derived_index
            ),
            "max_visible_point_backprojection_error_m": max(
                item["qc"]["max_visible_point_backprojection_error_m"] for item in derived_index
            ),
            "render_scene_buffers_called": False,
            "rgb_depth_mask_rerendered": False,
            "limitations": [
                "Only labels and overlays are newly generated; RGB, Depth, masks and render metadata are byte-identical parent assets.",
                "Visibility is recomputed per snapshot and may legitimately be false for any point.",
                "engineering_reference does not constitute doctor-confirmed medical truth.",
                "This route does not validate soft-tissue contact, real RGB-D noise or robot coordinates.",
            ],
        }
        write_json(output / "dataset_qc_report.json", report)
        (output / "README.md").write_text(
            "# Atlas v5 → 既有 30 场景标签派生\n\n"
            f"自动结果：**{'PASS' if report['passed'] else 'FAIL'}**。本目录从插件 schema v5 Atlas "
            "重新计算 30 个冻结 SKEL snapshot 的表面点、相机投影和真实可见性；没有调用渲染缓冲，"
            "没有重渲染 RGB、Depth 或 Mask。\n\n"
            "`rgb.png`、`scene_depth_z.npy`、两个 Mask 与 `render_metadata.json` 通过硬链接或复制复用，"
            "每个父资产和派生资产均记录 SHA-256。`labels.json` 与 `overlay.png` 是新生成文件。"
            "不可见点不会被强行改成可见，原因保存在 `visibility_reason`。\n\n"
            f"本轮 truth_status 为 `{args.truth_status}`。只有显式使用 `doctor_confirmed` 才会写入 medical_truth=true；"
            "默认工程参考 Atlas 不能当作医生医学真值。父交付和 snapshot 均经过运行前后哈希核对。\n"
            + (
                "\n此前派生目录 `"
                + str(supersedes)
                + "` 已由本次修正 Atlas 结果取代（superseded）；该旧目录保留且未被修改。"
                "本目录是当前结果。\n"
                if supersedes is not None
                else ""
            ),
            encoding="utf-8",
        )
        write_manifest(output)
        print(json.dumps({"passed": report["passed"], "output": str(output)}, ensure_ascii=False))
        if not report["passed"]:
            raise SystemExit(2)
    except Exception as exc:
        write_json(
            output / "FAILED_DO_NOT_USE.json",
            {
                "passed": False,
                "created_at": utc_now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "completed_samples": len(derived_index),
            },
        )
        raise


if __name__ == "__main__":
    main()
