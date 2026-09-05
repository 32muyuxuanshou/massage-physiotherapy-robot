from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("phase", choices=("validation", "untouched_test")); parser.add_argument("--root", required=True, type=Path); parser.add_argument("--python", required=True, type=Path); parser.add_argument("--weights-root", required=True, type=Path); args = parser.parse_args()
    root = args.root.resolve(); files = {split: root / args.phase / "predictions" / f"{split}.npz" for split in SPLITS}
    before = {split: sha(path) for split, path in files.items()}
    subprocess.run([str(args.python), str(Path(__file__).resolve().parent / "infer_decoder_gate.py"), args.phase,
                    "--root", str(root), "--weights-root", str(args.weights_root.resolve())], check=True)
    after = {split: sha(path) for split, path in files.items()}
    checks = {f"{split}_prediction_hash_equal": before[split] == after[split] for split in SPLITS}
    payload = {"schema": f"decoder-{args.phase}-determinism-v1", "passed": all(checks.values()), "checks": checks, "before": before, "after": after}
    (root / f"{args.phase}_decoder_determinism.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(payload)
    if not payload["passed"]: raise SystemExit(2)


if __name__ == "__main__": main()
