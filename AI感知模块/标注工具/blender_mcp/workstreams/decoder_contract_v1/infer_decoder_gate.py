from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from boundary_hybrid_decoder import decode_guarded  # noqa: E402

SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


class TinyHeatmapNet(nn.Module):
    def __init__(self, point_count: int):
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(3, 16, 5, stride=2, padding=2), nn.GroupNorm(4, 16), nn.GELU(),
            nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.GroupNorm(8, 32), nn.GELU(),
            nn.Conv2d(32, 64, 3, padding=1), nn.GroupNorm(8, 64), nn.GELU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.GELU(), nn.Conv2d(64, point_count, 1),
        )
    def forward(self, value: torch.Tensor) -> torch.Tensor: return self.network(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("validation", "untouched_test"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--weights-root", required=True, type=Path)
    parser.add_argument("--curvature-epsilon", type=float, default=1e-8)
    args = parser.parse_args(); root = args.root.resolve()
    if args.phase == "untouched_test" and not (root / "decoder_contract_freeze_receipt.json").is_file():
        raise RuntimeError("Untouched test remains locked")
    data = np.load(root / f"{args.phase}_decoder_cache.npz", allow_pickle=False)
    raw = torch.from_numpy(data["images_rgb"].astype(np.float32) / 255.0).permute(0, 3, 1, 2)
    out = root / args.phase / "predictions"; out.mkdir(parents=True, exist_ok=True)
    report = {"schema": f"decoder-{args.phase}-inference-v1", "splits": {}}
    for split in SPLITS:
        state = torch.load(args.weights_root / split / "model_state.pt", map_location="cpu", weights_only=False)
        model = TinyHeatmapNet(len(state["point_ids"])); model.load_state_dict(state["model_state"]); model.eval()
        normalized = (raw - state["channel_mean"]) / state["channel_std"]
        with torch.no_grad(): logits = model(normalized).cpu().numpy().astype(np.float32)
        decoded = decode_guarded(logits, boundary_cells=4, curvature_epsilon=args.curvature_epsilon,
                                 min_correction_original_px=12.0)
        np.savez_compressed(out / f"{split}.npz", logits=logits, **decoded)
        report["splits"][split] = {
            "logits_finite": bool(np.isfinite(logits).all()),
            "branch_requested": int(decoded["branch_requested"].sum()),
            "branch_used": int(decoded["branch_used"].sum()),
            "fallback_count": int((decoded["fallback_code"] != 0).sum()),
        }
        print(split, report["splits"][split], flush=True)
    report["passed"] = all(item["logits_finite"] for item in report["splits"].values())
    (root / f"{args.phase}_inference_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["passed"]: raise SystemExit(2)


if __name__ == "__main__": main()
