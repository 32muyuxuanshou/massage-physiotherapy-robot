from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--envelope", type=Path, required=True)
    parser.add_argument("--expected-status", default="ENGINEERING_REFERENCE")
    args = parser.parse_args()

    envelope = json.loads(args.envelope.read_text(encoding="utf-8"))
    artifact = Path(envelope["artifact_path"])
    checks = {
        "artifact_exists": artifact.is_file(),
        "artifact_hash_matches": artifact.is_file() and sha256(artifact) == envelope["artifact_sha256"],
        "status_matches": envelope["truth_status"] == args.expected_status,
        "engineering_not_medical_truth": (
            args.expected_status != "ENGINEERING_REFERENCE"
            or (envelope.get("medical_truth") is False and envelope.get("medical_validated") is False)
        ),
        "point_count_is_20": envelope.get("point_count") == 20,
    }
    report = {
        "schema": "truth-envelope-validation-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "artifact": str(artifact),
        "artifact_sha256": sha256(artifact) if artifact.is_file() else None,
        "truth_status": envelope.get("truth_status"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
