from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
WIDTH, HEIGHT = 1280, 1024


def read(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8-sig"))
def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stats(values: list[float], unit: str) -> dict:
    a = np.asarray(values, np.float64)
    if not a.size: return {"count": 0, "mean": None, "p95": None, "p99": None, "max": None, "unit": unit}
    return {"count": int(a.size), "mean": float(a.mean()), "p95": float(np.percentile(a, 95)),
            "p99": float(np.percentile(a, 99)), "max": float(a.max()), "unit": unit}


def edge_distance(uv: np.ndarray) -> float: return float(min(uv[0], WIDTH - uv[0], uv[1], HEIGHT - uv[1]))
def bucket(distance: float) -> str:
    if distance < 16: return "0-16"
    if distance < 32: return "16-32"
    if distance < 64: return "32-64"
    if distance < 128: return "64-128"
    return ">=128"


def metric_for_decoder(pred: np.ndarray, data, cache: dict, *, key: str) -> dict:
    err2, err3, invalid = [], [], []
    by_camera, by_kind, by_direction, by_point = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for i, path in enumerate(data["sample_paths"].astype(str)):
        if path not in cache:
            sample = Path(path); labels = read(sample / "labels.json"); depth = np.load(sample / "scene_depth_z.npy", allow_pickle=False)
            with Image.open(sample / "depth_valid_mask.png") as image: valid = np.asarray(image.convert("L"), np.uint8)
            with Image.open(sample / "skin_mask.png") as image: skin = np.asarray(image.convert("L"), np.uint8)
            cache[path] = (labels, depth, valid, skin)
        labels, depth, valid, skin = cache[path]; intr = labels["camera"]["intrinsics"]
        for j, point_id in enumerate(data["point_ids"].astype(str)):
            if not bool(data["visible"][i, j]): continue
            gt = data["uv"][i, j].astype(np.float64); uv = pred[i, j].astype(np.float64)
            error = float(np.linalg.norm(uv - gt)); err2.append(error)
            by_camera[str(data["camera_ids"][i])].append(error); by_kind[str(data["camera_kinds"][i])].append(error)
            by_direction[str(data["directions"][i])].append(error); by_point[str(point_id)].append(error)
            col, row = int(math.floor(uv[0])), int(math.floor(uv[1])); reason = None
            if not (0 <= col < depth.shape[1] and 0 <= row < depth.shape[0]): reason = "PREDICTED_OUT_OF_FRAME"
            elif depth[row, col] <= 0 or valid[row, col] != 255: reason = "INVALID_DEPTH"
            elif skin[row, col] != 255: reason = "NON_SKIN_FIRST_SURFACE"
            if reason:
                invalid.append({"sample_id": str(data["sample_ids"][i]), "point_id": str(point_id), "reason": reason})
                continue
            z = float(depth[row, col]); xyz = np.asarray([(uv[0] - intr["cx"]) * z / intr["fx"], (uv[1] - intr["cy"]) * z / intr["fy"], z])
            target = np.asarray(labels["points"][j]["xyz_camera_opencv_m"])
            err3.append(float(np.linalg.norm(xyz - target) * 1000.0))
    return {"decoder": key, "visible_2d": stats(err2, "px"), "final_3d": stats(err3, "mm"),
            "tail_gt30mm_count": sum(x > 30 for x in err3), "invalid_3d_count": len(invalid), "invalid_3d_details": invalid,
            "by_camera": {k: stats(v, "px") for k, v in sorted(by_camera.items())},
            "by_kind": {k: stats(v, "px") for k, v in sorted(by_kind.items())},
            "by_direction": {k: stats(v, "px") for k, v in sorted(by_direction.items())},
            "worst_points": sorted(({"point_id": k, **stats(v, "px")} for k, v in by_point.items()), key=lambda x: x["p95"], reverse=True)[:8]}


def branch_audit(pred, data) -> dict:
    bins = defaultdict(list); false_nonedge = []; regressions = []; improvements = []
    exp, hyb = pred["expectation"], pred["hybrid"]
    for i in range(len(data["sample_ids"])):
        for j in range(len(data["point_ids"])):
            if not bool(data["visible"][i, j]): continue
            gt = data["uv"][i, j].astype(np.float64); d = edge_distance(gt); used = bool(pred["branch_used"][i, j])
            e = float(np.linalg.norm(exp[i, j] - gt)); h = float(np.linalg.norm(hyb[i, j] - gt)); delta = h - e
            bins[bucket(d)].append((used, delta)); regressions.append(delta); improvements.append(-delta)
            if d >= 128: false_nonedge.append((used, delta))
    by_bin = {}
    for name, values in bins.items():
        used = [v for v in values if v[0]]
        by_bin[name] = {"count": len(values), "activation_count": len(used), "activation_rate": len(used) / len(values),
                        "mean_delta_error_px_when_used": float(np.mean([v[1] for v in used])) if used else None,
                        "harm_count_when_used": sum(v[1] > 0 for v in used), "improvement_count_when_used": sum(v[1] < 0 for v in used)}
    return {"by_gt_edge_distance": by_bin,
            "nonedge_gt_ge128_activation_rate": sum(v[0] for v in false_nonedge) / max(1, len(false_nonedge)),
            "max_regression_px": float(max(regressions)), "max_improvement_px": float(max(improvements)),
            "fallback_count_all_points": int((pred["fallback_code"] != 0).sum()),
            "branch_requested_all_points": int(pred["branch_requested"].sum()), "branch_used_all_points": int(pred["branch_used"].sum())}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("phase", choices=("validation", "untouched_test")); parser.add_argument("--root", required=True, type=Path); args = parser.parse_args()
    root = args.root.resolve(); data = np.load(root / f"{args.phase}_decoder_cache.npz", allow_pickle=False); report = {"schema": f"decoder-{args.phase}-evaluation-v1", "splits": {}}
    shared_cache = {}
    for split in SPLITS:
        pred = np.load(root / args.phase / "predictions" / f"{split}.npz", allow_pickle=False)
        report["splits"][split] = {"expectation": metric_for_decoder(pred["expectation"], data, shared_cache, key="expectation"),
                                    "hybrid": metric_for_decoder(pred["hybrid"], data, shared_cache, key="hybrid"),
                                    "branch_audit": branch_audit(pred, data)}
    report["analytic_guard_suite"] = read(root / "decoder_guard_unit_tests.json"); write(root / f"{args.phase}_decoder_evaluation.json", report)
    for split in SPLITS:
        e, h = report["splits"][split]["expectation"], report["splits"][split]["hybrid"]
        print(split, "p95", e["visible_2d"]["p95"], "->", h["visible_2d"]["p95"], "tail", e["tail_gt30mm_count"], "->", h["tail_gt30mm_count"], flush=True)


if __name__ == "__main__": main()
