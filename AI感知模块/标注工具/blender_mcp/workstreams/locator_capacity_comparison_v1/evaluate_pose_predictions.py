"""Evaluate exported MMPose predictions in the frozen original-image space."""

from __future__ import annotations

import argparse
import json
import pickle
from collections import defaultdict
from pathlib import Path

import numpy as np


ORIGINAL_SIZE = (1280, 1024)
NETWORK_INPUT_SIZE = (160, 128)
SCALE_X = ORIGINAL_SIZE[0] / NETWORK_INPUT_SIZE[0]
SCALE_Y = ORIGINAL_SIZE[1] / NETWORK_INPUT_SIZE[1]


def summarize(values: list[float]) -> dict[str, float | int]:
    data = np.asarray(values, dtype=np.float64)
    if data.size == 0:
        return {"count": 0}
    return {
        "count": int(data.size),
        "mean_px": float(data.mean()),
        "median_px": float(np.median(data)),
        "p95_px": float(np.percentile(data, 95)),
        "p99_px": float(np.percentile(data, 99)),
        "max_px": float(data.max()),
        "gt_20px_count": int((data > 20.0).sum()),
        "gt_20px_rate": float((data > 20.0).mean()),
        "gt_30px_count": int((data > 30.0).sum()),
        "gt_30px_rate": float((data > 30.0).mean()),
    }


def camera_from_path(path: str) -> str:
    stem = Path(path).stem
    for camera in (
        "NORMAL_MAIN",
        "C1_MILD_OBLIQUE",
        "C2_EDGE_CROP",
        "C3_EXTERNAL_OCCLUDER",
    ):
        if f"__{camera}__" in stem:
            return camera
    return "UNKNOWN"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--split", required=True)
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()

    with args.predictions.open("rb") as handle:
        records = pickle.load(handle)

    all_errors: list[float] = []
    by_camera: dict[str, list[float]] = defaultdict(list)
    by_point_index: dict[int, list[float]] = defaultdict(list)
    image_ids: list[int] = []

    for record in records:
        pred = np.asarray(record["pred_instances"]["keypoints"], dtype=np.float64)[0]
        gt = np.asarray(record["gt_instances"]["keypoints"], dtype=np.float64)[0]
        visible = (
            np.asarray(record["gt_instances"]["keypoints_visible"], dtype=np.float64)[0]
            > 0
        )
        if pred.shape != gt.shape or pred.shape != (20, 2):
            raise ValueError(f"Unexpected keypoint shape: pred={pred.shape}, gt={gt.shape}")

        delta = pred - gt
        delta[:, 0] *= SCALE_X
        delta[:, 1] *= SCALE_Y
        errors = np.linalg.norm(delta, axis=1)
        camera = camera_from_path(record["img_path"])
        image_ids.append(int(record["img_id"]))

        for point_index in np.flatnonzero(visible):
            error = float(errors[point_index])
            all_errors.append(error)
            by_camera[camera].append(error)
            by_point_index[int(point_index)].append(error)

    report = {
        "schema": "locator-capacity-evaluation-v1",
        "split": args.split,
        "checkpoint": args.checkpoint,
        "prediction_file": str(args.predictions),
        "coordinate_contract": {
            "evaluation_space": "original continuous image coordinates",
            "original_resolution": list(ORIGINAL_SIZE),
            "network_input_resolution": list(NETWORK_INPUT_SIZE),
            "input_to_original_scale": [SCALE_X, SCALE_Y],
            "visibility_rule": "gt_instances.keypoints_visible > 0",
        },
        "sample_count": len(records),
        "unique_image_id_count": len(set(image_ids)),
        "overall": summarize(all_errors),
        "by_camera": {
            key: summarize(values) for key, values in sorted(by_camera.items())
        },
        "by_point_index": {
            str(key): summarize(values) for key, values in sorted(by_point_index.items())
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["overall"], indent=2))


if __name__ == "__main__":
    main()
