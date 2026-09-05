from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "reliability_dataset_gate_v1"
sys.path.insert(0, str(BASE))
import train_reliability_models as core  # noqa: E402

LOCATORS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
CONTRACT = HERE / "UNTOUCHED_ACCEPTANCE_CONTRACT_V1.json"


def load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def probabilities(rows: list[dict], model: dict) -> np.ndarray:
    x, _, _, _ = core.prepare_matrix(
        rows,
        model["features"],
        np.asarray(model["median_imputation"]),
        np.asarray(model["mean"]),
        np.asarray(model["std"]),
    )
    return core.predict(x, np.asarray(model["coefficients"]), float(model["intercept"]))


def ratio(mask: np.ndarray, population: np.ndarray) -> float:
    return float(mask.sum() / max(population.sum(), 1))


def evaluate(root: Path, locator: str, gates: dict) -> dict:
    rows = load_rows(root / "runtime_features" / "UNTOUCHED_TEST" / f"{locator}.csv")
    model_root = root / "reliability_models" / locator
    thresholds = core.read_json(model_root / "thresholds.json")["thresholds"]
    p_available = probabilities(rows, core.read_json(model_root / "availability_model.json"))
    p_bad15 = probabilities(rows, core.read_json(model_root / "bad15_model.json"))
    gt_available = np.asarray([row["gt_available_for_3d"] == "True" for row in rows])
    gt_bad15 = np.asarray([row["bad15"] == "True" for row in rows])
    gt_bad30 = np.asarray([row["bad30"] == "True" for row in rows])
    invalid = np.asarray([bool(row["invalid_prediction_reason"]) for row in rows])
    pred_available = p_available >= float(thresholds["availability"]["threshold"])
    pred_bad15 = p_bad15 >= float(thresholds["bad15"]["threshold"])
    accept = pred_available & ~pred_bad15 & ~invalid
    unavailable = ~gt_available
    available_bad15 = gt_available & gt_bad15
    accepted_available = accept & gt_available
    metrics = {
        "availability_available_recall": ratio(pred_available & gt_available, gt_available),
        "availability_unavailable_recall": ratio(~pred_available & unavailable, unavailable),
        "bad15_recall_among_available": ratio(pred_bad15 & available_bad15, available_bad15),
        "combined_accept_fraction": float(accept.mean()),
        "combined_unavailable_false_accept_rate": ratio(accept & unavailable, unavailable),
        "combined_bad15_rate_among_accepted_available": ratio(accepted_available & gt_bad15, accepted_available),
        "combined_bad30_rate_among_accepted_available": ratio(accepted_available & gt_bad30, accepted_available),
        "invalid_predicted_3d": int(invalid.sum()),
        "counts": {
            "rows": len(rows),
            "available": int(gt_available.sum()),
            "unavailable": int(unavailable.sum()),
            "bad15": int(available_bad15.sum()),
            "bad30": int((gt_available & gt_bad30).sum()),
            "accepted": int(accept.sum()),
        },
    }
    checks = {
        key: (
            metrics[key] >= value if key.endswith("_min")
            else metrics[key.removesuffix("_max")] <= value
        )
        for key, value in {}
    }
    checks = {
        "availability_unavailable_recall": metrics["availability_unavailable_recall"] >= gates["availability_unavailable_recall_min"],
        "availability_available_recall": metrics["availability_available_recall"] >= gates["availability_available_recall_min"],
        "bad15_recall": metrics["bad15_recall_among_available"] >= gates["bad15_recall_among_available_min"],
        "combined_accept_fraction": metrics["combined_accept_fraction"] >= gates["combined_accept_fraction_min"],
        "unavailable_false_accept_rate": metrics["combined_unavailable_false_accept_rate"] <= gates["combined_unavailable_false_accept_rate_max"],
        "bad15_rate_accepted": metrics["combined_bad15_rate_among_accepted_available"] <= gates["combined_bad15_rate_among_accepted_available_max"],
        "bad30_rate_accepted": metrics["combined_bad30_rate_among_accepted_available"] <= gates["combined_bad30_rate_among_accepted_available_max"],
        "invalid_predicted_3d": metrics["invalid_predicted_3d"] <= gates["invalid_predicted_3d_max"],
    }
    return {"passed": all(checks.values()), "checks": checks, "metrics": metrics, "thresholds": thresholds}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    freeze = core.read_json(root / "reliability_model_freeze_receipt.json")
    if not freeze["passed"] or not freeze["untouched_test_inference_authorized"]:
        raise RuntimeError("Models are not frozen")
    changed = [
        relative for relative, item in freeze["protected_models_and_reports"].items()
        if core.sha(root / relative) != item["sha256"]
    ]
    if changed:
        raise RuntimeError(f"Frozen files changed: {changed}")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    results = {locator: evaluate(root, locator, contract["per_locator_hard_gates"]) for locator in LOCATORS}
    passed = all(item["passed"] for item in results.values())
    report = {
        "schema": "rtmpose-reliability-untouched-evaluation-v1",
        "passed": passed,
        "status": contract["decision"]["all_three_pass"] if passed else contract["decision"]["any_fail"],
        "acceptance_contract_sha256": core.sha(CONTRACT),
        "frozen_models_unchanged": not changed,
        "thresholds_retuned_on_untouched_test": False,
        "results": results,
        "medical_truth": False,
        "real_human_validated": False,
        "robot_safe": False,
    }
    core.write_json(root / "untouched_evaluation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(5)


if __name__ == "__main__":
    main()
