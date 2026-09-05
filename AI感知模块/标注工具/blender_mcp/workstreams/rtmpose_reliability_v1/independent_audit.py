from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


LOCATORS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def value(text: str) -> float:
    if text == "True":
        return 1.0
    if text == "False":
        return 0.0
    if text == "" or text.lower() in ("nan", "none"):
        return float("nan")
    return float(text)


def probability(data: list[dict], model: dict) -> np.ndarray:
    raw = np.asarray([[value(row[name]) for name in model["features"]] for row in data], np.float64)
    median = np.asarray(model["median_imputation"], np.float64)
    matrix = np.where(np.isfinite(raw), raw, median[None, :])
    matrix = (matrix - np.asarray(model["mean"])) / np.asarray(model["std"])
    z = np.clip(matrix @ np.asarray(model["coefficients"]) + float(model["intercept"]), -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-z))


def fraction(numerator: np.ndarray, population: np.ndarray) -> float:
    return float(numerator.sum() / max(population.sum(), 1))


def recompute(root: Path, locator: str) -> dict:
    data = rows(root / "runtime_features" / "UNTOUCHED_TEST" / f"{locator}.csv")
    model_root = root / "reliability_models" / locator
    thresholds = read(model_root / "thresholds.json")["thresholds"]
    p_available = probability(data, read(model_root / "availability_model.json"))
    p_bad15 = probability(data, read(model_root / "bad15_model.json"))
    available = np.asarray([row["gt_available_for_3d"] == "True" for row in data])
    unavailable = ~available
    bad15 = np.asarray([row["bad15"] == "True" for row in data])
    bad30 = np.asarray([row["bad30"] == "True" for row in data])
    invalid = np.asarray([bool(row["invalid_prediction_reason"]) for row in data])
    pred_available = p_available >= float(thresholds["availability"]["threshold"])
    pred_bad15 = p_bad15 >= float(thresholds["bad15"]["threshold"])
    accept = pred_available & ~pred_bad15 & ~invalid
    accepted_available = accept & available
    return {
        "availability_available_recall": fraction(pred_available & available, available),
        "availability_unavailable_recall": fraction(~pred_available & unavailable, unavailable),
        "bad15_recall_among_available": fraction(pred_bad15 & available & bad15, available & bad15),
        "combined_accept_fraction": float(accept.mean()),
        "combined_unavailable_false_accept_rate": fraction(accept & unavailable, unavailable),
        "combined_bad15_rate_among_accepted_available": fraction(accepted_available & bad15, accepted_available),
        "combined_bad30_rate_among_accepted_available": fraction(accepted_available & bad30, accepted_available),
        "invalid_predicted_3d": int(invalid.sum()),
        "counts": {
            "rows": len(data),
            "available": int(available.sum()),
            "unavailable": int(unavailable.sum()),
            "bad15": int((available & bad15).sum()),
            "bad30": int((available & bad30).sum()),
            "accepted": int(accept.sum()),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    report = read(root / "untouched_evaluation.json")
    freeze = read(root / "reliability_model_freeze_receipt.json")
    hash_checks = {
        relative: (root / relative).is_file() and sha(root / relative) == item["sha256"]
        for relative, item in freeze["protected_models_and_reports"].items()
    }
    recomputed = {locator: recompute(root, locator) for locator in LOCATORS}
    comparisons = {}
    for locator in LOCATORS:
        expected = report["results"][locator]["metrics"]
        actual = recomputed[locator]
        comparisons[locator] = {
            key: (
                actual[key] == expected[key]
                if isinstance(actual[key], (dict, int))
                else abs(actual[key] - expected[key]) <= 1e-12
            )
            for key in actual
        }
    passed = all(hash_checks.values()) and all(
        all(checks.values()) for checks in comparisons.values()
    )
    output = {
        "schema": "rtmpose-reliability-independent-audit-v1",
        "passed": passed,
        "imports_training_or_evaluation_code": False,
        "frozen_file_hash_checks": hash_checks,
        "metric_comparisons": comparisons,
        "recomputed": recomputed,
    }
    (root / "independent_audit.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"passed": passed}, indent=2))
    if not passed:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
