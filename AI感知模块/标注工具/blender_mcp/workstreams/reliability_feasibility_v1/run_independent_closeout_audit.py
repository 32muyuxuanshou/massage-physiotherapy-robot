from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
PHASES = ("validation", "untouched_test")
REASONS = (
    "VISIBLE",
    "OUT_OF_FRAME",
    "EXTERNAL_OCCLUDED",
    "SELF_OCCLUDED",
    "BACK_FACING",
    "BEHIND_CAMERA",
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count(rows: list[dict]) -> dict:
    return {
        "point_instances": len(rows),
        "images": len({row["sample_id"] for row in rows}),
        "body_geometries": len({row["body_geometry_id"] for row in rows}),
        "body_geometry_ids": sorted({row["body_geometry_id"] for row in rows}),
    }


def same_count(actual: dict, expected: dict) -> bool:
    return all(actual[key] == expected[key] for key in actual)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--decoder-root", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    decoder_root = args.decoder_root.resolve()

    promotion = read_json(output / "BOUNDARY_HYBRID_V1_PROMOTION_RECEIPT.json")
    contract_v3 = read_json(output / "EVALUATION_CONTRACT_V3.json")
    phase0 = read_json(output / "phase0_verification.json")
    phase1 = read_json(output / "phase1_verification.json")
    exposure = read_json(output / "LOCATOR_EXPOSURE_MATRIX_V1.json")
    events = read_json(output / "RELIABILITY_EVENT_INVENTORY_V1.json")
    leakage = read_json(output / "RUNTIME_FEATURE_LEAKAGE_AUDIT_V1.json")
    decision = read_json(output / "RELIABILITY_DATA_SUFFICIENCY_DECISION_V1.json")

    frozen_contract = decoder_root / "BOUNDARY_HYBRID_DECODER_CONTRACT_V1.json"
    frozen_contract_hash = sha256(frozen_contract)
    expected_contract_hash = "6a3b3a109026e7cee95bea03aff41e09f4ec2c874179fc234689f57ef1c23260"

    with (output / "LOCATOR_EXPOSURE_MATRIX_V1.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        exposure_rows = list(csv.DictReader(stream))
    with (output / "reliability_event_rows.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        event_rows = list(csv.DictReader(stream))

    exposure_recomputed = {}
    for split in SPLITS:
        exposure_recomputed[split] = {}
        for category in ("TRAIN_SEEN", "VAL_SEEN", "TEST_ONLY", "COMPLETELY_UNSEEN"):
            sample_count = sum(row[f"{split}_image"] == category for row in exposure_rows)
            body_ids = {
                row["body_geometry_id"]
                for row in exposure_rows
                if row[f"{split}_body"] == category
            }
            exposure_recomputed[split][category] = {
                "sample_count": sample_count,
                "body_geometry_count": len(body_ids),
            }

    event_mismatches: list[str] = []
    for split in SPLITS:
        for phase in PHASES:
            subset = [
                row
                for row in event_rows
                if row["locator_model"] == split and row["phase"] == phase
            ]
            predicates = {
                "AVAILABLE_WITH_VALID_3D": lambda row: row["available_for_3d_gt"] == "True"
                and row["final_3d_error_mm"] != "",
                "INVALID_PREDICTED_3D": lambda row: row["invalid_prediction_reason"] != "",
                "BAD20": lambda row: row["final_3d_error_mm"] != ""
                and float(row["final_3d_error_mm"]) > 20.0,
                "BAD30": lambda row: row["final_3d_error_mm"] != ""
                and float(row["final_3d_error_mm"]) > 30.0,
                "BAD50": lambda row: row["final_3d_error_mm"] != ""
                and float(row["final_3d_error_mm"]) > 50.0,
            }
            for name, predicate in predicates.items():
                actual = count([row for row in subset if predicate(row)])
                expected = events["reliability_by_locator"][split][phase][name]
                if not same_count(actual, expected):
                    event_mismatches.append(f"{split}/{phase}/{name}")

    availability_mismatches: list[str] = []
    for phase in PHASES:
        subset = [
            row
            for row in event_rows
            if row["locator_model"] == SPLITS[0] and row["phase"] == phase
        ]
        actual_available = count(
            [row for row in subset if row["available_for_3d_gt"] == "True"]
        )
        if not same_count(actual_available, events["availability"][phase]["AVAILABLE_FOR_3D"]):
            availability_mismatches.append(f"{phase}/AVAILABLE_FOR_3D")
        for reason in REASONS:
            actual = count([row for row in subset if row["visibility_reason"] == reason])
            if not same_count(actual, events["availability"][phase][reason]):
                availability_mismatches.append(f"{phase}/{reason}")

    unseen_by_all = sorted(
        {
            row["body_geometry_id"]
            for row in exposure_rows
            if all(row[f"{split}_body"] == "COMPLETELY_UNSEEN" for split in SPLITS)
        }
    )
    expected_unseen = sorted(decision["locator_unseen_body_geometry_ids"])

    prohibited_output_patterns = (
        "reliability_model",
        "risk_model",
        "availability_model",
        "calibrator",
        "reliability_untouched",
    )
    prohibited_outputs = [
        str(path)
        for path in output.rglob("*")
        if path.is_file()
        and any(pattern in path.name.lower() for pattern in prohibited_output_patterns)
    ]

    promotion_references_ok = True
    for key in (
        "frozen_decoder_contract",
        "freeze_receipt",
        "final_untouched_verification",
        "decoder_code",
    ):
        item = promotion[key]
        path = Path(item["path"])
        promotion_references_ok &= path.is_file() and sha256(path) == item["sha256"]
    for group in (
        "frozen_model_weights",
        "validation_predictions",
        "untouched_test_predictions",
    ):
        for item in promotion[group].values():
            path = Path(item["path"])
            promotion_references_ok &= path.is_file() and sha256(path) == item["sha256"]

    checks = {
        "frozen_decoder_contract_hash_unchanged": frozen_contract_hash == expected_contract_hash,
        "promotion_receipt_passed": promotion["passed"] is True,
        "promotion_references_exist_and_match_hashes": promotion_references_ok,
        "phase0_passed": phase0["passed"] is True,
        "phase1_passed": phase1["passed"] is True,
        "evaluation_v3_references_promoted_contract": contract_v3["references"]["decoder_contract"]["sha256"]
        == expected_contract_hash,
        "three_locators_declared_independent": all(
            contract_v3["model_roles"][split]["role"] == "INDEPENDENT_DIAGNOSTIC_REPLICA"
            and contract_v3["model_roles"][split]["may_pool_risk_training_rows"] is False
            for split in SPLITS
        ),
        "exposure_csv_has_760_rows": len(exposure_rows) == 760,
        "exposure_summary_recomputed": exposure_recomputed == exposure["summary"],
        "event_csv_has_expected_2880_rows": len(event_rows) == 2880,
        "event_counts_recomputed": not event_mismatches,
        "availability_counts_recomputed": not availability_mismatches,
        "jointly_unseen_body_ids_recomputed": unseen_by_all == expected_unseen,
        "jointly_unseen_body_count_is_8": len(unseen_by_all) == 8,
        "external_self_backfacing_events_absent": all(
            not decision["availability_reason_body_geometry_coverage"][reason]
            for reason in ("EXTERNAL_OCCLUDED", "SELF_OCCLUDED", "BACK_FACING")
        ),
        "runtime_feature_leakage_audit_passed": leakage["passed"] is True,
        "decision_is_insufficient": decision["decision"]
        == "INSUFFICIENT_NEED_NEW_RELIABILITY_DATA",
        "training_not_authorized": decision["training_authorized"] is False,
        "phase1_records_no_training": phase1["no_model_training_performed"] is True,
        "no_reliability_training_or_test_artifacts": not prohibited_outputs,
    }

    report = {
        "schema": "reliability-feasibility-independent-closeout-audit-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "recomputed": {
            "exposure_rows": len(exposure_rows),
            "event_rows": len(event_rows),
            "jointly_locator_unseen_body_ids": unseen_by_all,
            "exposure_summary": exposure_recomputed,
        },
        "mismatches": {
            "event_inventory": event_mismatches,
            "availability_inventory": availability_mismatches,
            "prohibited_outputs": prohibited_outputs,
        },
        "conclusion": (
            "Phase 0 promotion evidence and Phase 1 feasibility audit are internally consistent. "
            "The current evidence does not support training or calibrating a reliability model."
        ),
    }
    audit_path = output / "independent_closeout_audit.json"
    audit_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"passed": report["passed"], "checks": checks}, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
