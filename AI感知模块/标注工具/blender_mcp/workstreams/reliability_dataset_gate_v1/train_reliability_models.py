from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
HERE = Path(__file__).resolve().parent
DESIGN = HERE / "RELIABILITY_MODEL_DESIGN_V1.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(value: str) -> float:
    if value == "True":
        return 1.0
    if value == "False":
        return 0.0
    if value == "" or value.lower() in ("nan", "none"):
        return float("nan")
    return float(value)


def rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def auc(y: np.ndarray, score: np.ndarray) -> float | None:
    pos = score[y == 1]
    neg = score[y == 0]
    if not len(pos) or not len(neg):
        return None
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    recall_pos = tp / (tp + fn) if tp + fn else None
    recall_neg = tn / (tn + fp) if tn + fp else None
    balanced = (recall_pos + recall_neg) / 2 if recall_pos is not None and recall_neg is not None else None
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn, "positive_recall": recall_pos, "negative_recall": recall_neg, "balanced_accuracy": balanced}


def threshold_availability(y: np.ndarray, prob: np.ndarray) -> tuple[float, dict]:
    candidates = np.unique(np.concatenate(([0.0], prob, [1.0])))
    evaluated = []
    for threshold in candidates:
        result = metrics(y, (prob >= threshold).astype(np.uint8))
        evaluated.append((float(threshold), result))
    feasible = [item for item in evaluated if item[1]["negative_recall"] is not None and item[1]["negative_recall"] >= 0.90]
    if feasible:
        chosen = max(feasible, key=lambda item: (item[1]["positive_recall"], item[1]["balanced_accuracy"], item[0]))
        rule = "UNAVAILABLE_RECALL_GE_0.90_MAX_AVAILABLE_RECALL"
    else:
        chosen = max(evaluated, key=lambda item: (item[1]["balanced_accuracy"], item[0]))
        rule = "FALLBACK_MAX_BALANCED_ACCURACY"
    return chosen[0], {**chosen[1], "selection_rule": rule}


def threshold_bad30(y: np.ndarray, prob: np.ndarray) -> tuple[float, dict]:
    candidates = np.unique(np.concatenate(([0.0], prob, [1.0])))
    evaluated = []
    for threshold in candidates:
        result = metrics(y, (prob >= threshold).astype(np.uint8))
        evaluated.append((float(threshold), result))
    feasible = [item for item in evaluated if item[1]["positive_recall"] is not None and item[1]["positive_recall"] >= 0.80]
    if feasible:
        chosen = max(feasible, key=lambda item: (item[1]["negative_recall"], item[1]["balanced_accuracy"], -item[0]))
        rule = "BAD30_RECALL_GE_0.80_MAX_SAFE_ACCEPTANCE"
    else:
        chosen = max(evaluated, key=lambda item: (item[1]["balanced_accuracy"], -item[0]))
        rule = "FALLBACK_MAX_BALANCED_ACCURACY"
    return chosen[0], {**chosen[1], "selection_rule": rule}


def prepare_matrix(data: list[dict], features: list[str], medians: np.ndarray | None = None, means: np.ndarray | None = None, stds: np.ndarray | None = None):
    raw = np.asarray([[parse(row[name]) for name in features] for row in data], dtype=np.float64)
    if medians is None:
        medians = np.nanmedian(raw, axis=0)
        medians = np.where(np.isfinite(medians), medians, 0.0)
    imputed = np.where(np.isfinite(raw), raw, medians[None, :])
    if means is None:
        means = imputed.mean(axis=0)
    if stds is None:
        stds = imputed.std(axis=0)
        stds = np.where(stds >= 1e-8, stds, 1.0)
    return (imputed - means[None, :]) / stds[None, :], medians, means, stds


def sample_weights(data: list[dict], y: np.ndarray) -> np.ndarray:
    bodies = Counter(row["body_geometry_id"] for row in data)
    body_weight = np.asarray([1.0 / bodies[row["body_geometry_id"]] for row in data], np.float64)
    counts = np.bincount(y.astype(np.int64), minlength=2)
    class_weight = np.asarray([len(y) / (2.0 * max(count, 1)) for count in counts], np.float64)
    result = body_weight * class_weight[y.astype(np.int64)]
    return result / result.mean()


def fit_logistic(x: np.ndarray, y: np.ndarray, weight: np.ndarray) -> tuple[np.ndarray, float, list[float]]:
    torch.manual_seed(2026090204)
    xt = torch.tensor(x, dtype=torch.float64)
    yt = torch.tensor(y, dtype=torch.float64)
    wt = torch.tensor(weight, dtype=torch.float64)
    coef = torch.zeros(x.shape[1], dtype=torch.float64, requires_grad=True)
    intercept = torch.zeros((), dtype=torch.float64, requires_grad=True)
    optimizer = torch.optim.LBFGS([coef, intercept], lr=1.0, max_iter=250, tolerance_grad=1e-10, tolerance_change=1e-12, line_search_fn="strong_wolfe")
    history = []

    def closure():
        optimizer.zero_grad()
        logits = xt @ coef + intercept
        loss_rows = torch.nn.functional.binary_cross_entropy_with_logits(logits, yt, reduction="none")
        loss = (loss_rows * wt).mean() + 0.001 * (coef * coef).sum()
        loss.backward()
        history.append(float(loss.detach()))
        return loss

    optimizer.step(closure)
    return coef.detach().numpy(), float(intercept.detach()), history


def predict(x: np.ndarray, coef: np.ndarray, intercept: float) -> np.ndarray:
    z = np.clip(x @ coef + intercept, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-z))


def train_one(root: Path, split: str, features: list[str]) -> dict:
    train_rows = rows(root / "runtime_features" / "RELIABILITY_TRAIN" / f"{split}.csv")
    cal_rows = rows(root / "runtime_features" / "CALIBRATION" / f"{split}.csv")
    x_train, medians, means, stds = prepare_matrix(train_rows, features)
    x_cal, _, _, _ = prepare_matrix(cal_rows, features, medians, means, stds)
    output = root / "reliability_models" / split
    output.mkdir(parents=True, exist_ok=True)
    model_reports = {}
    thresholds = {}
    for model_name in ("availability", "bad30"):
        if model_name == "availability":
            train_mask = np.ones(len(train_rows), dtype=bool)
            cal_mask = np.ones(len(cal_rows), dtype=bool)
            y_train = np.asarray([row["gt_available_for_3d"] == "True" for row in train_rows], np.uint8)
            y_cal = np.asarray([row["gt_available_for_3d"] == "True" for row in cal_rows], np.uint8)
        else:
            train_mask = np.asarray([row["gt_available_for_3d"] == "True" for row in train_rows])
            cal_mask = np.asarray([row["gt_available_for_3d"] == "True" for row in cal_rows])
            y_train = np.asarray([row["bad30"] == "True" for row in train_rows], np.uint8)[train_mask]
            y_cal = np.asarray([row["bad30"] == "True" for row in cal_rows], np.uint8)[cal_mask]
        selected_train = [row for row, keep in zip(train_rows, train_mask) if keep]
        selected_cal = [row for row, keep in zip(cal_rows, cal_mask) if keep]
        weights = sample_weights(selected_train, y_train)
        coef, intercept, history = fit_logistic(x_train[train_mask], y_train, weights)
        p_train = predict(x_train[train_mask], coef, intercept)
        p_cal = predict(x_cal[cal_mask], coef, intercept)
        if model_name == "availability":
            threshold, threshold_metrics = threshold_availability(y_cal, p_cal)
        else:
            threshold, threshold_metrics = threshold_bad30(y_cal, p_cal)
        model = {
            "schema": "weighted-logistic-reliability-model-v1",
            "locator_model": split,
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
        write_json(model_path, model)
        thresholds[model_name] = {"threshold": threshold, "calibration_metrics": threshold_metrics}
        model_reports[model_name] = {
            "model": {"path": str(model_path), "sha256": sha(model_path)},
            "train_auc": auc(y_train, p_train),
            "calibration_auc": auc(y_cal, p_cal),
            "train_positive_count": int(y_train.sum()),
            "calibration_positive_count": int(y_cal.sum()),
            "optimizer_final_loss": history[-1],
            "optimizer_evaluations": len(history),
        }
    threshold_path = output / "thresholds.json"
    write_json(threshold_path, {"schema": "reliability-calibration-thresholds-v1", "locator_model": split, "thresholds": thresholds})

    availability_model = read_json(output / "availability_model.json")
    bad_model = read_json(output / "bad30_model.json")
    p_avail = predict(x_cal, np.asarray(availability_model["coefficients"]), availability_model["intercept"])
    p_bad = predict(x_cal, np.asarray(bad_model["coefficients"]), bad_model["intercept"])
    accept = (p_avail >= thresholds["availability"]["threshold"]) & (p_bad < thresholds["bad30"]["threshold"])
    gt_available = np.asarray([row["gt_available_for_3d"] == "True" for row in cal_rows])
    bad30 = np.asarray([row["bad30"] == "True" for row in cal_rows])
    accepted_available = accept & gt_available
    combined = {
        "calibration_total_rows": len(cal_rows),
        "accepted_rows": int(accept.sum()),
        "accepted_fraction": float(accept.mean()),
        "unavailable_false_accepts": int((accept & ~gt_available).sum()),
        "bad30_false_accepts": int((accepted_available & bad30).sum()),
        "accepted_available_rows": int(accepted_available.sum()),
        "observed_bad30_rate_among_accepted_available": float((accepted_available & bad30).sum() / max(accepted_available.sum(), 1)),
    }
    report = {
        "schema": "reliability-model-training-report-v1",
        "locator_model": split,
        "passed": all(value["calibration_auc"] is not None for value in model_reports.values()),
        "models": model_reports,
        "thresholds": {"path": str(threshold_path), "sha256": sha(threshold_path), "values": thresholds},
        "combined_calibration": combined,
        "pooled_with_other_locators": False,
        "untouched_test_accessed": False,
    }
    write_json(output / "training_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    receipt = read_json(root / "runtime_feature_contract_freeze_receipt.json")
    if not receipt["passed"] or not receipt["reliability_training_authorized"]:
        raise RuntimeError("Runtime feature contract did not authorize training")
    if (root / "locator_predictions" / "UNTOUCHED_TEST").exists():
        raise RuntimeError("Untouched-test inference must remain absent before model freeze")
    shutil.copy2(DESIGN, root / DESIGN.name)
    contract = read_json(root / "RUNTIME_FEATURE_CONTRACT_V1.json")
    features = contract["runtime_input_features"]
    reports = {split: train_one(root, split, features) for split in SPLITS}
    checks = {
        "three_independent_reports_passed": all(report["passed"] for report in reports.values()),
        "no_pooling": all(not report["pooled_with_other_locators"] for report in reports.values()),
        "untouched_test_not_accessed": all(not report["untouched_test_accessed"] for report in reports.values())
        and not (root / "locator_predictions" / "UNTOUCHED_TEST").exists(),
        "six_models_exist": len(list((root / "reliability_models").rglob("*_model.json"))) == 6,
        "three_threshold_files_exist": len(list((root / "reliability_models").glob("*/thresholds.json"))) == 3,
    }
    protected = {}
    for path in sorted((root / "reliability_models").rglob("*.json")):
        protected[str(path.relative_to(root))] = {"path": str(path), "sha256": sha(path)}
    receipt_out = {
        "schema": "reliability-model-and-threshold-freeze-receipt-v1",
        "passed": all(checks.values()),
        "status": "RELIABILITY_MODELS_AND_THRESHOLDS_FROZEN" if all(checks.values()) else "FREEZE_FAILED",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "design": {"path": str(root / DESIGN.name), "sha256": sha(root / DESIGN.name)},
        "runtime_feature_contract_sha256": receipt["runtime_feature_contract_sha256"],
        "protected_models_and_reports": protected,
        "untouched_test_inference_authorized": all(checks.values()),
        "production_or_robot_use_authorized": False,
    }
    write_json(root / "reliability_model_freeze_receipt.json", receipt_out)
    print(json.dumps({"passed": receipt_out["passed"], "reports": {split: reports[split]["combined_calibration"] for split in SPLITS}}, ensure_ascii=False, indent=2))
    if not receipt_out["passed"]:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
