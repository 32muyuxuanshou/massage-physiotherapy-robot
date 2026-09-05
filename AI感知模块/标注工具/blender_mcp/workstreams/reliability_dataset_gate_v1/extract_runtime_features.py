from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image


HERE = Path(__file__).resolve().parent
DECODER_WS = HERE.parent / "decoder_contract_v1"
sys.path.insert(0, str(DECODER_WS))
from boundary_hybrid_decoder import decode_guarded  # noqa: E402
from infer_decoder_gate import SPLITS, TinyHeatmapNet  # noqa: E402

PARTITIONS = ("RELIABILITY_TRAIN", "CALIBRATION")
WIDTH, HEIGHT = 1280, 1024


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_partition(manifest: dict, partition: str) -> tuple[np.ndarray, list[dict]]:
    selected = [row for row in manifest["selected_samples"] if row["partition"] == partition]
    images = []
    for row in selected:
        with Image.open(Path(row["sample"]) / "rgb_model.png") as image:
            images.append(
                np.asarray(
                    image.convert("RGB").resize((160, 128), Image.Resampling.BILINEAR),
                    dtype=np.uint8,
                )
            )
    return np.asarray(images), selected


def probability_features(logits: np.ndarray) -> dict[str, np.ndarray]:
    b, p, h, w = logits.shape
    flat = logits.reshape(b, p, -1).astype(np.float64)
    shifted = flat - flat.max(axis=2, keepdims=True)
    exp = np.exp(shifted)
    prob = exp / exp.sum(axis=2, keepdims=True)
    order = np.partition(prob, -2, axis=2)
    top1 = order[:, :, -1]
    top2 = order[:, :, -2]
    entropy = -(prob * np.log(np.clip(prob, 1e-15, None))).sum(axis=2)
    entropy_norm = entropy / math.log(h * w)
    grid_y, grid_x = np.mgrid[0:h, 0:w]
    grid_x = grid_x.reshape(1, 1, -1)
    grid_y = grid_y.reshape(1, 1, -1)
    mean_x = (prob * grid_x).sum(axis=2)
    mean_y = (prob * grid_y).sum(axis=2)
    std_x = np.sqrt(np.maximum((prob * (grid_x - mean_x[:, :, None]) ** 2).sum(axis=2), 0.0))
    std_y = np.sqrt(np.maximum((prob * (grid_y - mean_y[:, :, None]) ** 2).sum(axis=2), 0.0))
    argmax = prob.argmax(axis=2)
    peak_x, peak_y = argmax % w, argmax // w
    local_mass = np.zeros((b, p), np.float64)
    for i in range(b):
        for j in range(p):
            x, y = int(peak_x[i, j]), int(peak_y[i, j])
            patch = prob[i, j].reshape(h, w)[max(0, y - 1):min(h, y + 2), max(0, x - 1):min(w, x + 2)]
            local_mass[i, j] = patch.sum()
    return {
        "logit_peak": logits.reshape(b, p, -1).max(axis=2).astype(np.float32),
        "probability_peak": top1.astype(np.float32),
        "probability_top1_top2_gap": (top1 - top2).astype(np.float32),
        "entropy_nats": entropy.astype(np.float32),
        "entropy_normalized": entropy_norm.astype(np.float32),
        "local_3x3_probability_mass": local_mass.astype(np.float32),
        "heatmap_std_x_cells": std_x.astype(np.float32),
        "heatmap_std_y_cells": std_y.astype(np.float32),
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
    result["depth_z_m_at_predicted_uv"] = float(depth[row, col]) if result["depth_valid_at_predicted_uv"] else float("nan")
    result["local_depth_valid_fraction_5x5"] = float(patch_valid.mean())
    if values.size:
        result["local_depth_std_m_5x5"] = float(values.std())
        result["local_depth_range_m_5x5"] = float(values.max() - values.min())
    return result


def infer_partition(root: Path, weights_root: Path, partition: str) -> dict:
    manifest = read(root / "selected_dataset_manifest.json")
    images, selected = load_partition(manifest, partition)
    raw = torch.from_numpy(images.astype(np.float32) / 255.0).permute(0, 3, 1, 2)
    reports = {}
    for split in SPLITS:
        state_path = weights_root / split / "model_state.pt"
        state = torch.load(state_path, map_location="cpu", weights_only=False)
        model = TinyHeatmapNet(len(state["point_ids"]))
        model.load_state_dict(state["model_state"])
        model.eval()
        normalized = (raw - state["channel_mean"]) / state["channel_std"]
        with torch.no_grad():
            logits = model(normalized).cpu().numpy().astype(np.float32)
        decoded = decode_guarded(logits, boundary_cells=4, curvature_epsilon=1e-8, min_correction_original_px=12.0)
        prob_features = probability_features(logits)
        pred_dir = root / "locator_predictions" / partition
        pred_dir.mkdir(parents=True, exist_ok=True)
        prediction_path = pred_dir / f"{split}.npz"
        np.savez_compressed(prediction_path, logits=logits, **decoded, **prob_features)
        rows = []
        for i, sample_row in enumerate(selected):
            sample = Path(sample_row["sample"])
            labels = read(sample / "labels.json")
            depth = np.load(sample / "scene_depth_z.npy", allow_pickle=False)
            with Image.open(sample / "depth_valid_mask.png") as image:
                valid = np.asarray(image.convert("L"), np.uint8)
            intr = labels["camera"]["intrinsics"]
            for j, point in enumerate(labels["points"]):
                u, v = map(float, decoded["hybrid"][i, j])
                runtime_depth = depth_features(depth, valid, u, v)
                available = bool(point["visibility_reason"] == "VISIBLE" and point["visible"] and point["in_frame"] and point["front_facing"])
                error_mm = None
                invalid_reason = ""
                if available:
                    if not runtime_depth["predicted_uv_in_frame"]:
                        invalid_reason = "PREDICTED_OUT_OF_FRAME"
                    elif not runtime_depth["depth_valid_at_predicted_uv"]:
                        invalid_reason = "INVALID_DEPTH"
                    else:
                        z = runtime_depth["depth_z_m_at_predicted_uv"]
                        xyz = np.asarray([(u - intr["cx"]) * z / intr["fx"], (v - intr["cy"]) * z / intr["fy"], z])
                        error_mm = float(np.linalg.norm(xyz - np.asarray(point["xyz_camera_opencv_m"])) * 1000.0)
                row = {
                    "partition": partition,
                    "locator_model": split,
                    "sample_id": sample_row["sample_id"],
                    "body_geometry_id": sample_row["case_id"],
                    "camera_id": sample_row["camera_id"],
                    "camera_kind": sample_row["camera_kind"],
                    "point_id": point["point_id"],
                    "gt_visibility_reason": point["visibility_reason"],
                    "gt_available_for_3d": available,
                    "final_3d_error_mm": error_mm,
                    "bad20": bool(error_mm is not None and error_mm > 20.0),
                    "bad30": bool(error_mm is not None and error_mm > 30.0),
                    "bad50": bool(error_mm is not None and error_mm > 50.0),
                    "invalid_prediction_reason": invalid_reason,
                    "predicted_u_original_px": u,
                    "predicted_v_original_px": v,
                    "predicted_edge_distance_px": min(u, v, WIDTH - u, HEIGHT - v),
                    "branch_requested": bool(decoded["branch_requested"][i, j]),
                    "branch_used": bool(decoded["branch_used"][i, j]),
                    "branch_requested_x": bool(decoded["branch_requested_x"][i, j]),
                    "branch_requested_y": bool(decoded["branch_requested_y"][i, j]),
                    "branch_used_x": bool(decoded["branch_used_x"][i, j]),
                    "branch_used_y": bool(decoded["branch_used_y"][i, j]),
                    "fallback_code": int(decoded["fallback_code"][i, j]),
                    "correction_magnitude_original_px": float(decoded["correction_magnitude_original_px"][i, j]),
                    "curvature_x": float(decoded["curvature_x"][i, j]),
                    "curvature_y": float(decoded["curvature_y"][i, j]),
                    **{name: float(values[i, j]) for name, values in prob_features.items()},
                    **runtime_depth,
                }
                rows.append(row)
        csv_path = root / "runtime_features" / partition / f"{split}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        reports[split] = {
            "weight": {"path": str(state_path), "sha256": sha(state_path)},
            "prediction": {"path": str(prediction_path), "sha256": sha(prediction_path)},
            "features": {"path": str(csv_path), "sha256": sha(csv_path)},
            "row_count": len(rows),
            "body_count": len({row["body_geometry_id"] for row in rows}),
            "available_count": sum(row["gt_available_for_3d"] for row in rows),
            "unavailable_count": sum(not row["gt_available_for_3d"] for row in rows),
            "bad30_count": sum(row["bad30"] for row in rows),
            "invalid_3d_count": sum(bool(row["invalid_prediction_reason"]) for row in rows),
            "logits_finite": bool(np.isfinite(logits).all()),
        }
        print(partition, split, reports[split], flush=True)
    report = {
        "schema": "frozen-locator-runtime-feature-extraction-v1",
        "partition": partition,
        "passed": all(item["logits_finite"] and item["row_count"] == len(selected) * 20 for item in reports.values()),
        "sample_count": len(selected),
        "reports": reports,
        "untouched_test_inference_not_generated": not (root / "locator_predictions" / "UNTOUCHED_TEST").exists(),
        "reliability_model_trained": False,
    }
    write(root / f"{partition.lower()}_runtime_feature_report.json", report)
    if not report["passed"]:
        raise SystemExit(3)
    return report


def freeze_contract(root: Path) -> None:
    train = read(root / "reliability_train_runtime_feature_report.json")
    calibration = read(root / "calibration_runtime_feature_report.json")
    runtime_features = [
        "logit_peak",
        "probability_peak",
        "probability_top1_top2_gap",
        "entropy_nats",
        "entropy_normalized",
        "local_3x3_probability_mass",
        "heatmap_std_x_cells",
        "heatmap_std_y_cells",
        "predicted_u_original_px",
        "predicted_v_original_px",
        "predicted_edge_distance_px",
        "branch_requested",
        "branch_used",
        "branch_requested_x",
        "branch_requested_y",
        "branch_used_x",
        "branch_used_y",
        "fallback_code",
        "correction_magnitude_original_px",
        "curvature_x",
        "curvature_y",
        "predicted_uv_in_frame",
        "depth_valid_at_predicted_uv",
        "depth_z_m_at_predicted_uv",
        "local_depth_valid_fraction_5x5",
        "local_depth_std_m_5x5",
        "local_depth_range_m_5x5",
    ]
    target_only = [
        "gt_visibility_reason",
        "gt_available_for_3d",
        "final_3d_error_mm",
        "bad20",
        "bad30",
        "bad50",
        "invalid_prediction_reason",
    ]
    grouping_only = ["sample_id", "body_geometry_id", "camera_id", "camera_kind", "point_id", "partition", "locator_model"]
    checks = {
        "train_features_passed": train["passed"],
        "calibration_features_passed": calibration["passed"],
        "three_locators_kept_separate": set(train["reports"]) == set(SPLITS) == set(calibration["reports"]),
        "untouched_test_inference_absent": not (root / "locator_predictions" / "UNTOUCHED_TEST").exists(),
        "no_reliability_model_exists": not list(root.rglob("reliability_model*")),
    }
    contract = {
        "schema": "reliability-runtime-feature-contract-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "runtime_input_features": runtime_features,
        "target_or_evaluation_only": target_only,
        "grouping_only_not_model_inputs": grouping_only,
        "prohibited_model_inputs": [
            "GT Skin Mask",
            "GT visibility or coordinates",
            "final error or BAD labels",
            "sample/body/camera/point IDs",
            "synthetic-only metadata",
            "data from the locked untouched-test partition",
        ],
        "model_policy": "Train and calibrate one reliability model per frozen locator; never pool rows from the three locators.",
        "untouched_test_lock": "No locator inference, feature extraction, feature selection, reliability training or calibration may access UNTOUCHED_TEST until the reliability model and decision thresholds are frozen.",
        "medical_truth": False,
        "production_or_robot_use": False,
    }
    path = root / "RUNTIME_FEATURE_CONTRACT_V1.json"
    write(path, contract)
    receipt = {
        "schema": "runtime-feature-contract-freeze-receipt-v1",
        "passed": contract["passed"],
        "runtime_feature_contract_sha256": sha(path),
        "selected_dataset_manifest_sha256": sha(root / "selected_dataset_manifest.json"),
        "train_feature_report_sha256": sha(root / "reliability_train_runtime_feature_report.json"),
        "calibration_feature_report_sha256": sha(root / "calibration_runtime_feature_report.json"),
        "untouched_test_inference_absent_at_freeze": checks["untouched_test_inference_absent"],
        "reliability_training_authorized": contract["passed"],
        "untouched_test_authorized": False,
    }
    write(root / "runtime_feature_contract_freeze_receipt.json", receipt)
    print(json.dumps({"passed": receipt["passed"], "contract_sha256": receipt["runtime_feature_contract_sha256"], "untouched_locked": receipt["untouched_test_inference_absent_at_freeze"]}, indent=2))
    if not receipt["passed"]:
        raise SystemExit(4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("extract", "freeze"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--weights-root", type=Path)
    parser.add_argument("--partition", choices=PARTITIONS)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "extract":
        if args.weights_root is None or args.partition is None:
            raise SystemExit("--weights-root and --partition are required")
        infer_partition(root, args.weights_root.resolve(), args.partition)
    else:
        freeze_contract(root)


if __name__ == "__main__":
    main()
