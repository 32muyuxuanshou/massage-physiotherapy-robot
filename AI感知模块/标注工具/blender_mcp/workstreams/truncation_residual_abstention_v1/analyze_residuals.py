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


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stats(values: list[float], unit: str) -> dict:
    a = np.asarray(values, dtype=np.float64)
    if not a.size:
        return {"count": 0, "mean": None, "p95": None, "max": None, "unit": unit}
    return {"count": int(a.size), "mean": float(a.mean()), "p95": float(np.percentile(a, 95)), "max": float(a.max()), "unit": unit}


def rank_auc(labels: np.ndarray, risk_score: np.ndarray) -> float | None:
    labels = labels.astype(bool)
    pos = risk_score[labels]
    neg = risk_score[~labels]
    if not pos.size or not neg.size:
        return None
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (pos.size * neg.size))


def bootstrap_auc(labels: np.ndarray, risk_score: np.ndarray, seed: int = 20260901) -> dict:
    value = rank_auc(labels, risk_score)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(500):
        idx = rng.integers(0, len(labels), len(labels))
        item = rank_auc(labels[idx], risk_score[idx])
        if item is not None:
            draws.append(item)
    return {"auc": value, "bootstrap_95ci": [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))] if draws else None}


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-v2", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence_v2.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    data = np.load(evidence / "truncation_holdout_v2.npz", allow_pickle=False)
    manifest = read_json(evidence / "dataset_manifest.json")
    by_id = {row["sample_id"]: row for row in manifest["truncation_holdout"]}
    point_ids = data["point_ids"].astype(str).tolist()
    sample_ids = data["sample_ids"].astype(str)
    target_uv_all = data["uv"].astype(np.float64)
    visible_all = data["visible"].astype(bool)
    records = []
    buffer_cache = {}
    for split_id in SPLITS:
        diag = np.load(args.diagnostics / f"{split_id}_heatmap_diagnostics.npz", allow_pickle=False)
        selection = diag["selection"].astype(np.int64)
        for local, global_index in enumerate(selection):
            row = by_id[sample_ids[global_index]]
            sample_dir = Path(row["gate_sample_directory"])
            cache_key = str(sample_dir)
            if cache_key not in buffer_cache:
                labels = read_json(sample_dir / "labels.json")
                depth = np.load(sample_dir / "scene_depth_z.npy", allow_pickle=False)
                with Image.open(sample_dir / "depth_valid_mask.png") as image:
                    valid = np.asarray(image.convert("L"), dtype=np.uint8)
                with Image.open(sample_dir / "skin_mask.png") as image:
                    skin = np.asarray(image.convert("L"), dtype=np.uint8)
                buffer_cache[cache_key] = labels, depth, valid, skin
            labels, depth, valid, skin = buffer_cache[cache_key]
            k = labels["camera"]["intrinsics"]
            for point_index, point_id in enumerate(point_ids):
                is_visible = bool(visible_all[global_index, point_index])
                target_uv = target_uv_all[global_index, point_index]
                for version in ("v1", "v2"):
                    pred = diag[f"{version}_predicted_uv"][local, point_index].astype(np.float64)
                    error_2d = float(np.linalg.norm(pred - target_uv))
                    error_3d = None
                    invalid_reason = None
                    if is_visible:
                        col, image_row = int(math.floor(pred[0])), int(math.floor(pred[1]))
                        if not (0 <= col < depth.shape[1] and 0 <= image_row < depth.shape[0]):
                            invalid_reason = "PREDICTED_OUT_OF_FRAME"
                        elif depth[image_row, col] <= 0 or valid[image_row, col] != 255:
                            invalid_reason = "INVALID_DEPTH"
                        elif skin[image_row, col] != 255:
                            invalid_reason = "NON_SKIN_FIRST_SURFACE"
                        else:
                            z = float(depth[image_row, col])
                            xyz = np.asarray([(pred[0] - k["cx"]) * z / k["fx"], (pred[1] - k["cy"]) * z / k["fy"], z])
                            target_xyz = np.asarray(labels["points"][point_index]["xyz_camera_opencv_m"], dtype=np.float64)
                            error_3d = float(np.linalg.norm(xyz - target_xyz) * 1000.0)
                    records.append({
                        "split": split_id, "version": version, "sample_id": row["sample_id"], "case_id": row["case_id"],
                        "shape_id": row["shape_id"], "pose_id": row["pose_id"], "camera_id": row["camera_id"],
                        "direction": row["subject_side_clipped"], "severity": row["severity_class"], "point_id": point_id,
                        "point_side": point_id.rsplit("_", 1)[-1], "visible": is_visible, "error_2d_px": error_2d,
                        "error_3d_mm": error_3d, "invalid_3d_reason": invalid_reason,
                        "peak_probability": float(diag[f"{version}_peak_probability"][local, point_index]),
                        "normalized_entropy": float(diag[f"{version}_normalized_entropy"][local, point_index]),
                        "peak_margin": float(diag[f"{version}_peak_margin"][local, point_index]),
                    })
    fields = list(records[0])
    with (output / "point_residuals.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(records)

    report = {"schema": "truncation-residual-breakdown-v1", "medical_truth": False, "splits": {}}
    confidence = {"schema": "heatmap-confidence-abstention-probe-v1", "status": "TEST_SET_DIAGNOSTIC_ONLY_NOT_A_DEPLOYMENT_THRESHOLD", "splits": {}}
    for split_id in SPLITS:
        report["splits"][split_id] = {}
        confidence["splits"][split_id] = {}
        for version in ("v1", "v2"):
            subset = [r for r in records if r["split"] == split_id and r["version"] == version]
            visible = [r for r in subset if r["visible"]]
            valid3d = [r for r in visible if r["error_3d_mm"] is not None]
            groups = {}
            for keys in (("direction",), ("severity",), ("direction", "severity"), ("point_id",), ("pose_id",), ("point_side",)):
                bucket = defaultdict(list)
                for r in visible:
                    bucket["|".join(str(r[k]) for k in keys)].append(r)
                groups["_x_".join(keys)] = {
                    key: {"error_2d": stats([x["error_2d_px"] for x in rows], "px"), "error_3d": stats([x["error_3d_mm"] for x in rows if x["error_3d_mm"] is not None], "mm"), "tail_gt30mm": sum((x["error_3d_mm"] or -1) > 30 for x in rows)}
                    for key, rows in sorted(bucket.items())
                }
            report["splits"][split_id][version] = {
                "visible_2d": stats([r["error_2d_px"] for r in visible], "px"),
                "valid_3d": stats([r["error_3d_mm"] for r in valid3d], "mm"),
                "invalid_3d_count": len(visible) - len(valid3d), "tail_gt30mm": sum(r["error_3d_mm"] > 30 for r in valid3d),
                "groups": groups,
                "worst_v2_points_or_v1_points": sorted(({"point_id": key, **value} for key, value in groups["point_id"].items()), key=lambda x: x["error_2d"]["p95"] or -1, reverse=True)[:8],
            }
            peak = np.asarray([r["peak_probability"] for r in visible])
            entropy = np.asarray([r["normalized_entropy"] for r in visible])
            error2d = np.asarray([r["error_2d_px"] for r in visible])
            valid_for_tail = [r for r in valid3d]
            peak3 = np.asarray([r["peak_probability"] for r in valid_for_tail])
            entropy3 = np.asarray([r["normalized_entropy"] for r in valid_for_tail])
            tail3 = np.asarray([r["error_3d_mm"] > 30 for r in valid_for_tail])
            all_peak = np.asarray([r["peak_probability"] for r in subset])
            all_entropy = np.asarray([r["normalized_entropy"] for r in subset])
            invisible = np.asarray([not r["visible"] for r in subset])
            thresholds = np.quantile(peak, [0.1, 0.25, 0.5, 0.75, 0.9]) if peak.size else []
            curve = []
            for threshold in thresholds:
                retained = peak3 >= threshold
                all_retained = all_peak >= threshold
                curve.append({
                    "peak_threshold": float(threshold), "visible_valid3d_coverage": float(retained.mean()),
                    "retained_tail_gt30mm_rate": float(tail3[retained].mean()) if retained.any() else None,
                    "invisible_false_accept_rate": float(all_retained[invisible].mean()) if invisible.any() else None,
                })
            confidence["splits"][split_id][version] = {
                "visible_error_gt20px_auc": {"low_peak": bootstrap_auc(error2d > 20, -peak), "high_entropy": bootstrap_auc(error2d > 20, entropy)},
                "visible_3d_gt30mm_auc": {"low_peak": bootstrap_auc(tail3, -peak3), "high_entropy": bootstrap_auc(tail3, entropy3)},
                "invisible_auc": {"low_peak": bootstrap_auc(invisible, -all_peak), "high_entropy": bootstrap_auc(invisible, all_entropy)},
                "oracle_test_threshold_curve": curve,
            }
    v2_auc = [confidence["splits"][s]["v2"]["visible_3d_gt30mm_auc"]["low_peak"]["auc"] for s in SPLITS]
    usable = all(value is not None and value >= 0.70 for value in v2_auc)
    decision = {
        "schema": "truncation-residual-decision-gate-v1", "medical_truth": False,
        "stage_status": "PASS_DIAGNOSTIC_COMPLETE",
        "softmax_peak_operational_abstention_ready": False,
        "softmax_peak_auc_ge_0_70_all_splits": usable,
        "decision": "VALIDATE_EXPLICIT_VISIBILITY_CONFIDENCE_HEAD_AND_CAPACITY_ABLATION" if not usable else "BUILD_VALIDATION_CALIBRATED_ABSTENTION_CONTRACT",
        "restrictions": ["No threshold selected on this test holdout may be deployed", "E01-E20 are non-medical engineering points", "No robot-safety claim"],
        "source_hashes": {"dataset": sha256(evidence / "truncation_holdout_v2.npz"), "diagnostics_export": sha256(args.diagnostics / "export_verification.json")},
    }
    write_json(output / "residual_breakdown.json", report)
    write_json(output / "confidence_abstention_probe.json", confidence)
    write_json(output / "decision_gate.json", decision)
    print(json.dumps({"status": decision["stage_status"], "decision": decision["decision"], "v2_tail_auc": v2_auc}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
