from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_dataset as gen  # noqa: E402

PARTITIONS = ("RELIABILITY_TRAIN", "CALIBRATION", "UNTOUCHED_TEST")
EXPECTED_BODIES = {"RELIABILITY_TRAIN": 12, "CALIBRATION": 6, "UNTOUCHED_TEST": 6}
EXPECTED_SAMPLES = {"RELIABILITY_TRAIN": 84, "CALIBRATION": 42, "UNTOUCHED_TEST": 42}


def file_ref(path: Path) -> dict:
    return {"path": str(path), "sha256": gen.sha(path), "bytes": path.stat().st_size}


def normalize_reserve(root: Path, report: dict) -> dict:
    sample = Path(report["sample"])
    return {
        "sample_id": report["selected_sample_id"],
        "partition": report["partition"],
        "case_id": report["case_id"],
        "camera_id": report["scenario"]["camera_id"],
        "camera_kind": report["scenario"]["kind"],
        "passed": report["passed"],
        "checks": report["checks"],
        "reason_counts": report["camera_qc"]["reason_counts"],
        "external_details": report["camera_qc"]["external_details"],
        "severity": report["severity"],
        "sample": str(sample),
        "hashes": report["hashes"],
        "is_camera_reserve": True,
        "replaces_sample_id": report["replaces_sample_id"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    freeze = gen.verify_freeze(root)
    reports = {
        partition: gen.read(root / f"{partition.lower()}_generation_report.json")
        for partition in PARTITIONS
    }
    reserve = gen.read(root / "camera_reserve_result.json")
    calibration_failed = [row for row in reports["CALIBRATION"]["samples"] if not row["passed"]]
    selected = []
    for partition in PARTITIONS:
        selected.extend(row for row in reports[partition]["samples"] if row["passed"])
    selected.append(normalize_reserve(root, reserve))
    selected.sort(key=lambda row: (PARTITIONS.index(row["partition"]), row["case_id"], row["camera_id"]))

    body_counts = {
        partition: len({row["case_id"] for row in selected if row["partition"] == partition})
        for partition in PARTITIONS
    }
    sample_counts = Counter(row["partition"] for row in selected)
    per_body = defaultdict(list)
    reasons = {partition: Counter() for partition in PARTITIONS}
    camera_kinds = {partition: Counter() for partition in PARTITIONS}
    hash_failures = []
    for row in selected:
        per_body[(row["partition"], row["case_id"])].append(row["sample_id"])
        reasons[row["partition"]].update(row["reason_counts"])
        camera_kinds[row["partition"]][row["camera_kind"]] += 1
        sample = Path(row["sample"])
        for name, expected in row["hashes"].items():
            path = sample / name
            if not path.is_file() or gen.sha(path) != expected:
                hash_failures.append(f"{row['sample_id']}/{name}")

    selected_ids = {row["sample_id"] for row in selected}
    checks = {
        "partition_freeze_still_valid": freeze["passed"],
        "train_generation_passed": reports["RELIABILITY_TRAIN"]["passed"],
        "untouched_generation_passed": reports["UNTOUCHED_TEST"]["passed"],
        "exactly_one_predeclared_calibration_failure": len(calibration_failed) == 1
        and calibration_failed[0]["sample_id"] == "RCAL_G04__R_LEFT_MILD",
        "camera_reserve_passed": reserve["passed"],
        "failed_sample_not_selected": "RCAL_G04__R_LEFT_MILD" not in selected_ids,
        "reserve_sample_selected": reserve["selected_sample_id"] in selected_ids,
        "exact_body_counts": body_counts == EXPECTED_BODIES,
        "exact_sample_counts": dict(sample_counts) == EXPECTED_SAMPLES,
        "seven_selected_samples_per_body": all(len(values) == 7 for values in per_body.values()),
        "all_selected_rows_passed": all(row["passed"] for row in selected),
        "selected_hashes_match": not hash_failures,
        "external_occlusion_covered_in_every_partition": all(
            reasons[partition]["EXTERNAL_OCCLUDED"] > 0 for partition in PARTITIONS
        ),
        "out_of_frame_covered_in_every_partition": all(
            reasons[partition]["OUT_OF_FRAME"] > 0 for partition in PARTITIONS
        ),
        "normal_oblique_truncation_external_present": all(
            camera_kinds[partition][kind] > 0
            for partition in PARTITIONS
            for kind in ("CONTROL_NORMAL", "CONTROL_OBLIQUE", "TRUNCATION", "EXTERNAL_OCCLUSION")
        ),
        "no_locator_predictions_exist": not list(root.rglob("*prediction*")),
        "no_reliability_model_exists": not list(root.rglob("*model_state*")),
    }
    manifest = {
        "schema": "reliability-dataset-selected-sample-manifest-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "body_counts": body_counts,
        "sample_counts": dict(sample_counts),
        "camera_kind_counts": {k: dict(v) for k, v in camera_kinds.items()},
        "visibility_reason_point_counts": {k: dict(v) for k, v in reasons.items()},
        "selected_samples": selected,
        "excluded_diagnostics": [
            {
                "sample_id": calibration_failed[0]["sample_id"],
                "reason": "Body silhouette was truncated but no E01-E20 target was OUT_OF_FRAME under the fixed mild-left camera.",
                "preserved_path": calibration_failed[0]["sample"],
            }
        ],
        "medical_truth": False,
        "robot_safe": False,
    }
    manifest_path = root / "selected_dataset_manifest.json"
    gen.write(manifest_path, manifest)
    verification = {
        "schema": "reliability-dataset-gate-verification-v1",
        "passed": manifest["passed"],
        "status": "PASS_RELIABILITY_DATASET_GATE_V1" if manifest["passed"] else "FAIL_RELIABILITY_DATASET_GATE_V1",
        "checks": checks,
        "body_count": sum(body_counts.values()),
        "sample_count": sum(sample_counts.values()),
        "point_instance_count": sum(sample_counts.values()) * 20,
        "partition_counts": EXPECTED_BODIES,
        "selected_dataset_manifest_sha256": gen.sha(manifest_path),
        "frozen_before_locator_predictions": True,
        "reliability_feasibility_training_authorized": manifest["passed"],
        "untouched_test_locked_from_training_and_calibration": True,
        "production_or_robot_use_authorized": False,
        "next_stage": "FROZEN_LOCATOR_RUNTIME_FEATURE_EXTRACTION_V1",
    }
    gen.write(root / "verification.json", verification)
    print(json.dumps({"passed": verification["passed"], "body_counts": body_counts, "sample_counts": dict(sample_counts), "reason_counts": {k: dict(v) for k, v in reasons.items()}}, ensure_ascii=False, indent=2))
    if not verification["passed"]:
        print(json.dumps({"hash_failures": hash_failures, "failed_checks": [k for k, v in checks.items() if not v]}, ensure_ascii=False, indent=2))
        raise SystemExit(4)


if __name__ == "__main__":
    main()
