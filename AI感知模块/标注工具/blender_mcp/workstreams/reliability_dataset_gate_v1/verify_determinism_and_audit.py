from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract_runtime_features as extraction  # noqa: E402


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def boolean(value: str) -> bool:
    return value == "True"


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def recompute_decisions(root: Path, split: str, gates: dict) -> dict:
    path = root / "untouched_reliability" / f"{split}_decisions.csv"
    rows = read_csv(path)
    thresholds = read(root / "reliability_models" / split / "thresholds.json")["thresholds"]
    gt_available = [boolean(row["gt_available_for_3d"]) for row in rows]
    bad30 = [boolean(row["bad30"]) for row in rows]
    pred_available = [boolean(row["predicted_available"]) for row in rows]
    pred_bad = [boolean(row["predicted_bad30"]) for row in rows]
    accepted = [boolean(row["accepted"]) for row in rows]
    p_avail = [float(row["availability_probability"]) for row in rows]
    p_bad = [float(row["bad30_probability"]) for row in rows]
    threshold_consistent = all(
        pa == (p >= float(thresholds["availability"]["threshold"]))
        and pb == (q >= float(thresholds["bad30"]["threshold"]))
        and ac == (pa and not pb)
        for pa, pb, ac, p, q in zip(pred_available, pred_bad, accepted, p_avail, p_bad)
    )
    available_count = sum(gt_available)
    unavailable_count = len(rows) - available_count
    bad_available_count = sum(a and b for a, b in zip(gt_available, bad30))
    available_recall = sum(a and p for a, p in zip(gt_available, pred_available)) / max(available_count, 1)
    unavailable_recall = sum((not a) and (not p) for a, p in zip(gt_available, pred_available)) / max(unavailable_count, 1)
    bad_recall = sum(a and b and p for a, b, p in zip(gt_available, bad30, pred_bad)) / max(bad_available_count, 1)
    false_unavailable = sum(ac and not a for ac, a in zip(accepted, gt_available))
    accepted_available = sum(ac and a for ac, a in zip(accepted, gt_available))
    accepted_bad = sum(ac and a and b for ac, a, b in zip(accepted, gt_available, bad30))
    values = {
        "availability_available_recall": available_recall,
        "availability_unavailable_recall": unavailable_recall,
        "bad30_recall_among_available": bad_recall,
        "combined_accept_fraction": sum(accepted) / len(rows),
        "combined_unavailable_false_accept_rate": false_unavailable / max(unavailable_count, 1),
        "combined_bad30_rate_among_accepted_available": accepted_bad / max(accepted_available, 1),
    }
    checks = {
        "threshold_and_accept_decisions_consistent": threshold_consistent,
        "availability_unavailable_recall": values["availability_unavailable_recall"] >= gates["availability_unavailable_recall_min"],
        "availability_available_recall": values["availability_available_recall"] >= gates["availability_available_recall_min"],
        "bad30_recall": values["bad30_recall_among_available"] >= gates["bad30_recall_among_available_min"],
        "combined_accept_fraction": values["combined_accept_fraction"] >= gates["combined_accept_fraction_min"],
        "combined_unavailable_false_accept_rate": values["combined_unavailable_false_accept_rate"] <= gates["combined_unavailable_false_accept_rate_max"],
        "combined_bad30_rate": values["combined_bad30_rate_among_accepted_available"] <= gates["combined_bad30_rate_among_accepted_available_max"],
    }
    return {"passed": all(checks.values()), "checks": checks, "metrics": values, "row_count": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--weights-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    repeat = root / "determinism_repeat"
    repeat.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "selected_dataset_manifest.json", repeat / "selected_dataset_manifest.json")
    extraction.infer_partition(repeat, args.weights_root.resolve(), "UNTOUCHED_TEST")
    deterministic = {}
    for split in extraction.SPLITS:
        original_prediction = root / "locator_predictions" / "UNTOUCHED_TEST" / f"{split}.npz"
        repeat_prediction = repeat / "locator_predictions" / "UNTOUCHED_TEST" / f"{split}.npz"
        original_features = root / "runtime_features" / "UNTOUCHED_TEST" / f"{split}.csv"
        repeat_features = repeat / "runtime_features" / "UNTOUCHED_TEST" / f"{split}.csv"
        deterministic[split] = {
            "prediction_hash_equal": sha(original_prediction) == sha(repeat_prediction),
            "feature_csv_hash_equal": sha(original_features) == sha(repeat_features),
            "original_prediction_sha256": sha(original_prediction),
            "repeat_prediction_sha256": sha(repeat_prediction),
            "original_feature_sha256": sha(original_features),
            "repeat_feature_sha256": sha(repeat_features),
        }
    determinism_report = {
        "schema": "untouched-reliability-determinism-v1",
        "passed": all(all(value for key, value in item.items() if key.endswith("_equal")) for item in deterministic.values()),
        "splits": deterministic,
    }
    write(root / "untouched_reliability_determinism.json", determinism_report)

    contract = read(root / "UNTOUCHED_RELIABILITY_ACCEPTANCE_CONTRACT_V1.json")
    evaluation = read(root / "untouched_reliability_evaluation.json")
    model_freeze = read(root / "reliability_model_freeze_receipt.json")
    protected_changed = []
    for name, item in model_freeze["protected_models_and_reports"].items():
        path = Path(item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            protected_changed.append(name)
    recomputed = {
        split: recompute_decisions(root, split, contract["per_locator_hard_gates"])
        for split in extraction.SPLITS
    }
    checks = {
        "dataset_gate_passed": read(root / "verification.json")["passed"],
        "partition_freeze_passed": read(root / "partition_freeze_receipt.json")["passed"],
        "feature_contract_freeze_passed": read(root / "runtime_feature_contract_freeze_receipt.json")["passed"],
        "model_freeze_passed": model_freeze["passed"],
        "frozen_models_unchanged": not protected_changed,
        "untouched_acceptance_contract_predated_results": contract["frozen_before_untouched_locator_inference"] is True,
        "untouched_evaluation_passed": evaluation["passed"],
        "independent_csv_recomputation_passed": all(item["passed"] for item in recomputed.values()),
        "fresh_inference_deterministic": determinism_report["passed"],
        "three_locators_not_pooled": all(
            not read(root / "reliability_models" / split / "training_report.json")["pooled_with_other_locators"]
            for split in extraction.SPLITS
        ),
    }
    audit = {
        "schema": "synthetic-reliability-feasibility-independent-audit-v1",
        "passed": all(checks.values()),
        "status": "PASS_SYNTHETIC_RELIABILITY_FEASIBILITY_V1" if all(checks.values()) else "AUDIT_FAILED",
        "checks": checks,
        "protected_model_changes": protected_changed,
        "recomputed_from_decision_csv": recomputed,
        "limitations": [
            "Only six untouched synthetic Shape-Pose bodies.",
            "Point and image rows are correlated within bodies.",
            "E01-E20 are engineering points, not medical truth.",
            "No real RGB-D, patient, clinical or robot-safety validation.",
        ],
    }
    write(root / "independent_audit.json", audit)
    final = {
        "schema": "reliability-dataset-and-feasibility-closeout-v1",
        "passed": audit["passed"],
        "status": audit["status"],
        "body_count": 24,
        "selected_sample_count": 168,
        "selected_point_instance_count": 3360,
        "independent_locator_count": 3,
        "reliability_model_count": 6,
        "untouched_body_count": 6,
        "medical_truth": False,
        "real_human_validated": False,
        "robot_safe": False,
        "production_use_authorized": False,
        "next_gate": "MODEL_CAPACITY_COMPARISON_OR_REAL_RGBD_DOMAIN_GATE",
    }
    write(root / "final_verification.json", final)
    print(json.dumps({"passed": audit["passed"], "status": audit["status"], "checks": checks}, ensure_ascii=False, indent=2))
    if not audit["passed"]:
        raise SystemExit(6)


if __name__ == "__main__":
    main()
