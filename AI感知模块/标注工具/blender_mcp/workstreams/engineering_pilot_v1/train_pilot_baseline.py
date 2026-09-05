from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TinyHeatmapNet(nn.Module):
    def __init__(self, point_count: int):
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(3, 16, 5, stride=2, padding=2),
            nn.GroupNorm(4, 16),
            nn.GELU(),
            nn.Conv2d(16, 32, 3, stride=2, padding=1),
            nn.GroupNorm(8, 32),
            nn.GELU(),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.GroupNorm(8, 64),
            nn.GELU(),
            nn.Conv2d(64, 64, 3, padding=1),
            nn.GELU(),
            nn.Conv2d(64, point_count, 1),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.network(value)


def target_distributions(
    uv: torch.Tensor,
    visible: torch.Tensor,
    width: int,
    height: int,
    heat_w: int,
    heat_h: int,
    sigma: float = 1.35,
) -> torch.Tensor:
    x = uv[..., 0] / width * heat_w - 0.5
    y = uv[..., 1] / height * heat_h - 0.5
    grid_x = torch.arange(heat_w, device=uv.device, dtype=torch.float32).view(1, 1, 1, heat_w)
    grid_y = torch.arange(heat_h, device=uv.device, dtype=torch.float32).view(1, 1, heat_h, 1)
    gaussian = torch.exp(-((grid_x - x[..., None, None]) ** 2 + (grid_y - y[..., None, None]) ** 2) / (2.0 * sigma * sigma))
    gaussian = gaussian * visible[..., None, None]
    normalizer = gaussian.flatten(2).sum(dim=2).clamp_min(1e-12)[..., None, None]
    return gaussian / normalizer


def decode(logits: torch.Tensor, width: int, height: int) -> torch.Tensor:
    batch, points, heat_h, heat_w = logits.shape
    probability = torch.softmax(logits.flatten(2), dim=2).reshape(batch, points, heat_h, heat_w)
    grid_x = torch.arange(heat_w, device=logits.device, dtype=torch.float32).view(1, 1, 1, heat_w)
    grid_y = torch.arange(heat_h, device=logits.device, dtype=torch.float32).view(1, 1, heat_h, 1)
    x = (probability * grid_x).sum(dim=(2, 3))
    y = (probability * grid_y).sum(dim=(2, 3))
    return torch.stack(((x + 0.5) / heat_w * width, (y + 0.5) / heat_h * height), dim=2)


def metric_summary(errors: np.ndarray) -> dict:
    if errors.size == 0:
        return {"count": 0, "mean_px": None, "median_px": None, "max_px": None, "pck": {}}
    return {
        "count": int(errors.size),
        "mean_px": float(errors.mean()),
        "median_px": float(np.median(errors)),
        "max_px": float(errors.max()),
        "pck": {f"@{threshold}px": float((errors <= threshold).mean()) for threshold in (5, 10, 20, 40)},
    }


def grouped_metrics(errors: np.ndarray, visible: np.ndarray, groups: np.ndarray) -> dict:
    output = {}
    for group in sorted(set(groups.tolist())):
        selected = groups == group
        output[str(group)] = metric_summary(errors[selected][visible[selected]])
    return output


def predict(model: nn.Module, images: torch.Tensor, batch_size: int) -> np.ndarray:
    model.eval()
    chunks = []
    with torch.no_grad():
        for start in range(0, len(images), batch_size):
            chunks.append(decode(model(images[start : start + batch_size]), 1280, 1024).cpu())
    return torch.cat(chunks, dim=0).numpy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--split-id", choices=("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260831)
    args = parser.parse_args()
    root = args.dataset.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    qc = read_json(root / "qc_verification.json")
    visual = read_json(root / "visual_review.json")
    splits = read_json(root / "contracts" / "evaluation_splits_v1.json")
    cache_report = read_json(args.cache.with_suffix(".json"))
    if not qc["passed"] or not visual["passed"] or not cache_report["passed"] or sha256(args.cache) != cache_report["cache_sha256"]:
        raise RuntimeError("Training inputs are not frozen and passed")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(min(8, max(1, torch.get_num_threads())))
    torch.use_deterministic_algorithms(True)
    data = np.load(args.cache, allow_pickle=False)
    sample_ids = data["sample_ids"].astype(str)
    split = splits["splits"][args.split_id]
    id_to_index = {sample_id: index for index, sample_id in enumerate(sample_ids.tolist())}
    indices = {
        bucket: np.asarray([id_to_index[sample_id] for sample_id in split["sample_ids"][bucket]], dtype=np.int64)
        for bucket in ("train", "val", "test")
    }
    raw_images = torch.from_numpy(data["images_rgb"].astype(np.float32) / 255.0).permute(0, 3, 1, 2)
    uv = torch.from_numpy(data["uv"].astype(np.float32))
    visible = torch.from_numpy(data["visible"].astype(np.float32))
    channel_mean = raw_images[indices["train"]].mean(dim=(0, 2, 3), keepdim=True)
    channel_std = raw_images[indices["train"]].std(dim=(0, 2, 3), keepdim=True).clamp_min(1e-4)
    images = (raw_images - channel_mean) / channel_std
    challenge_raw = torch.from_numpy(data["challenge_images_rgb"].astype(np.float32) / 255.0).permute(0, 3, 1, 2)
    challenge_images = (challenge_raw - channel_mean) / channel_std

    model = TinyHeatmapNet(uv.shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=2e-5)
    generator = np.random.default_rng(args.seed)
    history = []
    best_state = None
    best_val = math.inf
    best_epoch = -1
    stale = 0
    started = time.time()
    for epoch in range(args.epochs):
        model.train()
        shuffled = indices["train"].copy()
        generator.shuffle(shuffled)
        total_loss = 0.0
        total_visible = 0.0
        for start in range(0, len(shuffled), args.batch_size):
            batch = shuffled[start : start + args.batch_size]
            logits = model(images[batch])
            target = target_distributions(uv[batch], visible[batch], 1280, 1024, logits.shape[3], logits.shape[2])
            log_probability = F.log_softmax(logits.flatten(2), dim=2).reshape_as(logits)
            per_point = -(target * log_probability).sum(dim=(2, 3))
            weight = visible[batch]
            loss = (per_point * weight).sum() / weight.sum().clamp_min(1.0)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * float(weight.sum())
            total_visible += float(weight.sum())
        scheduler.step()
        if epoch % 4 == 0 or epoch == args.epochs - 1:
            val_pred = predict(model, images[indices["val"]], args.batch_size)
            val_target = data["uv"][indices["val"]]
            val_visible = data["visible"][indices["val"]].astype(bool)
            val_errors = np.linalg.norm(val_pred - val_target, axis=2)
            val_mean = float(val_errors[val_visible].mean())
            history.append({
                "epoch": epoch + 1,
                "train_cross_entropy": total_loss / max(total_visible, 1.0),
                "val_visible_mean_pixel_error": val_mean,
                "learning_rate": float(optimizer.param_groups[0]["lr"]),
            })
            if val_mean < best_val - 1e-6:
                best_val = val_mean
                best_epoch = epoch + 1
                best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
                stale = 0
            else:
                stale += 4
            print(f"{args.split_id} epoch={epoch + 1} loss={history[-1]['train_cross_entropy']:.5f} val={val_mean:.3f}px", flush=True)
            if stale >= 20 and epoch + 1 >= 32:
                break
    if best_state is None:
        raise RuntimeError("No best state was captured")
    model.load_state_dict(best_state)

    reports = {}
    stored_predictions = {}
    for bucket in ("train", "val", "test"):
        selection = indices[bucket]
        pred = predict(model, images[selection], args.batch_size)
        target = data["uv"][selection].astype(np.float64)
        vis = data["visible"][selection].astype(bool)
        errors = np.linalg.norm(pred - target, axis=2)
        reports[bucket] = {
            "visible_metrics": metric_summary(errors[vis]),
            "by_camera": grouped_metrics(errors, vis, data["camera_ids"][selection].astype(str)),
            "by_shape": grouped_metrics(errors, vis, data["shape_ids"][selection].astype(str)),
            "by_pose": grouped_metrics(errors, vis, data["pose_ids"][selection].astype(str)),
            "by_point": {
                str(point_id): metric_summary(errors[:, point_index][vis[:, point_index]])
                for point_index, point_id in enumerate(data["point_ids"].tolist())
            },
            "diagnostic_by_visibility_reason_code": {
                str(code): metric_summary(errors[data["reason_code"][selection] == code])
                for code in sorted(set(data["reason_code"].reshape(-1).tolist()))
            },
            "excluded_from_visible_loss_by_reason_code": {
                str(code): int(((data["reason_code"][selection] == code) & ~vis).sum())
                for code in sorted(set(data["reason_code"].reshape(-1).tolist()))
            },
        }
        stored_predictions[bucket] = pred.astype(np.float32)

    challenge_pred = predict(model, challenge_images, args.batch_size).astype(np.float32)
    challenge_target = data["challenge_uv"].astype(np.float64)
    challenge_visible = data["challenge_visible"].astype(bool)
    challenge_errors = np.linalg.norm(challenge_pred - challenge_target, axis=2)
    train_case_ids = set(split["train_case_ids"])
    reports["challenge"] = {
        "challenge_only_not_used_for_training": True,
        "visible_metrics": metric_summary(challenge_errors[challenge_visible]),
        "case_seen_in_train": {
            str(case_id): bool(str(case_id) in train_case_ids)
            for case_id in sorted(set(data["challenge_case_ids"].astype(str).tolist()))
        },
        "diagnostic_by_visibility_reason_code": {
            str(code): metric_summary(challenge_errors[data["challenge_reason_code"] == code])
            for code in sorted(set(data["challenge_reason_code"].reshape(-1).tolist()))
        },
    }

    torch.save({
        "model_state": best_state,
        "channel_mean": channel_mean,
        "channel_std": channel_std,
        "point_ids": data["point_ids"].tolist(),
        "split_id": args.split_id,
        "seed": args.seed,
        "architecture": "TinyHeatmapNet",
    }, output / "model_state.pt")
    np.savez_compressed(
        output / "predictions.npz",
        train_indices=indices["train"],
        val_indices=indices["val"],
        test_indices=indices["test"],
        train_predicted_uv=stored_predictions["train"],
        val_predicted_uv=stored_predictions["val"],
        test_predicted_uv=stored_predictions["test"],
        test_target_uv=data["uv"][indices["test"]].astype(np.float32),
        test_visible=data["visible"][indices["test"]].astype(np.uint8),
        challenge_predicted_uv=challenge_pred,
        challenge_target_uv=data["challenge_uv"].astype(np.float32),
        challenge_visible=data["challenge_visible"].astype(np.uint8),
        challenge_sample_ids=data["challenge_sample_ids"],
    )
    with (output / "training_curve.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    write_json(output / "training_config.json", {
        "schema": "engineering-pilot-heatmap-training-config-v1",
        "split_id": args.split_id,
        "seed": args.seed,
        "architecture": "TinyHeatmapNet RGB-only 20-channel heatmap",
        "input_resolution": [160, 128],
        "heatmap_resolution": [40, 32],
        "loss": "Per-visible-point spatial cross entropy against Gaussian target; invisible weights are zero.",
        "optimizer": "AdamW",
        "learning_rate": 0.001,
        "requested_epochs": args.epochs,
        "best_epoch": best_epoch,
        "model_inputs": ["images_rgb"],
        "prohibited_inputs": ["Depth", "Mask", "labels", "overlay", "case/shape/pose/camera identifiers"],
        "metadata_used_only_for": ["group split selection", "evaluation breakdown"],
        "pretrained_weights": False,
        "device": "CPU",
        "torch_version": torch.__version__,
    })
    write_json(output / "metrics.json", {
        "schema": "engineering-pilot-generalization-metrics-v1",
        "medical_truth": False,
        "split_id": args.split_id,
        "best_epoch": best_epoch,
        "best_val_visible_mean_pixel_error": best_val,
        "elapsed_seconds": time.time() - started,
        "reports": reports,
        "allowed_conclusion": "This baseline measures engineering generalization on one frozen grouped split.",
        "not_claimed": ["medical accuracy", "real-human generalization", "clinical usability", "robot safety"],
    })
    verification = {
        "schema": "engineering-pilot-baseline-verification-v1",
        "passed": bool(
            all(len(indices[bucket]) > 0 for bucket in ("train", "val", "test"))
            and math.isfinite(reports["test"]["visible_metrics"]["mean_px"])
        ),
        "checks": {
            "grouped_split_used": True,
            "rgb_only_model_input": True,
            "invisible_heatmap_loss_zero": True,
            "test_visible_metrics_finite": math.isfinite(reports["test"]["visible_metrics"]["mean_px"]),
            "depth_to_3d_delegated_to_independent_evaluator": True,
        },
        "test_visible_metrics": reports["test"]["visible_metrics"],
        "performance_gate": "No accuracy threshold in V1; this is the first failure-map baseline, not a quality claim.",
    }
    write_json(output / "verification.json", verification)
    print(json.dumps({
        "BASELINE": "PASS" if verification["passed"] else "FAIL",
        "split": args.split_id,
        "test_mean_px": reports["test"]["visible_metrics"]["mean_px"],
        "test_pck_20": reports["test"]["visible_metrics"]["pck"]["@20px"],
    }, ensure_ascii=False))
    if not verification["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
