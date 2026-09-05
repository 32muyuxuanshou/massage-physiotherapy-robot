from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summary(values: list[float], unit: str) -> dict:
    data = np.asarray(values, dtype=np.float64)
    if not data.size:
        return {"count": 0, "mean": None, "median": None, "p90": None, "p95": None, "p99": None, "max": None, "unit": unit}
    return {
        "count": int(data.size), "mean": float(data.mean()), "median": float(np.median(data)),
        "p90": float(np.percentile(data, 90)), "p95": float(np.percentile(data, 95)),
        "p99": float(np.percentile(data, 99)), "max": float(data.max()), "unit": unit,
    }


def evaluate(
    predicted: np.ndarray,
    target_uv: np.ndarray,
    visible: np.ndarray,
    selected_rows: list[dict],
    point_ids: list[str],
) -> dict:
    pixel = np.linalg.norm(predicted - target_uv, axis=2)
    pixel_values = pixel[visible].tolist()
    by_camera = defaultdict(list)
    by_point = defaultdict(list)
    final_3d = []
    invalid = defaultdict(int)
    tail = []
    buffer_cache = {}
    for sample_index, row in enumerate(selected_rows):
        camera_id = row["camera_id"]
        sample_dir = Path(row["gate_sample_directory"])
        if str(sample_dir) not in buffer_cache:
            labels = read_json(sample_dir / "labels.json")
            depth = np.load(sample_dir / "scene_depth_z.npy", allow_pickle=False)
            with Image.open(sample_dir / "depth_valid_mask.png") as image:
                valid = np.asarray(image.convert("L"), dtype=np.uint8)
            with Image.open(sample_dir / "skin_mask.png") as image:
                skin = np.asarray(image.convert("L"), dtype=np.uint8)
            buffer_cache[str(sample_dir)] = labels, depth, valid, skin
        labels, depth, valid, skin = buffer_cache[str(sample_dir)]
        intrinsics = labels["camera"]["intrinsics"]
        for point_index, point_id in enumerate(point_ids):
            if not visible[sample_index, point_index]:
                continue
            error_px = float(pixel[sample_index, point_index])
            by_camera[camera_id].append(error_px)
            by_point[point_id].append(error_px)
            u, v = map(float, predicted[sample_index, point_index])
            col, image_row = int(math.floor(u)), int(math.floor(v))
            reason = None
            if not (0 <= col < depth.shape[1] and 0 <= image_row < depth.shape[0]):
                reason = "PREDICTED_OUT_OF_FRAME"
            elif depth[image_row, col] <= 0 or valid[image_row, col] != 255:
                reason = "INVALID_DEPTH"
            elif skin[image_row, col] != 255:
                reason = "NON_SKIN_FIRST_SURFACE"
            if reason:
                invalid[reason] += 1
                continue
            z = float(depth[image_row, col])
            xyz = np.asarray([
                (u - float(intrinsics["cx"])) * z / float(intrinsics["fx"]),
                (v - float(intrinsics["cy"])) * z / float(intrinsics["fy"]),
                z,
            ])
            target = np.asarray(labels["points"][point_index]["xyz_camera_opencv_m"], dtype=np.float64)
            error_mm = float(np.linalg.norm(xyz - target) * 1000.0)
            final_3d.append(error_mm)
            if error_mm > 30.0:
                tail.append({
                    "sample_id": row["sample_id"], "case_id": row["case_id"], "camera_id": camera_id,
                    "point_id": point_id, "pixel_error": error_px, "final_3d_error_mm": error_mm,
                })
    pixel_report = summary(pixel_values, "original_render_px")
    pixel_report["pck"] = {f"@{value}px": float((np.asarray(pixel_values) <= value).mean()) for value in (5, 10, 20, 40)}
    final_report = summary(final_3d, "mm")
    final_report["tail_failure_rate"] = {f">{value}mm": float((np.asarray(final_3d) > value).mean()) for value in (20, 30, 50)}
    return {
        "visible_2d": pixel_report,
        "by_camera": {key: summary(value, "original_render_px") for key, value in sorted(by_camera.items())},
        "by_point": {key: summary(value, "original_render_px") for key, value in sorted(by_point.items())},
        "final_3d": final_report,
        "invalid_3d_count": int(sum(invalid.values())),
        "invalid_3d_reasons": dict(invalid),
        "tail_gt30mm": sorted(tail, key=lambda item: item["final_3d_error_mm"], reverse=True),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-v2", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dataset = args.dataset_v2.resolve()
    output = args.output.resolve()
    data = np.load(dataset / "truncation_holdout_v2.npz", allow_pickle=False)
    manifest = read_json(dataset / "dataset_manifest.json")
    by_id = {row["sample_id"]: row for row in manifest["truncation_holdout"]}
    splits = read_json(dataset / "contracts" / "evaluation_splits_v1.json")
    sample_ids = data["sample_ids"].astype(str)
    case_ids = data["case_ids"].astype(str)
    point_ids = data["point_ids"].astype(str).tolist()
    report = {"schema": "failure-driven-truncation-holdout-ab-v2", "medical_truth": False, "splits": {}}
    for split_id in SPLITS:
        test_cases = set(splits["splits"][split_id]["test_case_ids"])
        selection = np.asarray([index for index, case_id in enumerate(case_ids) if case_id in test_cases], dtype=np.int64)
        rows = [by_id[sample_ids[index]] for index in selection]
        target_uv = data["uv"][selection].astype(np.float64)
        visible = data["visible"][selection].astype(bool)
        prediction = np.load(args.predictions / f"{split_id}_predictions.npz", allow_pickle=False)
        if not np.array_equal(prediction["selection"], selection):
            raise RuntimeError(f"Prediction selection changed: {split_id}")
        v1_pred = prediction["v1_predicted_uv"].astype(np.float64)
        v2_pred = prediction["v2_predicted_uv"].astype(np.float64)
        v1_eval = evaluate(v1_pred, target_uv, visible, rows, point_ids)
        v2_eval = evaluate(v2_pred, target_uv, visible, rows, point_ids)
        report["splits"][split_id] = {
            "holdout_sample_count": int(selection.size),
            "test_case_ids": sorted(test_cases),
            "v1": v1_eval,
            "v2": v2_eval,
            "delta_v2_minus_v1": {
                "mean_2d_px": v2_eval["visible_2d"]["mean"] - v1_eval["visible_2d"]["mean"],
                "p95_2d_px": v2_eval["visible_2d"]["p95"] - v1_eval["visible_2d"]["p95"],
                "mean_3d_mm": v2_eval["final_3d"]["mean"] - v1_eval["final_3d"]["mean"],
                "p95_3d_mm": v2_eval["final_3d"]["p95"] - v1_eval["final_3d"]["p95"],
                "tail_gt30mm_count": len(v2_eval["tail_gt30mm"]) - len(v1_eval["tail_gt30mm"]),
            },
        }
        print(f"{split_id}: V1 {v1_eval['visible_2d']['mean']:.3f}px -> V2 {v2_eval['visible_2d']['mean']:.3f}px", flush=True)
    checks = {
        "three_splits": len(report["splits"]) == 3,
        "all_holdouts_nonempty": all(item["holdout_sample_count"] > 0 for item in report["splits"].values()),
        "all_v2_means_finite": all(math.isfinite(item["v2"]["visible_2d"]["mean"]) for item in report["splits"].values()),
        "same_holdout_used_for_v1_v2": True,
    }
    report["verification"] = {"passed": all(checks.values()), "checks": checks}
    write_json(output / "truncation_holdout_ab_report.json", report)
    print(json.dumps({"TRUNCATION_HOLDOUT_AB": "PASS" if all(checks.values()) else "FAIL"}, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
