#!/usr/bin/env python3
"""Prone-scene acceptance checks independent from fixture construction/export code."""

from __future__ import annotations

import argparse
import ast
from array import array
import json
from pathlib import Path
import struct
import sys

from PIL import Image


DORSAL_IDS = {
    "ENG_BACK_C7",
    "ENG_BACK_SCAPULA_L",
    "ENG_BACK_SCAPULA_R",
    "ENG_BACK_THORACIC_L",
    "ENG_BACK_THORACIC_R",
    "ENG_BACK_LUMBAR",
}
VENTRAL_IDS = {"ENG_FRONT_CHEST", "ENG_FRONT_ABDOMEN"}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--independent-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_npy_2d(path: Path) -> tuple[tuple[int, int], array]:
    with path.open("rb") as handle:
        if handle.read(6) != b"\x93NUMPY":
            raise ValueError("depth is not a NumPy file")
        major, minor = handle.read(2)
        header_length = struct.unpack("<H", handle.read(2))[0] if (major, minor) == (1, 0) else struct.unpack("<I", handle.read(4))[0]
        header = ast.literal_eval(handle.read(header_length).decode("latin1").strip())
        shape = tuple(int(value) for value in header["shape"])
        if len(shape) != 2 or header.get("fortran_order"):
            raise ValueError("depth must be a C-order 2-D array")
        descriptor = str(header["descr"])
        typecode = "f" if descriptor.endswith("f4") else "d"
        values = array(typecode)
        values.frombytes(handle.read())
        if descriptor.startswith(">") and sys.byteorder == "little":
            values.byteswap()
        if len(values) != shape[0] * shape[1]:
            raise ValueError("depth payload length mismatch")
        return (shape[0], shape[1]), values


def main() -> None:
    args = _arguments()
    labels = _load(args.sample / "labels.json")
    fixture = _load(args.fixture)
    independent = _load(args.independent_report)
    points = {str(point["point_id"]): point for point in labels.get("points", [])}
    fixture_points = {str(point["point_id"]): point for point in fixture.get("anchors", [])}
    checks = []

    def check(check_id: str, passed: bool, message: str, metrics=None) -> None:
        item = {"id": check_id, "passed": bool(passed), "message": message}
        if metrics is not None:
            item["metrics"] = metrics
        checks.append(item)

    check(
        "independent_replay_passed",
        independent.get("passed") is True,
        "Independent verifier must pass before prone-specific acceptance.",
        independent.get("summary"),
    )
    fixture_exact = set(points) == set(fixture_points) == DORSAL_IDS | VENTRAL_IDS
    if fixture_exact:
        for point_id, frozen in fixture_points.items():
            actual = points[point_id]
            fixture_exact = fixture_exact and (
                int(actual["face_index"]) == int(frozen["face_index"])
                and [int(value) for value in actual["vertex_indices"]]
                == [int(value) for value in frozen["vertex_indices"]]
                and max(
                    abs(float(a) - float(b))
                    for a, b in zip(actual["barycentric"], frozen["barycentric"])
                )
                <= 1e-12
            )
    check(
        "frozen_fixture_unchanged",
        fixture_exact,
        "All eight labels must retain the frozen face/vertices/barycentric binding; no point reselection is allowed.",
        {"point_count": len(points)},
    )

    dorsal_state = {
        point_id: points.get(point_id, {}).get("visibility_reason") for point_id in sorted(DORSAL_IDS)
    }
    check(
        "dorsal_anchors_visible",
        all(points.get(point_id, {}).get("visible") is True and dorsal_state[point_id] == "VISIBLE" for point_id in DORSAL_IDS),
        "All six dorsal engineering anchors must be visible from the overhead camera.",
        dorsal_state,
    )
    ventral_state = {
        point_id: points.get(point_id, {}).get("visibility_reason") for point_id in sorted(VENTRAL_IDS)
    }
    check(
        "ventral_anchors_not_visible",
        all(
            points.get(point_id, {}).get("visible") is False
            and ventral_state[point_id] in {"BACK_FACING", "SELF_OCCLUDED"}
            for point_id in VENTRAL_IDS
        ),
        "Chest/abdomen controls must be invisible from above; BACK_FACING is expected before the ray stage.",
        ventral_state,
    )

    probe = ((independent.get("blender_scene_probe") or {}).get("first") or {})
    probe_points = {str(item.get("point_id")): item for item in probe.get("point_results", [])}
    ventral_occluded = all(
        probe_points.get(point_id, {}).get("ray_hit") is True
        and probe_points.get(point_id, {}).get("ray_hit_object") == labels["model"]["object_name"]
        and float(probe_points.get(point_id, {}).get("ray_error_m") or 0.0) > 0.02
        for point_id in VENTRAL_IDS
    )
    check(
        "ventral_body_occlusion_ray",
        ventral_occluded,
        "Independent camera-to-ventral rays must hit a nearer part of the SKEL skin, proving body self-occlusion even though the primary reason is BACK_FACING.",
        {
            point_id: {
                "hit_object": probe_points.get(point_id, {}).get("ray_hit_object"),
                "ray_error_m": probe_points.get(point_id, {}).get("ray_error_m"),
            }
            for point_id in sorted(VENTRAL_IDS)
        },
    )

    depth_shape, depth = _read_npy_2d(args.sample / "scene_depth_z.npy")
    with Image.open(args.sample / "depth_valid_mask.png") as image:
        valid_shape = (image.height, image.width)
        valid = image.convert("L").tobytes()
    with Image.open(args.sample / "skin_mask.png") as image:
        skin_shape = (image.height, image.width)
        skin = image.convert("L").tobytes()
    non_skin_valid_count = sum(1 for valid_value, skin_value in zip(valid, skin) if valid_value == 255 and skin_value != 255)
    valid_depths = [float(value) for value, valid_value in zip(depth, valid) if valid_value == 255]
    bed_hits = [
        item
        for item in probe.get("pixel_rays", [])
        if (item.get("request") or {}).get("group") == "non_skin_surface"
        and item.get("hit_object") == "ACU_PRONE_BED"
    ]
    bed_ok = non_skin_valid_count > 10000 and len(bed_hits) >= 16
    check(
        "bed_depth_not_skin",
        bed_ok,
        "The bed must contribute valid first-surface scene depth while remaining outside Skin Mask.",
        {
            "valid_non_skin_pixel_count": non_skin_valid_count,
            "independent_bed_ray_count": len(bed_hits),
            "depth_min_m": min(valid_depths) if valid_depths else None,
            "depth_max_m": max(valid_depths) if valid_depths else None,
        },
    )
    check(
        "aligned_buffer_shapes",
        depth_shape == valid_shape == skin_shape,
        "Depth, valid mask, and skin mask must have identical dimensions.",
        {"depth": list(depth_shape), "valid": list(valid_shape), "skin": list(skin_shape)},
    )
    check(
        "scene_contract",
        labels.get("medical_truth") is False
        and labels.get("scene", {}).get("contract") == "SKEL_PRONE_BACK_RGBD_ENGINEERING_V1"
        and labels.get("scene", {}).get("snapshot_replayable") is True,
        "Labels must identify the prone engineering contract and frozen replay snapshot without medical claims.",
    )

    passed = all(item["passed"] for item in checks)
    report = {
        "schema": "skel-prone-rgbd-acceptance-v1",
        "passed": passed,
        "medical_truth": False,
        "checks": checks,
        "summary": {"pass": sum(item["passed"] for item in checks), "fail": sum(not item["passed"] for item in checks)},
        "interpretation_note": (
            "Ventral points are classified BACK_FACING by the primary mutually-exclusive visibility contract; "
            "the independent ray probe separately confirms that nearer dorsal skin blocks the camera-to-point ray."
        ),
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "summary": report["summary"], "output": str(args.output)}, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
