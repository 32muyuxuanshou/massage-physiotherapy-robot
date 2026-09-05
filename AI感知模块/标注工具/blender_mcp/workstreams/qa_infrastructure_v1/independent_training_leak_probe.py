from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn


class IndependentKeypointMLP(nn.Module):
    def __init__(self, input_dim: int, output_dim: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.GELU(),
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Linear(128, output_dim),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.network(value)


def pixel_error(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.linalg.norm(prediction - target, axis=2).mean())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cache = np.load(args.output / "training_cache.npz", allow_pickle=False)
    state = torch.load(args.output / "model_state.pt", map_location="cpu", weights_only=False)
    rgb = cache["images_rgb"].astype(np.float32) / 255.0
    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    flat = gray.reshape(gray.shape[0], -1)
    mean = state["feature_mean"].numpy()
    std = state["feature_std"].numpy()
    features = (flat - mean) / std
    target = cache["uv"].astype(np.float32)
    point_count = target.shape[1]
    model = IndependentKeypointMLP(features.shape[1], point_count * 2)
    model.load_state_dict(state["model_state"])
    model.eval()

    width = float(state["original_width"])
    height = float(state["original_height"])

    def predict(input_features: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            result = model(torch.from_numpy(input_features)).reshape(len(input_features), point_count, 2).numpy()
        result[..., 0] = (result[..., 0] + 1.0) * 0.5 * width
        result[..., 1] = (result[..., 1] + 1.0) * 0.5 * height
        return result

    original = predict(features)
    permutation = np.roll(np.arange(len(features)), 1)
    shuffled = predict(features[permutation])
    constant = predict(np.zeros_like(features))
    original_error = pixel_error(original, target)
    shuffled_error = pixel_error(shuffled, target)
    constant_error = pixel_error(constant, target)
    checks = {
        "original_mean_error_below_1px": original_error < 1.0,
        "shuffling_rgb_breaks_same_set_fit": shuffled_error > max(5.0, original_error * 10.0),
        "constant_rgb_breaks_same_set_fit": constant_error > max(5.0, original_error * 10.0),
        "state_has_no_sample_id_tensor": "sample_ids" not in state,
    }
    report = {
        "schema": "independent-training-input-leak-probe-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "mean_pixel_error_original_rgb": original_error,
        "mean_pixel_error_shifted_rgb_fixed_labels": shuffled_error,
        "mean_pixel_error_constant_rgb": constant_error,
        "interpretation": "The trained mapping depends on RGB content; sample/profile IDs are not stored in model state. This does not prove generalization.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
