from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
WIDTH, HEIGHT = 1280, 1024


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


def decode_expectation(logits: torch.Tensor) -> torch.Tensor:
    b, p, h, w = logits.shape
    prob = torch.softmax(logits.flatten(2), dim=2).reshape(b, p, h, w)
    gx = torch.arange(w, dtype=torch.float32).view(1, 1, 1, w)
    gy = torch.arange(h, dtype=torch.float32).view(1, 1, h, 1)
    x = (prob * gx).sum((2, 3)); y = (prob * gy).sum((2, 3))
    return torch.stack(((x + 0.5) / w * WIDTH, (y + 0.5) / h * HEIGHT), dim=2)


def to_original(x: np.ndarray, y: np.ndarray, w: int, h: int) -> np.ndarray:
    return np.stack(((x + 0.5) / w * WIDTH, (y + 0.5) / h * HEIGHT), axis=2).astype(np.float32)


def decode_argmax(logits: np.ndarray) -> np.ndarray:
    b, p, h, w = logits.shape
    flat = logits.reshape(b, p, -1).argmax(axis=2)
    return to_original((flat % w).astype(np.float64), (flat // w).astype(np.float64), w, h)


def vertex_from_three(values: np.ndarray, center: int, length: int) -> float:
    if center <= 0:
        indices = np.asarray([0.0, 1.0, 2.0])
    elif center >= length - 1:
        indices = np.asarray([length - 3.0, length - 2.0, length - 1.0])
    else:
        indices = np.asarray([center - 1.0, center, center + 1.0])
    selected = values[indices.astype(int)]
    matrix = np.stack((indices * indices, indices, np.ones(3)), axis=1)
    a, b, _ = np.linalg.solve(matrix, selected)
    if not np.isfinite(a) or a >= -1e-8:
        return float(center)
    # Pixel coordinates are half-open: [0, width) / [0, height). Keep the fitted center
    # just inside the corresponding heatmap-domain boundary after float32 conversion.
    return float(np.clip(-b / (2.0 * a), -0.4999, length - 0.5001))


def decode_log_quadratic(logits: np.ndarray) -> np.ndarray:
    b, p, h, w = logits.shape
    # Log-marginals preserve an ideal separable Gaussian's quadratic center, including one-sided boundary samples.
    tensor = torch.from_numpy(logits)
    x_log = torch.logsumexp(tensor, dim=2).numpy()
    y_log = torch.logsumexp(tensor, dim=3).numpy()
    flat = logits.reshape(b, p, -1).argmax(axis=2)
    peak_x = flat % w; peak_y = flat // w
    x = np.empty((b, p), dtype=np.float64); y = np.empty((b, p), dtype=np.float64)
    for i in range(b):
        for j in range(p):
            x[i, j] = vertex_from_three(x_log[i, j], int(peak_x[i, j]), w)
            y[i, j] = vertex_from_three(y_log[i, j], int(peak_y[i, j]), h)
    return to_original(x, y, w, h)


def infer(model_path: Path, images: np.ndarray) -> dict[str, np.ndarray]:
    state = torch.load(model_path, map_location="cpu", weights_only=False)
    model = TinyHeatmapNet(len(state["point_ids"])); model.load_state_dict(state["model_state"]); model.eval()
    raw = torch.from_numpy(images.astype(np.float32) / 255.0).permute(0, 3, 1, 2)
    normalized = (raw - state["channel_mean"]) / state["channel_std"]
    logits = []
    with torch.no_grad():
        for start in range(0, len(images), 24):
            logits.append(model(normalized[start:start + 24]).cpu())
    tensor = torch.cat(logits)
    array = tensor.numpy().astype(np.float32)
    expectation = decode_expectation(tensor).numpy().astype(np.float32)
    argmax = decode_argmax(array)
    quadratic = decode_log_quadratic(array)
    b, p, h, w = array.shape
    flat = array.reshape(b, p, -1).argmax(axis=2)
    peak_x, peak_y = flat % w, flat // w
    boundary = (peak_x <= 3) | (peak_x >= w - 4) | (peak_y <= 3) | (peak_y >= h - 4)
    hybrid = np.where(boundary[..., None], quadratic, expectation).astype(np.float32)
    return {"expectation": expectation, "argmax": argmax, "log_quadratic": quadratic, "boundary_hybrid": hybrid, "boundary_hybrid_used": boundary.astype(np.uint8)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-v2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    evidence = args.evidence_v2.resolve()
    data = np.load(evidence / "truncation_holdout_v2.npz", allow_pickle=False)
    splits = read_json(evidence / "contracts" / "evaluation_splits_v1.json")
    case_ids = data["case_ids"].astype(str)
    checks = {}
    for split in SPLITS:
        cases = set(splits["splits"][split]["test_case_ids"])
        selection = np.asarray([i for i, case in enumerate(case_ids) if case in cases], dtype=np.int64)
        decoded = infer(evidence / "training" / split / "model_state.pt", data["images_rgb"][selection])
        old = np.load(evidence / "truncation_holdout_predictions" / f"{split}_predictions.npz", allow_pickle=False)
        delta = float(np.max(np.abs(decoded["expectation"] - old["v2_predicted_uv"])))
        checks[f"{split}_expectation_parity_le_1e-5"] = delta <= 1e-5
        np.savez_compressed(args.output / f"{split}_decoder_predictions.npz", selection=selection, **decoded)
        print(f"{split}: expectation parity {delta:.9f}px", flush=True)
    report = {"schema": "frozen-v2-decoder-comparison-export-v1", "checks": checks, "passed": all(checks.values()), "decoders": ["expectation", "argmax", "log_quadratic", "boundary_hybrid"], "boundary_hybrid_rule": "Use log-quadratic only when heatmap argmax is in the outer four cells; otherwise preserve spatial expectation.", "candidate_status": "DIAGNOSTIC_NOT_PRODUCTION_VALIDATED"}
    (args.output / "export_verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
