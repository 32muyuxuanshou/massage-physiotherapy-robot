from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from train_overfit import KeypointMLP


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cache = np.load(args.cache, allow_pickle=False)
    saved = np.load(args.output / "predictions.npz", allow_pickle=False)
    state = torch.load(args.output / "model_state.pt", map_location="cpu", weights_only=False)
    rgb = cache["images_rgb"].astype(np.float32) / 255.0
    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    flat = gray.reshape(gray.shape[0], -1)
    mean = state["feature_mean"].numpy()
    std = state["feature_std"].numpy()
    x = torch.from_numpy((flat - mean) / std)
    point_count = len(state["point_ids"])
    model = KeypointMLP(x.shape[1], point_count)
    model.load_state_dict(state["model_state"])
    model.eval()
    with torch.no_grad():
        pred = model(x).reshape(x.shape[0], point_count, 2).numpy()
    pred[..., 0] = (pred[..., 0] + 1.0) * 0.5 * float(state["original_width"])
    pred[..., 1] = (pred[..., 1] + 1.0) * 0.5 * float(state["original_height"])
    expected = saved["predicted_uv"]
    report = {
        "schema": "independent-inference-replay-v1",
        "fresh_model_instance": True,
        "training_loop_called": False,
        "prediction_shape": list(pred.shape),
        "expected_shape": list(expected.shape),
        "exact_prediction_match": bool(np.array_equal(pred.astype(np.float32), expected)),
        "max_abs_uv_difference_px": float(np.max(np.abs(pred - expected))),
        "model_input": "training_cache.images_rgb only",
        "passed": bool(pred.shape == expected.shape and np.array_equal(pred.astype(np.float32), expected)),
    }
    (args.output / "inference_replay_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
