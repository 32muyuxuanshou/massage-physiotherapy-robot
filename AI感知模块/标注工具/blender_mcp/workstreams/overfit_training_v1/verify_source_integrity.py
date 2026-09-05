from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED = {
    Path(r"E:\项目-按摩理疗机器人\AI感知模块\outputs\交付文件\2026-08-28_20-21-54"): {
        "sha256sums_sha256": "d3634bd82909b3aaccd00cadba91a5adfce007c1a1698ce0eda66de2b0b8b255",
        "entries": 516,
    },
    Path(r"E:\项目-按摩理疗机器人\AI感知模块\outputs\交付文件\2026-08-29_16-21-55"): {
        "sha256sums_sha256": "844c9f269c5de8965d18f9a41152172bdd35184f0f989b7dc705ea0d67971595",
        "entries": 274,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    roots = []
    overall = True
    for root, expected in EXPECTED.items():
        manifest_path = root / "SHA256SUMS.txt"
        manifest_hash = sha256(manifest_path)
        missing = []
        mismatch = []
        rows = [line for line in manifest_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        for row in rows:
            expected_hash, relative = row.split("  ", 1)
            path = root / Path(relative)
            if not path.is_file():
                missing.append(relative)
            elif sha256(path) != expected_hash:
                mismatch.append(relative)
        passed = manifest_hash == expected["sha256sums_sha256"] and len(rows) == expected["entries"] and not missing and not mismatch
        overall &= passed
        roots.append({
            "root": str(root),
            "sha256sums_sha256": manifest_hash,
            "expected_sha256sums_sha256": expected["sha256sums_sha256"],
            "entries": len(rows),
            "expected_entries": expected["entries"],
            "missing": missing,
            "mismatch": mismatch,
            "passed": passed,
        })
    report = {"schema": "c-workstream-source-integrity-v1", "sources_unmodified": overall, "roots": roots, "passed": overall}
    (args.output / "source_integrity_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
