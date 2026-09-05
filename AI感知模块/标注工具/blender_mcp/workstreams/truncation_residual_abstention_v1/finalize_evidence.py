from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXCLUDED = {"SHA256SUMS.txt"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence.resolve()
    export = read_json(root / "heatmap_diagnostics" / "export_verification.json")
    audit = read_json(root / "independent_audit.json")
    decision = read_json(root / "analysis" / "decision_gate.json")
    protected_manifest = Path(r"E:\项目-按摩理疗机器人\AI感知模块\outputs\内部工程证据\2026-09-01_14-37-04_FAILURE_DRIVEN_PILOT_V2\SHA256SUMS.txt")
    checks = {
        "heatmap_prediction_parity_passed": bool(export["verification"]["passed"]),
        "independent_csv_audit_passed": bool(audit["passed"]),
        "diagnostic_stage_complete": decision["stage_status"] == "PASS_DIAGNOSTIC_COMPLETE",
        "no_operational_threshold_claimed": decision["softmax_peak_operational_abstention_ready"] is False,
        "previous_evidence_manifest_unchanged": sha256(protected_manifest).upper() == "E9AA524E65F8178A282B694540CA4AAB68365411F2451F2F95C942702F4FD367",
    }
    verification = {
        "schema": "truncation-residual-abstention-final-verification-v1",
        "status": "PASS_DIAGNOSTIC_COMPLETE" if all(checks.values()) else "FAIL",
        "checks": checks,
        "medical_truth": False,
        "robot_safety_validated": False,
        "training_performed": False,
    }
    (root / "final_verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.name not in EXCLUDED)
    lines = [f"{sha256(path).upper()} *{path.relative_to(root).as_posix()}" for path in files]
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": verification["status"], "file_count": len(files), "manifest_sha256": sha256(root / "SHA256SUMS.txt").upper()}, ensure_ascii=False))
    if verification["status"] != "PASS_DIAGNOSTIC_COMPLETE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
