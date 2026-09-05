from __future__ import annotations

import argparse
import csv
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn


class KeypointMLP(nn.Module):
    def __init__(self, input_dim: int, point_count: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.GELU(),
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Linear(128, point_count * 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=20260831)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(min(4, max(1, torch.get_num_threads())))
    torch.use_deterministic_algorithms(True)

    cache = np.load(args.cache, allow_pickle=False)
    rgb = cache["images_rgb"].astype(np.float32) / 255.0
    # The only model input is RGB; grayscale conversion is deterministic and
    # deliberately keeps depth/masks/labels/profile IDs outside the network.
    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    flat = gray.reshape(gray.shape[0], -1)
    feature_mean = flat.mean(axis=0, keepdims=True)
    feature_std = flat.std(axis=0, keepdims=True)
    feature_std = np.maximum(feature_std, 1e-4)
    x_np = (flat - feature_mean) / feature_std

    uv = cache["uv"].astype(np.float32)
    width = float(cache["original_width"])
    height = float(cache["original_height"])
    target_np = uv.copy()
    target_np[..., 0] = target_np[..., 0] / width * 2.0 - 1.0
    target_np[..., 1] = target_np[..., 1] / height * 2.0 - 1.0

    x = torch.from_numpy(x_np)
    target = torch.from_numpy(target_np.reshape(target_np.shape[0], -1))
    model = KeypointMLP(x.shape[1], uv.shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=0.0)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)
    loss_fn = nn.SmoothL1Loss(beta=0.01)

    curve = []
    best_mean_error = math.inf
    best_state = None
    started = time.time()
    for epoch in range(args.epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        prediction = model(x)
        loss = loss_fn(prediction, target)
        if epoch < args.epochs:
            loss.backward()
            optimizer.step()
            scheduler.step()

        if epoch % 10 == 0 or epoch == args.epochs:
            with torch.no_grad():
                pred_norm = model(x).reshape(uv.shape[0], uv.shape[1], 2).cpu().numpy()
            pred_uv = pred_norm.copy()
            pred_uv[..., 0] = (pred_uv[..., 0] + 1.0) * 0.5 * width
            pred_uv[..., 1] = (pred_uv[..., 1] + 1.0) * 0.5 * height
            errors = np.linalg.norm(pred_uv - uv, axis=2)
            mean_error = float(errors.mean())
            max_error = float(errors.max())
            curve.append({
                "epoch": epoch,
                "loss": float(loss.detach()),
                "mean_pixel_error": mean_error,
                "max_pixel_error": max_error,
                "lr": float(optimizer.param_groups[0]["lr"]),
            })
            if mean_error < best_mean_error:
                best_mean_error = mean_error
                best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            if mean_error <= 0.20 and max_error <= 1.0 and epoch >= 200:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pred_norm = model(x).reshape(uv.shape[0], uv.shape[1], 2).cpu().numpy()
    pred_uv = pred_norm.copy()
    pred_uv[..., 0] = (pred_uv[..., 0] + 1.0) * 0.5 * width
    pred_uv[..., 1] = (pred_uv[..., 1] + 1.0) * 0.5 * height
    errors = np.linalg.norm(pred_uv - uv, axis=2)

    state = {
        "model_state": model.state_dict(),
        "feature_mean": torch.from_numpy(feature_mean),
        "feature_std": torch.from_numpy(feature_std),
        "input_width": int(rgb.shape[2]),
        "input_height": int(rgb.shape[1]),
        "original_width": int(width),
        "original_height": int(height),
        "point_ids": cache["point_ids"].tolist(),
        "seed": args.seed,
    }
    torch.save(state, args.output / "model_state.pt")
    np.savez_compressed(
        args.output / "predictions.npz",
        predicted_uv=pred_uv.astype(np.float32),
        target_uv=uv.astype(np.float32),
        pixel_errors=errors.astype(np.float32),
        sample_ids=cache["sample_ids"],
        point_ids=cache["point_ids"],
    )
    with (args.output / "training_curve.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(curve[0]))
        writer.writeheader()
        writer.writerows(curve)

    thresholds = [1.0, 2.0, 5.0, 10.0]
    metrics = {
        "schema": "training-pipeline-v1-metrics",
        "purpose": "same-set overfit pipeline check; not generalization",
        "medical_truth": False,
        "model": "small deterministic MLP continuous 2D keypoint regressor",
        "model_input": "RGB only, converted to grayscale and downsampled to 40x32",
        "device": "cpu",
        "torch_version": torch.__version__,
        "seed": args.seed,
        "epochs_completed": curve[-1]["epoch"],
        "elapsed_seconds": time.time() - started,
        "sample_count": int(uv.shape[0]),
        "point_count": int(uv.shape[1]),
        "mean_pixel_error": float(errors.mean()),
        "median_pixel_error": float(np.median(errors)),
        "max_pixel_error": float(errors.max()),
        "per_point_mean_pixel_error": {str(point_id): float(errors[:, index].mean()) for index, point_id in enumerate(cache["point_ids"].tolist())},
        "pck_same_set": {f"@{threshold:.0f}px": float((errors <= threshold).mean()) for threshold in thresholds},
        "claims": {
            "training_pipeline_can_memorize_30_engineering_samples": bool(float(errors.mean()) <= 1.0),
            "generalization": False,
            "medical_accuracy": False,
        },
        "limitations": [
            "All 30 images are used for both optimization and evaluation.",
            "No train/validation split and no augmentation are used.",
            "Current RGB is engineering-quality synthetic imagery.",
            "The 20 labels are engineering references, not doctor-confirmed medical truth.",
        ],
    }
    (args.output / "training_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "training_config.json").write_text(json.dumps({
        "schema": "overfit-training-config-v1",
        "seed": args.seed,
        "requested_epochs": args.epochs,
        "optimizer": "AdamW",
        "learning_rate": 0.002,
        "weight_decay": 0.0,
        "loss": "SmoothL1 beta=0.01 on normalized continuous UV",
        "augmentation": [],
        "horizontal_flip": False,
        "pretrained_weights": False,
        "downloaded_weights": False,
        "device": "CPU",
        "model_inputs": ["RGB pixels only"],
        "prohibited_inputs": ["overlay", "depth", "mask", "labels", "sample/profile IDs"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": metrics["claims"]["training_pipeline_can_memorize_30_engineering_samples"], "mean_px": metrics["mean_pixel_error"], "max_px": metrics["max_pixel_error"], "epochs": metrics["epochs_completed"]}))


if __name__ == "__main__":
    main()
