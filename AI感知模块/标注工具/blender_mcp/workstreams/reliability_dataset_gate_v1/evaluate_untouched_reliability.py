from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract_runtime_features as extraction  # noqa: E402
import train_reliability_models as training  # noqa: E402

CONTRACT = HERE / "UNTOUCHED_RELIABILITY_ACCEPTANCE_CONTRACT_V1.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def model_prob(rows: list[dict], model: dict) -> np.ndarray:
    x, _, _, _ = training.prepare_matrix(
        rows,
        model["features"],
        np.asarray(model["median_imputation"], np.float64),
        np.asarray(model["mean"], np.float64),
        np.asarray(model["std"], np.float64),
    )
    return training.predict(x, np.asarray(model["coefficients"], np.float64), float(model["intercept"]))


def count_units(rows: list[dict], mask: np.ndarray) -> dict:
    chosen = [row for row, keep in zip(rows, mask) if keep]
    return {
        "point_instances": len(chosen),
        "images": len({row["sample_id"] for row in chosen}),
        "body_geometries": len({row["body_geometry_id"] for row in chosen}),
        "body_geometry_ids": sorted({row["body_geometry_id"] for row in chosen}),
    }


def evaluate_locator(root: Path, split: str, gates: dict) -> dict:
    rows = read_csv(root / "runtime_features" / "UNTOUCHED_TEST" / f"{split}.csv")
    model_root = root / "reliability_models" / split
    availability_model = read(model_root / "availability_model.json")
    bad_model = read(model_root / "bad30_model.json")
    thresholds = read(model_root / "thresholds.json")["thresholds"]
    p_avail = model_prob(rows, availability_model)
    p_bad = model_prob(rows, bad_model)
    gt_available = np.asarray([row["gt_available_for_3d"] == "True" for row in rows])
    gt_bad30 = np.asarray([row["bad30"] == "True" for row in rows])
    invalid = np.asarray([bool(row["invalid_prediction_reason"]) for row in rows])
    pred_available = p_avail >= float(thresholds["availability"]["threshold"])
    pred_bad = p_bad >= float(thresholds["bad30"]["threshold"])
    accept = pred_available & ~pred_bad & ~invalid
    available_recall = float((pred_available & gt_available).sum() / max(gt_available.sum(), 1))
    unavailable = ~gt_available
    unavailable_recall = float((~pred_available & unavailable).sum() / max(unavailable.sum(), 1))
    bad_available = gt_available & gt_bad30
    bad30_recall = float((pred_bad & bad_available).sum() / max(bad_available.sum(), 1))
    accepted_available = accept & gt_available
    unavailable_false_accept_rate = float((accept & unavailable).sum() / max(unavailable.sum(), 1))
    bad30_rate_accepted = float((accepted_available & gt_bad30).sum() / max(accepted_available.sum(), 1))
    metrics = {
        "availability_available_recall": available_recall,
        "availability_unavailable_recall": unavailable_recall,
        "bad30_recall_among_available": bad30_recall,
        "combined_accept_fraction": float(accept.mean()),
        "combined_unavailable_false_accept_rate": unavailable_false_accept_rate,
        "combined_bad30_rate_among_accepted_available": bad30_rate_accepted,
        "invalid_predicted_3d": int(invalid.sum()),
        "available": count_units(rows, gt_available),
        "unavailable": count_units(rows, unavailable),
        "bad30": count_units(rows, bad_available),
        "accepted": count_units(rows, accept),
        "unavailable_false_accepts": count_units(rows, accept & unavailable),
        "bad30_false_accepts": count_units(rows, accepted_available & gt_bad30),
    }
    checks = {
        "availability_unavailable_recall": unavailable_recall >= gates["availability_unavailable_recall_min"],
        "availability_available_recall": available_recall >= gates["availability_available_recall_min"],
        "bad30_recall": bad30_recall >= gates["bad30_recall_among_available_min"],
        "combined_accept_fraction": metrics["combined_accept_fraction"] >= gates["combined_accept_fraction_min"],
        "combined_unavailable_false_accept_rate": unavailable_false_accept_rate <= gates["combined_unavailable_false_accept_rate_max"],
        "combined_bad30_rate": bad30_rate_accepted <= gates["combined_bad30_rate_among_accepted_available_max"],
        "invalid_predicted_3d": int(invalid.sum()) <= gates["invalid_predicted_3d_max"],
    }
    decision_path = root / "untouched_reliability" / f"{split}_decisions.csv"
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["sample_id", "body_geometry_id", "camera_id", "camera_kind", "point_id", "gt_visibility_reason", "gt_available_for_3d", "final_3d_error_mm", "bad30", "availability_probability", "bad30_probability", "predicted_available", "predicted_bad30", "accepted"]
    with decision_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows):
            writer.writerow({name: row[name] for name in fields[:9]} | {"availability_probability": p_avail[i], "bad30_probability": p_bad[i], "predicted_available": bool(pred_available[i]), "predicted_bad30": bool(pred_bad[i]), "accepted": bool(accept[i])})
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": metrics,
        "thresholds": thresholds,
        "decision_exchange": {"path": str(decision_path), "sha256": sha(decision_path)},
        "models_unchanged": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--weights-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    freeze = read(root / "reliability_model_freeze_receipt.json")
    if not freeze["passed"] or not freeze["untouched_test_inference_authorized"]:
        raise RuntimeError("Reliability models are not frozen")
    changed = []
    for item in freeze["protected_models_and_reports"].values():
        path = Path(item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            changed.append(str(path))
    if changed:
        raise RuntimeError(f"Frozen reliability files changed: {changed}")
    if (root / "locator_predictions" / "UNTOUCHED_TEST").exists():
        raise RuntimeError("Untouched-test inference already exists; refuse implicit rerun")
    shutil.copy2(CONTRACT, root / CONTRACT.name)
    contract_hash_before = sha(root / CONTRACT.name)
    extraction.infer_partition(root, args.weights_root.resolve(), "UNTOUCHED_TEST")
    if sha(root / CONTRACT.name) != contract_hash_before:
        raise RuntimeError("Acceptance contract changed during untouched inference")
    contract = read(root / CONTRACT.name)
    gates = contract["per_locator_hard_gates"]
    results = {split: evaluate_locator(root, split, gates) for split in extraction.SPLITS}
    all_pass = all(result["passed"] for result in results.values())
    report = {
        "schema": "untouched-reliability-evaluation-v1",
        "passed": all_pass,
        "status": contract["decision"]["all_three_pass"] if all_pass else contract["decision"]["any_fail"],
        "acceptance_contract": {"path": str(root / CONTRACT.name), "sha256": contract_hash_before},
        "frozen_models_unchanged": not changed,
        "results": results,
        "thresholds_retuned_on_untouched_test": False,
        "medical_truth": False,
        "real_human_validated": False,
        "robot_safe": False,
    }
    write(root / "untouched_reliability_evaluation.json", report)
    verification = {
        "schema": "untouched-reliability-verification-v1",
        "passed": all_pass,
        "status": report["status"],
        "checks": {
            "acceptance_contract_frozen_before_test": True,
            "frozen_models_unchanged": True,
            "thresholds_not_retuned": True,
            "all_three_locator_gates_passed": all_pass,
        },
        "evaluation_sha256": sha(root / "untouched_reliability_evaluation.json"),
        "production_or_robot_use_authorized": False,
    }
    write(root / "untouched_reliability_verification.json", verification)
    print(json.dumps({"passed": all_pass, "status": report["status"], "results": {split: results[split]["metrics"] for split in extraction.SPLITS}}, ensure_ascii=False, indent=2))
    if not all_pass:
        raise SystemExit(5)


if __name__ == "__main__":
    main()
