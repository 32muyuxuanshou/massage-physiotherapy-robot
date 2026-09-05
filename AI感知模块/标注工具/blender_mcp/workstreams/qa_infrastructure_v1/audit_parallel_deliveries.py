from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path) -> dict[str, Any]:
    manifest = root / "SHA256SUMS.txt"
    missing: list[str] = []
    mismatches: list[dict[str, str]] = []
    listed: set[str] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        listed.add(relative)
        target = root / relative
        if not target.is_file():
            missing.append(relative)
        else:
            actual = sha256(target)
            if actual != expected:
                mismatches.append(
                    {"path": relative, "expected": expected, "actual": actual}
                )
    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest
    }
    unlisted = sorted(actual_files - listed)
    stale_entries = sorted(listed - actual_files)
    passed = not missing and not mismatches and not unlisted and not stale_entries
    return {
        "passed": passed,
        "entries": len(listed),
        "manifest_sha256": sha256(manifest),
        "missing": missing,
        "mismatches": mismatches,
        "unlisted_files": unlisted,
        "stale_entries": stale_entries,
    }


def truth_scan(root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    parse_errors: list[dict[str, str]] = []

    def walk(value: Any, location: str, file: Path) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                child = f"{location}.{key}" if location else key
                if key in {"medical_truth", "medical_validated"} and item is True:
                    findings.append(
                        {
                            "file": str(file),
                            "path": child,
                            "reason": "medical truth flag must remain false",
                        }
                    )
                if isinstance(item, str) and "doctor_annotation" in item.lower():
                    warnings.append(
                        {
                            "file": str(file),
                            "path": child,
                            "reason": "legacy wording; governed by engineering truth envelope",
                        }
                    )
                walk(item, child, file)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{location}[{index}]", file)

    parsed = 0
    for path in sorted(root.rglob("*.json")):
        try:
            data = read_json(path)
        except Exception as exc:  # pragma: no cover - delivery diagnostic
            parse_errors.append({"file": str(path), "error": str(exc)})
            continue
        parsed += 1
        walk(data, "", path)
    return {
        "passed": not findings and not parse_errors,
        "json_files_parsed": parsed,
        "findings": findings,
        "warnings": warnings,
        "parse_errors": parse_errors,
    }


def audit_a(root: Path, contract_hash: str) -> dict[str, Any]:
    verification = read_json(root / "verification.json")
    qualified = read_json(root / "QUALIFIED_SHAPE_PROFILES_FIXED_PRONE_V1.json")
    profiles = qualified["profiles"]
    profile_ids = [profile["profile_id"] for profile in profiles]
    nonzero_counts = {
        profile["profile_id"]: sum(abs(float(value)) > 1e-12 for value in profile["betas"])
        for profile in profiles
    }
    checks = {
        "line_verification_passed": verification.get("passed") is True,
        "baseline_restore_passed": verification.get("baseline_restore_passed") is True,
        "two_fresh_process_determinism_passed": verification.get(
            "two_fresh_process_determinism_passed"
        )
        is True,
        "source_inputs_unchanged": verification.get("source_inputs_unchanged") is True,
        "visual_review_passed": verification.get("visual_review", {}).get("passed") is True,
        "qualified_count_7": len(profiles) == 7,
        "baseline_present": profile_ids.count("S0_BASE") == 1,
        "qualified_combinations_are_2_or_3_dimensional": all(
            count in {2, 3}
            for profile_id, count in nonzero_counts.items()
            if profile_id != "S0_BASE"
        ),
        "rejected_C01_not_qualified": "C01_LONG_UPPER_WIDE" not in profile_ids,
        "contract_matches_F": sha256(root / "body_measurement_contract_v2.json")
        == contract_hash,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "qualified_profile_ids": profile_ids,
        "nonzero_beta_counts": nonzero_counts,
        "hash_manifest": verify_manifest(root),
        "truth_scan": truth_scan(root),
    }


def audit_b(root: Path) -> dict[str, Any]:
    verification = read_json(root / "verification.json")
    visual_review = read_json(root / "visual_review.json")
    qualified = read_json(root / "QUALIFIED_POSE_PROFILES_BASE_SHAPE_V1.json")
    profiles = qualified["profiles"]
    profile_ids = [
        profile
        if isinstance(profile, str)
        else profile.get("pose_id", profile.get("profile_id"))
        for profile in profiles
    ]
    betas = qualified.get("betas", [])
    rejected = {
        "P1_HEAD_NEG20",
        "D02_SCAPULA_ELEVATION_PAIR_NEG6",
        "D04_ELBOW_RIGHT_ASYM_30",
    }
    checks = {
        "line_verification_passed": verification.get("passed") is True,
        "automatic_gates_passed": verification.get("automatic_gates_passed") is True,
        "baseline_restore_passed": verification.get("baseline_restore_passed") is True,
        "determinism_passed": verification.get("determinism_passed") is True,
        "source_inputs_unchanged": verification.get("source_inputs_unchanged") is True,
        "visual_review_passed": verification.get("visual_review") == "PASS"
        and visual_review.get("passed") is True,
        "qualified_count_9": len(profile_ids) == 9,
        "beta_zero_scope": len(betas) == 10 and all(abs(float(value)) <= 1e-12 for value in betas),
        "rejected_profiles_not_qualified": rejected.isdisjoint(profile_ids),
        "shape_x_pose_not_authorized": "SHAPE_X_POSE"
        in qualified.get("next_required_stage", ""),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "qualified_profile_ids": profile_ids,
        "hash_manifest": verify_manifest(root),
        "truth_scan": truth_scan(root),
    }


def audit_c(root: Path) -> dict[str, Any]:
    verification = read_json(root / "verification.json")
    checks = {
        "line_verification_passed": verification.get("passed") is True,
        "medical_truth_false": verification.get("checks", {}).get("medical_truth_false")
        is True,
        "overlay_excluded": verification.get("checks", {}).get(
            "overlay_excluded_from_model_input"
        )
        is True,
        "same_set_overfit_passed": verification.get("checks", {}).get(
            "same_set_overfit_passed"
        )
        is True,
        "predicted_depth_3d_valid": verification.get("checks", {}).get(
            "predicted_uv_depth_3d_all_valid"
        )
        is True,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "headline_metrics": verification.get("headline_metrics", {}),
        "hash_manifest": verify_manifest(root),
        "truth_scan": truth_scan(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("parent", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    f_contract = args.parent / "F_qa" / "body_measurement_contract_v2.json"
    report = {
        "schema": "parallel-abc-independent-audit-v1",
        "A_shape_combination": audit_a(
            args.parent / "A_shape_combination", sha256(f_contract)
        ),
        "B_pose_only": audit_b(args.parent / "B_pose_only"),
        "C_overfit_training": audit_c(args.parent / "C_overfit_training"),
        "scope_limits": [
            "engineering reference points only",
            "no medical validation",
            "no Shape x Pose cross-product",
            "no real-camera validation",
            "no generalization claim",
        ],
    }
    for key in ("A_shape_combination", "B_pose_only", "C_overfit_training"):
        line = report[key]
        line["passed"] = bool(
            line["passed"]
            and line["hash_manifest"]["passed"]
            and line["truth_scan"]["passed"]
        )
    report["passed"] = all(
        report[key]["passed"]
        for key in ("A_shape_combination", "B_pose_only", "C_overfit_training")
    )
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"passed": report["passed"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
