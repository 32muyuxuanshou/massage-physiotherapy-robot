from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: np.ndarray, q: float) -> float | None:
    return float(np.percentile(values, q)) if values.size else None


def summary(values: list[float] | np.ndarray, unit: str) -> dict:
    array = np.asarray(values, dtype=np.float64)
    if not array.size:
        return {"count": 0, "mean": None, "median": None, "p90": None, "p95": None, "p99": None, "max": None, "unit": unit}
    return {
        "count": int(array.size),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p90": percentile(array, 90),
        "p95": percentile(array, 95),
        "p99": percentile(array, 99),
        "max": float(array.max()),
        "unit": unit,
    }


def pixel_summary(values: list[float]) -> dict:
    result = summary(values, "original_render_px")
    array = np.asarray(values, dtype=np.float64)
    result["pck"] = {f"@{threshold}px": float((array <= threshold).mean()) if array.size else None for threshold in (5, 10, 20, 40)}
    return result


def millimetre_summary(values: list[float]) -> dict:
    result = summary(values, "mm")
    array = np.asarray(values, dtype=np.float64)
    result["within"] = {f"@{threshold}mm": float((array <= threshold).mean()) if array.size else None for threshold in (5, 10, 20, 30)}
    result["tail_failure_rate"] = {f">{threshold}mm": float((array > threshold).mean()) if array.size else None for threshold in (20, 30, 50)}
    return result


def backproject(u: float, v: float, z: float, row: dict) -> np.ndarray:
    return np.asarray([
        (u - row["cx"]) * z / row["fx"],
        (v - row["cy"]) * z / row["fy"],
        z,
    ], dtype=np.float64)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone evaluator: does not import training or exporter modules.")
    parser.add_argument("--exchange", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--training-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with args.exchange.open("r", newline="", encoding="utf-8") as stream:
        raw_rows = list(csv.DictReader(stream))
    numeric_float = (
        "gt_u_original", "gt_v_original", "pred_u_original", "pred_v_original",
        "gt_x_camera_m", "gt_y_camera_m", "gt_z_camera_m", "fx", "fy", "cx", "cy",
    )
    numeric_int = ("appearance_ordinal", "point_index", "visible", "original_width", "original_height")
    rows = []
    for raw in raw_rows:
        row = dict(raw)
        for key in numeric_float:
            row[key] = float(row[key])
        for key in numeric_int:
            row[key] = int(row[key])
        rows.append(row)

    coordinate_checks = {
        "all_original_resolution_1280x1024": all(row["original_width"] == 1280 and row["original_height"] == 1024 for row in rows),
        "all_finite_coordinates_and_intrinsics": all(
            all(math.isfinite(row[key]) for key in numeric_float) and row["fx"] > 0 and row["fy"] > 0 for row in rows
        ),
        "visibility_flag_matches_reason": all(bool(row["visible"]) == (row["visibility_reason"] == "VISIBLE") for row in rows),
    }

    buffer_cache: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    tail_rows = []
    report = {"schema": "engineering-pilot-standalone-evaluation-v2", "medical_truth": False, "splits": {}}

    for split_id in SPLITS:
        report["splits"][split_id] = {}
        for bucket in ("test", "challenge"):
            selected = [row for row in rows if row["split_id"] == split_id and row["bucket"] == bucket]
            visible = [row for row in selected if row["visible"]]
            pixel_errors = []
            oracle_errors_mm = []
            pred_uv_gt_z_errors_mm = []
            final_errors_mm = []
            invalid_final = defaultdict(int)
            by_camera = defaultdict(list)
            by_point = defaultdict(list)
            by_geometry = defaultdict(lambda: {"pixel": [], "final_3d_mm": []})

            for row in visible:
                du = row["pred_u_original"] - row["gt_u_original"]
                dv = row["pred_v_original"] - row["gt_v_original"]
                pixel_error = math.hypot(du, dv)
                pixel_errors.append(pixel_error)
                by_camera[row["camera_id"]].append(pixel_error)
                by_point[row["point_id"]].append(pixel_error)
                by_geometry[row["base_geometry_id"]]["pixel"].append(pixel_error)
                target = np.asarray([row["gt_x_camera_m"], row["gt_y_camera_m"], row["gt_z_camera_m"]], dtype=np.float64)

                key = row["depth_relative_path"]
                if key not in buffer_cache:
                    depth = np.load(args.dataset / key, allow_pickle=False)
                    with Image.open(args.dataset / row["valid_mask_relative_path"]) as image:
                        valid = np.asarray(image.convert("L"), dtype=np.uint8)
                    with Image.open(args.dataset / row["skin_mask_relative_path"]) as image:
                        skin = np.asarray(image.convert("L"), dtype=np.uint8)
                    buffer_cache[key] = depth, valid, skin
                depth, valid, skin = buffer_cache[key]

                gt_col, gt_image_row = int(math.floor(row["gt_u_original"])), int(math.floor(row["gt_v_original"]))
                if 0 <= gt_col < depth.shape[1] and 0 <= gt_image_row < depth.shape[0] and depth[gt_image_row, gt_col] > 0:
                    oracle_xyz = backproject(row["gt_u_original"], row["gt_v_original"], float(depth[gt_image_row, gt_col]), row)
                    oracle_errors_mm.append(float(np.linalg.norm(oracle_xyz - target) * 1000.0))

                pure_2d_xyz = backproject(row["pred_u_original"], row["pred_v_original"], row["gt_z_camera_m"], row)
                pred_uv_gt_z_errors_mm.append(float(np.linalg.norm(pure_2d_xyz - target) * 1000.0))

                col, image_row = int(math.floor(row["pred_u_original"])), int(math.floor(row["pred_v_original"]))
                reason = None
                if not (0 <= col < depth.shape[1] and 0 <= image_row < depth.shape[0]):
                    reason = "PREDICTED_OUT_OF_FRAME"
                elif depth[image_row, col] <= 0 or valid[image_row, col] != 255:
                    reason = "INVALID_DEPTH"
                elif skin[image_row, col] != 255:
                    reason = "NON_SKIN_FIRST_SURFACE"
                if reason:
                    invalid_final[reason] += 1
                else:
                    final_xyz = backproject(row["pred_u_original"], row["pred_v_original"], float(depth[image_row, col]), row)
                    final_error_mm = float(np.linalg.norm(final_xyz - target) * 1000.0)
                    final_errors_mm.append(final_error_mm)
                    by_geometry[row["base_geometry_id"]]["final_3d_mm"].append(final_error_mm)
                    if final_error_mm > 30.0:
                        tail_rows.append({
                            "split_id": split_id,
                            "bucket": bucket,
                            "sample_id": row["sample_id"],
                            "base_geometry_id": row["base_geometry_id"],
                            "camera_id": row["camera_id"],
                            "shape_id": row["shape_id"],
                            "pose_id": row["pose_id"],
                            "point_id": row["point_id"],
                            "pixel_error_original": pixel_error,
                            "final_3d_error_mm": final_error_mm,
                        })

            geometry_mean_pixel = [float(np.mean(value["pixel"])) for value in by_geometry.values() if value["pixel"]]
            geometry_max_pixel = [float(np.max(value["pixel"])) for value in by_geometry.values() if value["pixel"]]
            geometry_mean_3d = [float(np.mean(value["final_3d_mm"])) for value in by_geometry.values() if value["final_3d_mm"]]
            geometries_over_30 = sum(any(error > 30.0 for error in value["final_3d_mm"]) for value in by_geometry.values())
            report["splits"][split_id][bucket] = {
                "sample_count": len({row["sample_id"] for row in selected}),
                "unique_base_geometry_count": len({row["base_geometry_id"] for row in selected}),
                "visible_point_instances": len(visible),
                "pixel_error_original": pixel_summary(pixel_errors),
                "by_camera": {key: pixel_summary(value) for key, value in sorted(by_camera.items())},
                "by_point": {key: pixel_summary(value) for key, value in sorted(by_point.items())},
                "geometry_clustered": {
                    "mean_pixel_error_per_geometry": summary(geometry_mean_pixel, "original_render_px"),
                    "max_pixel_error_per_geometry": summary(geometry_max_pixel, "original_render_px"),
                    "mean_final_3d_error_per_geometry": summary(geometry_mean_3d, "mm"),
                    "geometries_with_any_final_error_gt_30mm": geometries_over_30,
                },
                "error_decomposition_3d": {
                    "A_oracle_gt_uv_plus_scene_depth": millimetre_summary(oracle_errors_mm),
                    "B_pred_uv_plus_gt_point_z": millimetre_summary(pred_uv_gt_z_errors_mm),
                    "C_pred_uv_plus_scene_depth": millimetre_summary(final_errors_mm),
                    "C_invalid_count": sum(invalid_final.values()),
                    "C_invalid_reasons": dict(invalid_final),
                    "note": "A/B/C are diagnostics and are not algebraically additive.",
                },
            }

    write_json(output / "standalone_evaluation_v2.json", report)

    headline_splits = {}
    total_test_visible = 0
    total_test_gt30 = 0
    total_challenge_visible = 0
    total_challenge_gt30 = 0
    for split_id in SPLITS:
        test = report["splits"][split_id]["test"]
        challenge = report["splits"][split_id]["challenge"]
        test_final = test["error_decomposition_3d"]["C_pred_uv_plus_scene_depth"]
        challenge_final = challenge["error_decomposition_3d"]["C_pred_uv_plus_scene_depth"]
        test_gt30 = round(test_final["count"] * test_final["tail_failure_rate"][">30mm"])
        challenge_gt30 = round(challenge_final["count"] * challenge_final["tail_failure_rate"][">30mm"])
        total_test_visible += test_final["count"]
        total_test_gt30 += test_gt30
        total_challenge_visible += challenge_final["count"]
        total_challenge_gt30 += challenge_gt30
        headline_splits[split_id] = {
            "test_samples": test["sample_count"],
            "test_unique_base_geometries": test["unique_base_geometry_count"],
            "pixel_error_original": test["pixel_error_original"],
            "A_oracle_gt_uv_plus_scene_depth_mm": test["error_decomposition_3d"]["A_oracle_gt_uv_plus_scene_depth"],
            "B_pred_uv_plus_gt_point_z_mm": test["error_decomposition_3d"]["B_pred_uv_plus_gt_point_z"],
            "C_pred_uv_plus_scene_depth_mm": test_final,
            "test_gt30mm_count": test_gt30,
            "unique_geometries_with_any_gt30mm": test["geometry_clustered"]["geometries_with_any_final_error_gt_30mm"],
        }
    headline = {
        "schema": "engineering-pilot-evaluation-contract-v2-summary",
        "medical_truth": False,
        "coordinate_statement": "All reported pixel errors are continuous original-render 1280x1024 pixels.",
        "decoder": "SPATIAL_SOFTMAX_EXPECTATION",
        "splits": headline_splits,
        "aggregate_tail": {
            "test_visible_instances_across_three_evaluations": total_test_visible,
            "test_gt30mm_count": total_test_gt30,
            "test_gt30mm_rate": total_test_gt30 / total_test_visible,
            "challenge_visible_instances_across_three_evaluations": total_challenge_visible,
            "challenge_gt30mm_count": total_challenge_gt30,
            "challenge_gt30mm_rate": total_challenge_gt30 / total_challenge_visible,
            "warning": "The same synthetic base geometries can contribute multiple appearance variants and multiple split evaluations; this is an engineering diagnostic, not an independent population estimate.",
        },
        "interpretation": [
            "Oracle GT-uv plus scene-depth error stays sub-millimetre on average, so the large final tails are not created by the GT depth pipeline.",
            "Predicted-uv plus GT point Z already explains most of the final 3D error; 2D localization is the dominant current source.",
            "Tail failures remain incompatible with robot-safe claims, even though mean error is much smaller.",
        ],
    }
    write_json(output / "evaluation_summary_v2.json", headline)

    crosschecks = {}
    all_crosschecks_passed = True
    for split_id in SPLITS:
        reference = read_json(args.training_root / split_id / "independent_evaluation.json")
        actual = report["splits"][split_id]
        checks = {}
        for bucket in ("test", "challenge"):
            reference_2d = reference[bucket]["visible_2d"]
            actual_2d = actual[bucket]["pixel_error_original"]
            reference_3d = reference[bucket]["depth_to_3d"]["xyz_error_mm"]
            actual_3d = actual[bucket]["error_decomposition_3d"]["C_pred_uv_plus_scene_depth"]
            checks[f"{bucket}_2d_count"] = actual_2d["count"] == reference_2d["count"]
            checks[f"{bucket}_2d_mean"] = abs(actual_2d["mean"] - reference_2d["mean"]) < 1e-9
            checks[f"{bucket}_2d_max"] = abs(actual_2d["max"] - reference_2d["max"]) < 1e-9
            checks[f"{bucket}_3d_count"] = actual_3d["count"] == reference_3d["count"]
            checks[f"{bucket}_3d_mean"] = abs(actual_3d["mean"] - reference_3d["mean"]) < 1e-9
            checks[f"{bucket}_3d_max"] = abs(actual_3d["max"] - reference_3d["max"]) < 1e-9
        split_passed = all(checks.values())
        all_crosschecks_passed &= split_passed
        crosschecks[split_id] = {"passed": split_passed, "checks": checks}
    write_json(output / "legacy_crosscheck.json", {"schema": "evaluation-v2-legacy-crosscheck", "passed": all_crosschecks_passed, "splits": crosschecks})

    tail_path = output / "tail_failures_gt30mm.csv"
    with tail_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(tail_rows[0]) if tail_rows else ["split_id"])
        writer.writeheader()
        writer.writerows(sorted(tail_rows, key=lambda row: row["final_3d_error_mm"], reverse=True))

    verification = {
        "schema": "engineering-pilot-evaluation-contract-v2-verification",
        "passed": bool(all(coordinate_checks.values()) and all_crosschecks_passed),
        "checks": {**coordinate_checks, "legacy_metrics_exactly_reproduced": all_crosschecks_passed},
        "exchange_sha256": sha256(args.exchange),
        "standalone_evaluation_sha256": sha256(output / "standalone_evaluation_v2.json"),
        "tail_failure_count_gt30mm": len(tail_rows),
        "tail_failure_count_gt30mm_by_bucket": {
            "test": total_test_gt30,
            "challenge": total_challenge_gt30,
        },
        "truth_status": {"medical_truth": False, "real_human_validated": False, "robot_safe": False},
    }
    write_json(output / "verification.json", verification)
    print(json.dumps({"EVALUATION_V2": "PASS" if verification["passed"] else "FAIL", "tail_gt30mm": len(tail_rows)}))
    if not verification["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
