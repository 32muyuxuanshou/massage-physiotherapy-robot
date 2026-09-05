from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.dump.open("rb") as stream:
        records = pickle.load(stream)
    sample_ids, uv, scores, simcc_x, simcc_y = [], [], [], [], []
    for record in records:
        pred = record["pred_instances"]
        sample_ids.append(Path(record["img_path"]).stem)
        uv.append(np.asarray(pred["keypoints"], np.float32)[0])
        scores.append(np.asarray(pred["keypoint_scores"], np.float32)[0])
        simcc_x.append(np.asarray(pred["keypoint_x_labels"], np.float32)[0])
        simcc_y.append(np.asarray(pred["keypoint_y_labels"], np.float32)[0])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        sample_ids=np.asarray(sample_ids),
        uv_original_px=np.asarray(uv, np.float32),
        keypoint_scores=np.asarray(scores, np.float32),
        simcc_x=np.asarray(simcc_x, np.float32),
        simcc_y=np.asarray(simcc_y, np.float32),
    )
    print({"samples": len(sample_ids), "output": str(args.output)})


if __name__ == "__main__":
    main()
