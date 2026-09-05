from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    evaluation = read(root / "untouched_evaluation.json")
    audit = read(root / "independent_audit.json")
    determinism = read(root / "determinism_report.json")
    freeze = read(root / "reliability_model_freeze_receipt.json")
    train = read(root / "reliability_train_runtime_feature_report.json")
    calibration = read(root / "calibration_runtime_feature_report.json")
    untouched = read(root / "untouched_test_runtime_feature_report.json")
    checks = {
        "train_features_passed": train["passed"],
        "calibration_features_passed": calibration["passed"],
        "models_and_thresholds_frozen_before_untouched": freeze["passed"],
        "untouched_features_passed": untouched["passed"],
        "untouched_acceptance_passed": evaluation["passed"],
        "thresholds_not_retuned_on_untouched": not evaluation["thresholds_retuned_on_untouched_test"],
        "independent_metric_recalculation_passed": audit["passed"],
        "fresh_inference_repeat_exact": determinism["passed"],
        "three_locators_kept_separate": len(evaluation["results"]) == 3,
        "invalid_predicted_3d_zero": all(
            item["metrics"]["invalid_predicted_3d"] == 0
            for item in evaluation["results"].values()
        ),
    }
    verification = {
        "schema": "rtmpose-reliability-final-verification-v1",
        "passed": all(checks.values()),
        "status": evaluation["status"] if all(checks.values()) else "FAIL",
        "checks": checks,
        "untouched_test_results": {
            locator: result["metrics"] for locator, result in evaluation["results"].items()
        },
        "medical_truth": False,
        "real_rgbd_validated": False,
        "robot_safe": False,
    }
    (root / "verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            entries.append(f"{sha(path)} *{path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(json.dumps({"passed": verification["passed"], "files_hashed": len(entries)}, indent=2))
    if not verification["passed"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
