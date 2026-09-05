from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(root: Path, output: Path) -> dict:
    targets = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.resolve() != output.resolve()
    ]
    lines = [f"{sha256(path)}  {path.relative_to(root).as_posix()}" for path in targets]
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return {"entries": len(lines), "manifest_sha256": sha256(output)}


def verify(root: Path, manifest: Path) -> dict:
    missing = []
    mismatches = []
    count = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        target = root / relative
        count += 1
        if not target.is_file():
            missing.append(relative)
        else:
            actual = sha256(target)
            if actual != expected:
                mismatches.append({"path": relative, "expected": expected, "actual": actual})
    return {
        "entries": count,
        "manifest_sha256": sha256(manifest),
        "missing": missing,
        "mismatches": mismatches,
        "passed": not missing and not mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["build", "verify"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = args.manifest or (args.root / "SHA256SUMS.txt")
    result = build(args.root, manifest) if args.mode == "build" else verify(args.root, manifest)
    report = {
        "schema": "delivery-hash-manifest-v1",
        "mode": args.mode,
        "root": str(args.root),
        "manifest": str(manifest),
        **result,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
