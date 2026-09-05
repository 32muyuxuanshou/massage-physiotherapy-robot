from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from compare_frozen_decoders import SPLITS, infer


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-v2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    root = args.evidence_v2.resolve(); data = np.load(root / "training_cache_v2.npz", allow_pickle=False)
    splits = read_json(root / "contracts" / "evaluation_splits_v1.json"); sample_ids = data["sample_ids"].astype(str)
    by_id = {sample_id: index for index, sample_id in enumerate(sample_ids)}
    report = {"schema": "frozen-v2-main-test-decoder-export-v1", "splits": {}}
    for split in SPLITS:
        selection = np.asarray([by_id[sample_id] for sample_id in splits["splits"][split]["sample_ids"]["test"]], dtype=np.int64)
        decoded = infer(root / "training" / split / "model_state.pt", data["images_rgb"][selection])
        np.savez_compressed(args.output / f"{split}_main_test_decoders.npz", selection=selection, **decoded)
        report["splits"][split] = {"sample_count": int(selection.size)}
        print(f"{split}: {selection.size}", flush=True)
    (args.output / "export_verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
