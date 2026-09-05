from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "reliability_dataset_gate_v1"
sys.path.insert(0, str(BASE))
import train_reliability_models as core  # noqa: E402

LOCATORS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
DESIGN = HERE / "RTMPOSE_RELIABILITY_MODEL_DESIGN_V1.json"


def train_one(root: Path, locator: str, features: list[str]) -> dict:
    train_rows = core.rows(root / "runtime_features" / "RELIABILITY_TRAIN" / f"{locator}.csv")
    cal_rows = core.rows(root / "runtime_features" / "CALIBRATION" / f"{locator}.csv")
    x_train, medians, means, stds = core.prepare_matrix(train_rows, features)
    x_cal, _, _, _ = core.prepare_matrix(cal_rows, features, medians, means, stds)
    output = root / "reliability_models" / locator
    output.mkdir(parents=True, exist_ok=False)
    reports, thresholds = {}, {}
    for model_name in ("availability", "bad15"):
        if model_name == "availability":
            train_mask = np.ones(len(train_rows), dtype=bool)
            cal_mask = np.ones(len(cal_rows), dtype=bool)
            y_train = np.asarray([row["gt_available_for_3d"] == "True" for row in train_rows], np.uint8)
            y_cal = np.asarray([row["gt_available_for_3d"] == "True" for row in cal_rows], np.uint8)
        else:
            train_mask = np.asarray([row["gt_available_for_3d"] == "True" for row in train_rows])
            cal_mask = np.asarray([row["gt_available_for_3d"] == "True" for row in cal_rows])
            y_train = np.asarray([row["bad15"] == "True" for row in train_rows], np.uint8)[train_mask]
            y_cal = np.asarray([row["bad15"] == "True" for row in cal_rows], np.uint8)[cal_mask]
        if len(np.unique(y_train)) != 2 or len(np.unique(y_cal)) != 2:
            raise RuntimeError(f"{locator}/{model_name} requires both classes in train and calibration")
        selected_train = [row for row, keep in zip(train_rows, train_mask) if keep]
        selected_cal = [row for row, keep in zip(cal_rows, cal_mask) if keep]
        coef, intercept, history = core.fit_logistic(
            x_train[train_mask],
            y_train,
            core.sample_weights(selected_train, y_train),
        )
        p_train = core.predict(x_train[train_mask], coef, intercept)
        p_cal = core.predict(x_cal[cal_mask], coef, intercept)
        if model_name == "availability":
            threshold, threshold_metrics = core.threshold_availability(y_cal, p_cal)
        else:
            threshold, threshold_metrics = core.threshold_bad30(y_cal, p_cal)
            threshold_metrics["selection_rule"] = threshold_metrics["selection_rule"].replace("BAD30", "BAD15")
        model = {
            "schema": "weighted-logistic-rtmpose-reliability-model-v1",
            "locator_model": locator,
            "model_name": model_name,
            "features": features,
            "median_imputation": medians.tolist(),
            "mean": means.tolist(),
            "std": stds.tolist(),
            "coefficients": coef.tolist(),
            "intercept": intercept,
            "l2": 0.001,
            "training_body_count": len({row["body_geometry_id"] for row in selected_train}),
            "training_row_count": len(selected_train),
            "calibration_body_count": len({row["body_geometry_id"] for row in selected_cal}),
            "calibration_row_count": len(selected_cal),
        }
        model_path = output / f"{model_name}_model.json"
        core.write_json(model_path, model)
        thresholds[model_name] = {"threshold": threshold, "calibration_metrics": threshold_metrics}
        reports[model_name] = {
            "model": {"path": str(model_path), "sha256": core.sha(model_path)},
            "train_auc": core.auc(y_train, p_train),
            "calibration_auc": core.auc(y_cal, p_cal),
            "train_positive_count": int(y_train.sum()),
            "calibration_positive_count": int(y_cal.sum()),
            "optimizer_final_loss": history[-1],
        }
    threshold_path = output / "thresholds.json"
    core.write_json(threshold_path, {
        "schema": "rtmpose-reliability-calibration-thresholds-v1",
        "locator_model": locator,
        "thresholds": thresholds,
    })
    p_avail = core.predict(x_cal, np.asarray(core.read_json(output / "availability_model.json")["coefficients"]), core.read_json(output / "availability_model.json")["intercept"])
    p_bad = core.predict(x_cal, np.asarray(core.read_json(output / "bad15_model.json")["coefficients"]), core.read_json(output / "bad15_model.json")["intercept"])
    gt_available = np.asarray([row["gt_available_for_3d"] == "True" for row in cal_rows])
    gt_bad15 = np.asarray([row["bad15"] == "True" for row in cal_rows])
    accept = (p_avail >= thresholds["availability"]["threshold"]) & (p_bad < thresholds["bad15"]["threshold"])
    accepted_available = accept & gt_available
    report = {
        "schema": "rtmpose-reliability-training-report-v1",
        "locator_model": locator,
        "passed": all(value["calibration_auc"] is not None for value in reports.values()),
        "models": reports,
        "thresholds": {"path": str(threshold_path), "sha256": core.sha(threshold_path), "values": thresholds},
        "combined_calibration": {
            "rows": len(cal_rows),
            "accepted_fraction": float(accept.mean()),
            "unavailable_false_accepts": int((accept & ~gt_available).sum()),
            "bad15_false_accepts": int((accepted_available & gt_bad15).sum()),
            "accepted_available_rows": int(accepted_available.sum()),
            "bad15_rate_among_accepted_available": float((accepted_available & gt_bad15).sum() / max(accepted_available.sum(), 1)),
        },
        "pooled_with_other_locators": False,
        "untouched_test_accessed": False,
    }
    core.write_json(output / "training_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    receipt = core.read_json(root / "runtime_feature_contract_freeze_receipt.json")
    if not receipt["passed"] or not receipt["reliability_training_authorized"]:
        raise RuntimeError("Feature contract did not authorize training")
    if (root / "predictions" / "UNTOUCHED_TEST").exists():
        raise RuntimeError("Untouched predictions must not exist before freeze")
    shutil.copy2(DESIGN, root / DESIGN.name)
    features = core.read_json(root / "RUNTIME_FEATURE_CONTRACT_V1.json")["runtime_input_features"]
    reports = {locator: train_one(root, locator, features) for locator in LOCATORS}
    protected = {}
    for path in sorted((root / "reliability_models").rglob("*.json")):
        protected[str(path.relative_to(root))] = {"path": str(path), "sha256": core.sha(path)}
    checks = {
        "three_independent_reports_passed": all(report["passed"] for report in reports.values()),
        "no_pooling": all(not report["pooled_with_other_locators"] for report in reports.values()),
        "untouched_test_absent": not (root / "predictions" / "UNTOUCHED_TEST").exists(),
        "six_models_exist": len(list((root / "reliability_models").rglob("*_model.json"))) == 6,
    }
    out = {
        "schema": "rtmpose-reliability-model-freeze-receipt-v1",
        "passed": all(checks.values()),
        "status": "RTMPOSE_RELIABILITY_MODELS_AND_THRESHOLDS_FROZEN" if all(checks.values()) else "FREEZE_FAILED",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "design_sha256": core.sha(root / DESIGN.name),
        "runtime_feature_contract_sha256": receipt["runtime_feature_contract_sha256"],
        "protected_models_and_reports": protected,
        "untouched_test_inference_authorized": all(checks.values()),
        "production_or_robot_use_authorized": False,
    }
    core.write_json(root / "reliability_model_freeze_receipt.json", out)
    print(json.dumps({"passed": out["passed"], "calibration": {k: v["combined_calibration"] for k, v in reports.items()}}, indent=2))
    if not out["passed"]:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
