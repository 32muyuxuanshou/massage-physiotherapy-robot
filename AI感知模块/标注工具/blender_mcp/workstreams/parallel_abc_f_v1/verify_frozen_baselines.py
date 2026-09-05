from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "baseline_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha_file(root: Path) -> dict:
    sums_path = root / "SHA256SUMS.txt"
    missing: list[str] = []
    mismatches: list[dict] = []
    count = 0
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        target = root / relative
        count += 1
        if not target.is_file():
            missing.append(relative)
            continue
        actual = sha256(target)
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
    return {
        "entries": count,
        "sha256sums_sha256": sha256(sums_path),
        "missing": missing,
        "mismatches": mismatches,
        "passed": not missing and not mismatches,
    }


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results = []
    passed = True
    for source in manifest["sources"]:
        root = Path(source["path"])
        result = verify_sha_file(root)
        result["role"] = source["role"]
        result["path"] = str(root)
        result["manifest_sha_match"] = (
            result["sha256sums_sha256"] == source["sha256sums_sha256"]
        )
        result["manifest_count_match"] = result["entries"] == source["sha256_entries"]
        result["passed"] = (
            result["passed"]
            and result["manifest_sha_match"]
            and result["manifest_count_match"]
        )
        passed = passed and result["passed"]
        results.append(result)

    report = {
        "schema": "frozen-baseline-verification-v1",
        "passed": passed,
        "manifest": str(MANIFEST),
        "sources": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
