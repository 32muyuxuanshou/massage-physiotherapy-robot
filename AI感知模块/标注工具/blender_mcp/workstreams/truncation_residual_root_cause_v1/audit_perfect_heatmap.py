from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


WIDTH, HEIGHT = 1280, 1024
HEAT_W, HEAT_H = 40, 32
SIGMA = 1.35


def distribution(uv: np.ndarray) -> np.ndarray:
    x = uv[..., 0] / WIDTH * HEAT_W - 0.5
    y = uv[..., 1] / HEIGHT * HEAT_H - 0.5
    gx = np.arange(HEAT_W, dtype=np.float64).reshape(1, HEAT_W)
    gy = np.arange(HEAT_H, dtype=np.float64).reshape(HEAT_H, 1)
    heat = np.exp(-((gx - x) ** 2 + (gy - y) ** 2) / (2.0 * SIGMA * SIGMA))
    return heat / heat.sum()


def decode_expectation(probability: np.ndarray) -> np.ndarray:
    x = float((probability * np.arange(HEAT_W).reshape(1, HEAT_W)).sum())
    y = float((probability * np.arange(HEAT_H).reshape(HEAT_H, 1)).sum())
    return np.asarray([(x + 0.5) / HEAT_W * WIDTH, (y + 0.5) / HEAT_H * HEIGHT])


def decode_argmax(probability: np.ndarray) -> np.ndarray:
    row, col = np.unravel_index(int(probability.argmax()), probability.shape)
    return np.asarray([(col + 0.5) / HEAT_W * WIDTH, (row + 0.5) / HEAT_H * HEIGHT])


def edge_info(uv: np.ndarray) -> tuple[str, float]:
    values = {"LEFT": float(uv[0]), "RIGHT": float(WIDTH - uv[0]), "TOP": float(uv[1]), "BOTTOM": float(HEIGHT - uv[1])}
    edge = min(values, key=values.get)
    return edge, values[edge]


def bin_name(distance: float) -> str:
    for upper, name in ((16, "0-16"), (32, "16-32"), (64, "32-64"), (128, "64-128")):
        if distance < upper:
            return name
    return ">=128"


def inward(edge: str, delta: np.ndarray) -> float:
    return {"LEFT": delta[0], "RIGHT": -delta[0], "TOP": delta[1], "BOTTOM": -delta[1]}[edge]


def summarize(rows: list[dict]) -> dict:
    output = {}
    groups = defaultdict(list)
    for row in rows:
        groups[(row["edge"], row["distance_bin"])].append(row)
    for (edge, bucket), values in sorted(groups.items()):
        output[f"{edge}|{bucket}"] = {
            "count": len(values),
            "expectation_mean_error_px": float(np.mean([v["expectation_error_px"] for v in values])),
            "expectation_p95_error_px": float(np.percentile([v["expectation_error_px"] for v in values], 95)),
            "expectation_mean_inward_bias_px": float(np.mean([v["expectation_inward_bias_px"] for v in values])),
            "argmax_mean_error_px": float(np.mean([v["argmax_error_px"] for v in values])),
        }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = np.load(args.dataset, allow_pickle=False)
    actual = []
    for sample_index in range(len(data["uv"])):
        for point_index in range(len(data["point_ids"])):
            if not bool(data["visible"][sample_index, point_index]):
                continue
            uv = data["uv"][sample_index, point_index].astype(np.float64)
            edge, distance = edge_info(uv)
            prob = distribution(uv)
            exp_uv = decode_expectation(prob)
            arg_uv = decode_argmax(prob)
            delta = exp_uv - uv
            actual.append({
                "sample_id": str(data["sample_ids"][sample_index]), "case_id": str(data["case_ids"][sample_index]),
                "camera_id": str(data["camera_ids"][sample_index]), "point_id": str(data["point_ids"][point_index]),
                "edge": edge, "edge_distance_px": distance, "distance_bin": bin_name(distance),
                "gt_u": float(uv[0]), "gt_v": float(uv[1]), "expectation_u": float(exp_uv[0]), "expectation_v": float(exp_uv[1]),
                "expectation_du": float(delta[0]), "expectation_dv": float(delta[1]),
                "expectation_inward_bias_px": float(inward(edge, delta)), "expectation_error_px": float(np.linalg.norm(delta)),
                "argmax_error_px": float(np.linalg.norm(arg_uv - uv)),
            })
    synthetic = []
    for edge in ("LEFT", "RIGHT", "TOP", "BOTTOM"):
        for distance in (0, 4, 8, 16, 24, 32, 48, 64, 96, 128, 192):
            uv = {
                "LEFT": np.asarray([distance, HEIGHT / 2]), "RIGHT": np.asarray([WIDTH - distance, HEIGHT / 2]),
                "TOP": np.asarray([WIDTH / 2, distance]), "BOTTOM": np.asarray([WIDTH / 2, HEIGHT - distance]),
            }[edge]
            prob = distribution(uv)
            exp_uv = decode_expectation(prob); arg_uv = decode_argmax(prob); delta = exp_uv - uv
            synthetic.append({"edge": edge, "edge_distance_px": distance, "expectation_inward_bias_px": float(inward(edge, delta)), "expectation_error_px": float(np.linalg.norm(delta)), "argmax_error_px": float(np.linalg.norm(arg_uv - uv))})
    with (args.output / "actual_point_perfect_decode.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(actual[0])); writer.writeheader(); writer.writerows(actual)
    with (args.output / "synthetic_edge_sweep.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(synthetic[0])); writer.writeheader(); writer.writerows(synthetic)
    near = [row for row in actual if row["edge_distance_px"] < 64]
    report = {
        "schema": "perfect-target-heatmap-boundary-self-decode-v1", "medical_truth": False,
        "exact_training_contract": {"original_resolution": [WIDTH, HEIGHT], "heatmap_resolution": [HEAT_W, HEAT_H], "sigma_cells": SIGMA, "target": "truncated Gaussian normalized over in-frame heatmap", "decoder": "global spatial expectation"},
        "actual_visible_instance_count": len(actual), "actual_nearest_edge_lt64_count": len(near),
        "actual_nearest_edge_lt64": {
            "mean_expectation_error_px": float(np.mean([r["expectation_error_px"] for r in near])) if near else None,
            "p95_expectation_error_px": float(np.percentile([r["expectation_error_px"] for r in near], 95)) if near else None,
            "mean_inward_bias_px": float(np.mean([r["expectation_inward_bias_px"] for r in near])) if near else None,
        },
        "grouped_actual": summarize(actual),
        "synthetic_edge_sweep": synthetic,
        "interpretation_rule": "If perfect target expectation has material inward bias near edges, current target+decoder has a structural boundary floor independent of network learning.",
    }
    (args.output / "perfect_heatmap_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["actual_nearest_edge_lt64"], ensure_ascii=False))


if __name__ == "__main__":
    main()
