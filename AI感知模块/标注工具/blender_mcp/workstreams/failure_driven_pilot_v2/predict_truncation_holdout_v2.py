from __future__ import annotations

import argparse
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


def decode(logits: torch.Tensor) -> torch.Tensor:
    batch, points, heat_h, heat_w = logits.shape
    probability = torch.softmax(logits.flatten(2), dim=2).reshape(batch, points, heat_h, heat_w)
    grid_x = torch.arange(heat_w, dtype=torch.float32).view(1, 1, 1, heat_w)
    grid_y = torch.arange(heat_h, dtype=torch.float32).view(1, 1, heat_h, 1)
    x = (probability * grid_x).sum(dim=(2, 3))
    y = (probability * grid_y).sum(dim=(2, 3))
    return torch.stack(((x + 0.5) / heat_w * 1280, (y + 0.5) / heat_h * 1024), dim=2)


def predict(model_path: Path, images: np.ndarray) -> np.ndarray:
    state = torch.load(model_path, map_location="cpu", weights_only=False)
    if state["architecture"] != "TinyHeatmapNet":
        raise RuntimeError("Architecture changed")
    model = TinyHeatmapNet(len(state["point_ids"]))
    model.load_state_dict(state["model_state"])
    model.eval()
    raw = torch.from_numpy(images.astype(np.float32) / 255.0).permute(0, 3, 1, 2)
    normalized = (raw - state["channel_mean"]) / state["channel_std"]
    chunks = []
    with torch.no_grad():
        for start in range(0, len(images), 24):
            chunks.append(decode(model(normalized[start : start + 24])).cpu())
    return torch.cat(chunks, dim=0).numpy().astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-v2", type=Path, required=True)
    parser.add_argument("--v1-training", type=Path, required=True)
    parser.add_argument("--v2-training", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dataset = args.dataset_v2.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    data = np.load(dataset / "truncation_holdout_v2.npz", allow_pickle=False)
    splits = read_json(dataset / "contracts" / "evaluation_splits_v1.json")
    case_ids = data["case_ids"].astype(str)
    for split_id in SPLITS:
        test_cases = set(splits["splits"][split_id]["test_case_ids"])
        selection = np.asarray([index for index, case_id in enumerate(case_ids) if case_id in test_cases], dtype=np.int64)
        images = data["images_rgb"][selection]
        v1 = predict(args.v1_training / split_id / "model_state.pt", images)
        v2 = predict(args.v2_training / split_id / "model_state.pt", images)
        np.savez_compressed(output / f"{split_id}_predictions.npz", selection=selection, v1_predicted_uv=v1, v2_predicted_uv=v2)
        print(f"{split_id} PREDICTED {selection.size}", flush=True)


if __name__ == "__main__":
    main()
