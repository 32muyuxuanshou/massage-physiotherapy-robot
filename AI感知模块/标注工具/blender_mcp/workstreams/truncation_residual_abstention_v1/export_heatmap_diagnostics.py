from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn


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

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.network(value)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def infer(model_path: Path, images: np.ndarray) -> dict[str, np.ndarray]:
    state = torch.load(model_path, map_location="cpu", weights_only=False)
    if state["architecture"] != "TinyHeatmapNet":
        raise RuntimeError(f"Architecture changed: {model_path}")
    model = TinyHeatmapNet(len(state["point_ids"]))
    model.load_state_dict(state["model_state"])
    model.eval()
    raw = torch.from_numpy(images.astype(np.float32) / 255.0).permute(0, 3, 1, 2)
    normalized = (raw - state["channel_mean"]) / state["channel_std"]
    outputs: dict[str, list[torch.Tensor]] = {
        "predicted_uv": [], "peak_probability": [], "normalized_entropy": [], "peak_margin": []
    }
    with torch.no_grad():
        for start in range(0, len(images), 24):
            logits = model(normalized[start : start + 24])
            batch, points, heat_h, heat_w = logits.shape
            flat = torch.softmax(logits.flatten(2), dim=2)
            probability = flat.reshape(batch, points, heat_h, heat_w)
            grid_x = torch.arange(heat_w, dtype=torch.float32).view(1, 1, 1, heat_w)
            grid_y = torch.arange(heat_h, dtype=torch.float32).view(1, 1, heat_h, 1)
            x = (probability * grid_x).sum(dim=(2, 3))
            y = (probability * grid_y).sum(dim=(2, 3))
            uv = torch.stack(((x + 0.5) / heat_w * 1280, (y + 0.5) / heat_h * 1024), dim=2)
            top2 = torch.topk(flat, k=2, dim=2).values
            entropy = -(flat * torch.log(flat.clamp_min(1e-12))).sum(dim=2) / np.log(heat_h * heat_w)
            outputs["predicted_uv"].append(uv.cpu())
            outputs["peak_probability"].append(top2[:, :, 0].cpu())
            outputs["normalized_entropy"].append(entropy.cpu())
            outputs["peak_margin"].append((top2[:, :, 0] - top2[:, :, 1]).cpu())
    return {key: torch.cat(value).numpy().astype(np.float32) for key, value in outputs.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-v2", type=Path, required=True)
    parser.add_argument("--v1-training", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence_v2.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    data = np.load(evidence / "truncation_holdout_v2.npz", allow_pickle=False)
    splits = read_json(evidence / "contracts" / "evaluation_splits_v1.json")
    case_ids = data["case_ids"].astype(str)
    checks = {}
    sources = {"dataset": sha256(evidence / "truncation_holdout_v2.npz"), "models": {}}
    for split_id in SPLITS:
        test_cases = set(splits["splits"][split_id]["test_case_ids"])
        selection = np.asarray([i for i, case_id in enumerate(case_ids) if case_id in test_cases], dtype=np.int64)
        images = data["images_rgb"][selection]
        old = np.load(evidence / "truncation_holdout_predictions" / f"{split_id}_predictions.npz", allow_pickle=False)
        if not np.array_equal(old["selection"], selection):
            raise RuntimeError(f"Selection mismatch: {split_id}")
        payload = {"selection": selection}
        for version, root in (("v1", args.v1_training), ("v2", evidence / "training")):
            model_path = root / split_id / "model_state.pt"
            result = infer(model_path, images)
            reference = old[f"{version}_predicted_uv"]
            max_delta = float(np.max(np.abs(result["predicted_uv"] - reference)))
            checks[f"{split_id}_{version}_prediction_parity_le_1e-5"] = max_delta <= 1e-5
            payload[f"{version}_predicted_uv"] = result["predicted_uv"]
            payload[f"{version}_peak_probability"] = result["peak_probability"]
            payload[f"{version}_normalized_entropy"] = result["normalized_entropy"]
            payload[f"{version}_peak_margin"] = result["peak_margin"]
            sources["models"][f"{split_id}_{version}"] = {"path": str(model_path), "sha256": sha256(model_path), "prediction_parity_max_abs_px": max_delta}
        np.savez_compressed(output / f"{split_id}_heatmap_diagnostics.npz", **payload)
        print(f"{split_id}: {selection.size} samples", flush=True)
    report = {
        "schema": "truncation-residual-heatmap-diagnostics-v1",
        "medical_truth": False,
        "coordinate_space": "original_1280x1024_continuous_pixels",
        "decoder": "SPATIAL_SOFTMAX_EXPECTATION",
        "confidence_status": "DIAGNOSTIC_ONLY_NOT_CALIBRATED",
        "sources": sources,
        "verification": {"passed": all(checks.values()), "checks": checks},
    }
    (output / "export_verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["verification"]["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
