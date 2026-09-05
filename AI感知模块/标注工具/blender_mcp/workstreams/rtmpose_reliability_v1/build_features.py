from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image


LOCATORS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
POINT_IDS = [
    "GV14_MIDLINE", "BL13_LEFT", "BL13_RIGHT", "GV9_MIDLINE", "BL17_LEFT",
    "BL17_RIGHT", "GV6_MIDLINE", "BL20_LEFT", "BL20_RIGHT", "GV4_MIDLINE",
    "BL23_LEFT", "BL23_RIGHT", "BL25_LEFT", "BL25_RIGHT", "BL28_LEFT",
    "BL28_RIGHT", "GB21_LEFT", "GB21_RIGHT", "SI15_LEFT", "SI15_RIGHT",
]
FEATURES = [
    "keypoint_score",
    "simcc_x_peak_raw", "simcc_y_peak_raw",
    "simcc_x_peak_normalized", "simcc_y_peak_normalized",
    "simcc_x_top1_top2_gap", "simcc_y_top1_top2_gap",
    "simcc_x_entropy_normalized", "simcc_y_entropy_normalized",
    "simcc_x_std_bins", "simcc_y_std_bins",
    "simcc_x_boundary_mass_8", "simcc_y_boundary_mass_8",
    "predicted_u_original_px", "predicted_v_original_px", "predicted_edge_distance_px",
    "predicted_uv_in_frame", "depth_valid_at_predicted_uv",
    "depth_z_m_at_predicted_uv", "local_depth_valid_fraction_5x5",
    "local_depth_std_m_5x5", "local_depth_range_m_5x5",
]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def distribution_features(values: np.ndarray, axis: str) -> dict[str, np.ndarray]:
    raw = values.astype(np.float64)
    total = np.maximum(raw.sum(axis=2, keepdims=True), 1e-15)
    prob = raw / total
    order = np.partition(prob, -2, axis=2)
    top1, top2 = order[:, :, -1], order[:, :, -2]
    entropy = -(prob * np.log(np.clip(prob, 1e-15, None))).sum(axis=2)
    bins = np.arange(prob.shape[2], dtype=np.float64)[None, None, :]
    mean = (prob * bins).sum(axis=2)
    std = np.sqrt(np.maximum((prob * (bins - mean[:, :, None]) ** 2).sum(axis=2), 0.0))
    edge = np.minimum(bins, prob.shape[2] - 1 - bins) < 8
    boundary_mass = (prob * edge).sum(axis=2)
    return {
        f"simcc_{axis}_peak_raw": raw.max(axis=2).astype(np.float32),
        f"simcc_{axis}_peak_normalized": top1.astype(np.float32),
        f"simcc_{axis}_top1_top2_gap": (top1 - top2).astype(np.float32),
        f"simcc_{axis}_entropy_normalized": (entropy / math.log(prob.shape[2])).astype(np.float32),
        f"simcc_{axis}_std_bins": std.astype(np.float32),
        f"simcc_{axis}_boundary_mass_8": boundary_mass.astype(np.float32),
    }


def depth_features(depth: np.ndarray, valid: np.ndarray, u: float, v: float) -> dict:
    col, row = int(math.floor(u)), int(math.floor(v))
    in_frame = 0 <= col < depth.shape[1] and 0 <= row < depth.shape[0]
    result = {
        "predicted_uv_in_frame": in_frame,
        "depth_valid_at_predicted_uv": False,
        "depth_z_m_at_predicted_uv": float("nan"),
        "local_depth_valid_fraction_5x5": 0.0,
        "local_depth_std_m_5x5": float("nan"),
        "local_depth_range_m_5x5": float("nan"),
    }
    if not in_frame:
        return result
    r0, r1 = max(0, row - 2), min(depth.shape[0], row + 3)
    c0, c1 = max(0, col - 2), min(depth.shape[1], col + 3)
    patch = depth[r0:r1, c0:c1]
    patch_valid = (valid[r0:r1, c0:c1] == 255) & (patch > 0)
    values = patch[patch_valid]
    result["depth_valid_at_predicted_uv"] = bool(valid[row, col] == 255 and depth[row, col] > 0)
    if result["depth_valid_at_predicted_uv"]:
        result["depth_z_m_at_predicted_uv"] = float(depth[row, col])
    result["local_depth_valid_fraction_5x5"] = float(patch_valid.mean())
    if values.size:
        result["local_depth_std_m_5x5"] = float(values.std())
        result["local_depth_range_m_5x5"] = float(values.max() - values.min())
    return result


def build_partition(source: Path, prediction_root: Path, output: Path, partition: str) -> dict:
    manifest = read(source / "selected_dataset_manifest.json")
    selected = [row for row in manifest["selected_samples"] if row["partition"] == partition]
    reports = {}
    for locator in LOCATORS:
        prediction_path = prediction_root / partition / f"{locator}.npz"
        data = np.load(prediction_path, allow_pickle=False)
        index = {str(sample_id): i for i, sample_id in enumerate(data["sample_ids"])}
        if set(index) != {row["sample_id"] for row in selected}:
            raise ValueError(f"Prediction/sample mismatch for {partition}/{locator}")
        fx = distribution_features(data["simcc_x"], "x")
        fy = distribution_features(data["simcc_y"], "y")
        rows = []
        for sample_row in selected:
            i = index[sample_row["sample_id"]]
            sample = Path(sample_row["sample"])
            labels = read(sample / "labels.json")
            points = {point["point_id"]: point for point in labels["points"]}
            depth = np.load(sample / "scene_depth_z.npy", allow_pickle=False)
            with Image.open(sample / "depth_valid_mask.png") as image:
                valid = np.asarray(image.convert("L"), np.uint8)
            intr = labels["camera"]["intrinsics"]
            for j, point_id in enumerate(POINT_IDS):
                point = points[point_id]
                u, v = map(float, data["uv_original_px"][i, j])
                runtime_depth = depth_features(depth, valid, u, v)
                available = bool(
                    point["visibility_reason"] == "VISIBLE"
                    and point["visible"] and point["in_frame"] and point["front_facing"]
                )
                error_mm = None
                invalid_reason = ""
                if available:
                    if not runtime_depth["predicted_uv_in_frame"]:
                        invalid_reason = "PREDICTED_OUT_OF_FRAME"
                    elif not runtime_depth["depth_valid_at_predicted_uv"]:
                        invalid_reason = "INVALID_DEPTH"
                    else:
                        z = runtime_depth["depth_z_m_at_predicted_uv"]
                        xyz = np.asarray([
                            (u - intr["cx"]) * z / intr["fx"],
                            (v - intr["cy"]) * z / intr["fy"],
                            z,
                        ])
                        error_mm = float(
                            np.linalg.norm(xyz - np.asarray(point["xyz_camera_opencv_m"])) * 1000.0
                        )
                row = {
                    "partition": partition,
                    "locator_model": locator,
                    "sample_id": sample_row["sample_id"],
                    "body_geometry_id": sample_row["case_id"],
                    "camera_id": sample_row["camera_id"],
                    "camera_kind": sample_row["camera_kind"],
                    "point_id": point_id,
                    "gt_visibility_reason": point["visibility_reason"],
                    "gt_available_for_3d": available,
                    "final_3d_error_mm": error_mm,
                    "bad15": bool(error_mm is not None and error_mm > 15.0),
                    "bad20": bool(error_mm is not None and error_mm > 20.0),
                    "bad30": bool(error_mm is not None and error_mm > 30.0),
                    "bad50": bool(error_mm is not None and error_mm > 50.0),
                    "invalid_prediction_reason": invalid_reason,
                    "keypoint_score": float(data["keypoint_scores"][i, j]),
                    "predicted_u_original_px": u,
                    "predicted_v_original_px": v,
                    "predicted_edge_distance_px": min(u, v, 1280.0 - u, 1024.0 - v),
                    **{name: float(values[i, j]) for name, values in fx.items()},
                    **{name: float(values[i, j]) for name, values in fy.items()},
                    **runtime_depth,
                }
                rows.append(row)
        csv_path = output / "runtime_features" / partition / f"{locator}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        reports[locator] = {
            "prediction_sha256": sha(prediction_path),
            "features_sha256": sha(csv_path),
            "rows": len(rows),
            "bodies": len({row["body_geometry_id"] for row in rows}),
            "available": sum(row["gt_available_for_3d"] for row in rows),
            "unavailable": sum(not row["gt_available_for_3d"] for row in rows),
            "bad30": sum(row["bad30"] for row in rows),
            "invalid_3d": sum(bool(row["invalid_prediction_reason"]) for row in rows),
        }
    report = {
        "schema": "rtmpose-reliability-runtime-features-v1",
        "partition": partition,
        "passed": all(item["rows"] == len(selected) * 20 for item in reports.values()),
        "samples": len(selected),
        "reports": reports,
    }
    write(output / f"{partition.lower()}_runtime_feature_report.json", report)
    return report


def freeze(output: Path, source: Path, prediction_root: Path) -> None:
    train = read(output / "reliability_train_runtime_feature_report.json")
    calibration = read(output / "calibration_runtime_feature_report.json")
    untouched_absent = not (prediction_root / "UNTOUCHED_TEST").exists()
    checks = {
        "train_passed": train["passed"],
        "calibration_passed": calibration["passed"],
        "three_locators_separate": set(train["reports"]) == set(LOCATORS) == set(calibration["reports"]),
        "untouched_predictions_absent": untouched_absent,
        "no_reliability_models_exist": not (output / "reliability_models").exists(),
    }
    contract = {
        "schema": "rtmpose-reliability-runtime-feature-contract-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "runtime_input_features": FEATURES,
        "target_or_evaluation_only": [
            "gt_visibility_reason", "gt_available_for_3d", "final_3d_error_mm",
            "bad15", "bad20", "bad30", "bad50", "invalid_prediction_reason",
        ],
        "grouping_only_not_model_inputs": [
            "sample_id", "body_geometry_id", "camera_id", "camera_kind",
            "point_id", "partition", "locator_model",
        ],
        "model_policy": "One availability and one BAD30 model per RTMPose-S locator; no pooling.",
        "medical_truth": False,
        "production_or_robot_use": False,
    }
    contract_path = output / "RUNTIME_FEATURE_CONTRACT_V1.json"
    write(contract_path, contract)
    write(output / "runtime_feature_contract_freeze_receipt.json", {
        "schema": "rtmpose-reliability-feature-freeze-receipt-v1",
        "passed": contract["passed"],
        "runtime_feature_contract_sha256": sha(contract_path),
        "selected_dataset_manifest_sha256": sha(source / "selected_dataset_manifest.json"),
        "untouched_test_inference_absent_at_freeze": untouched_absent,
        "reliability_training_authorized": contract["passed"],
        "untouched_test_authorized": False,
    })
    if not contract["passed"]:
        raise SystemExit(3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "freeze"))
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--partition", choices=("RELIABILITY_TRAIN", "CALIBRATION", "UNTOUCHED_TEST"))
    args = parser.parse_args()
    if args.mode == "build":
        if not args.partition:
            raise SystemExit("--partition is required")
        report = build_partition(args.source.resolve(), args.predictions.resolve(), args.output.resolve(), args.partition)
        print(json.dumps(report, indent=2))
    else:
        freeze(args.output.resolve(), args.source.resolve(), args.predictions.resolve())


if __name__ == "__main__":
    main()
