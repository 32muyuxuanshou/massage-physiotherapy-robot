from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def overlay(source: Path, gt: np.ndarray, visible: np.ndarray, prediction: np.ndarray, label: str) -> Image.Image:
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image)
    for index in range(len(gt)):
        if not visible[index]:
            continue
        gu, gv = map(float, gt[index])
        pu, pv = map(float, prediction[index])
        draw.line((gu, gv, pu, pv), fill=(255, 215, 0), width=2)
        draw.ellipse((gu - 4, gv - 4, gu + 4, gv + 4), outline=(0, 255, 0), width=2)
        draw.ellipse((pu - 4, pv - 4, pu + 4, pv + 4), outline=(255, 0, 0), width=2)
    draw.rectangle((0, 0, 260, 34), fill=(20, 20, 22))
    draw.text((8, 10), label, fill=(255, 255, 255), font=ImageFont.load_default())
    image.thumbnail((640, 512), Image.Resampling.LANCZOS)
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    data = np.load(root / "truncation_holdout_v2.npz", allow_pickle=False)
    manifest = read_json(root / "dataset_manifest.json")
    report = read_json(root / "truncation_holdout_evaluation" / "truncation_holdout_ab_report.json")
    by_id = {row["sample_id"]: row for row in manifest["truncation_holdout"]}
    sample_ids = data["sample_ids"].astype(str)
    canvas = Image.new("RGB", (1280, 512 * 3), (28, 28, 30))
    index = []
    for row_index, split_id in enumerate(SPLITS):
        worst = report["splits"][split_id]["v1"]["tail_gt30mm"][0]
        sample_id = worst["sample_id"]
        global_index = int(np.where(sample_ids == sample_id)[0][0])
        prediction_file = np.load(root / "truncation_holdout_predictions" / f"{split_id}_predictions.npz", allow_pickle=False)
        local_index = int(np.where(prediction_file["selection"] == global_index)[0][0])
        source = root / by_id[sample_id]["rgb_relative_path"]
        gt = data["uv"][global_index]
        visible = data["visible"][global_index].astype(bool)
        v1 = overlay(source, gt, visible, prediction_file["v1_predicted_uv"][local_index], f"{split_id} | V1")
        v2 = overlay(source, gt, visible, prediction_file["v2_predicted_uv"][local_index], f"{split_id} | V2")
        canvas.paste(v1.resize((640, 512), Image.Resampling.LANCZOS), (0, row_index * 512))
        canvas.paste(v2.resize((640, 512), Image.Resampling.LANCZOS), (640, row_index * 512))
        index.append({"split_id": split_id, "sample_id": sample_id, "v1_worst_point": worst["point_id"], "v1_worst_3d_mm": worst["final_3d_error_mm"]})
    visuals = root / "visuals"
    visuals.mkdir(parents=True, exist_ok=True)
    target = visuals / "truncation_holdout_v1_vs_v2.png"
    canvas.save(target)
    (visuals / "ab_visual_index.json").write_text(json.dumps({"schema": "failure-driven-ab-visual-v2", "items": index}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
