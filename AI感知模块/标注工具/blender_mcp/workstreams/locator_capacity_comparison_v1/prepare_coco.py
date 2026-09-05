from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--split-id", default="POSE_HOLDOUT")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = np.load(args.cache, allow_pickle=False)
    split_contract = json.loads(args.splits.read_text(encoding="utf-8-sig"))["splits"][args.split_id]
    output = args.output.resolve()
    image_dir = output / "images"
    annotation_dir = output / "annotations"
    image_dir.mkdir(parents=True, exist_ok=True)
    annotation_dir.mkdir(parents=True, exist_ok=True)

    sample_ids = data["sample_ids"].astype(str)
    point_ids = data["point_ids"].astype(str).tolist()
    width = int(data["input_width"])
    height = int(data["input_height"])
    original_width = int(data["original_width"])
    original_height = int(data["original_height"])
    scale = np.asarray([width / original_width, height / original_height], dtype=np.float32)
    id_to_index = {sample_id: index for index, sample_id in enumerate(sample_ids.tolist())}

    for index, sample_id in enumerate(sample_ids):
        Image.fromarray(data["images_rgb"][index], mode="RGB").save(image_dir / f"{sample_id}.png")

    category = {
        "id": 1,
        "name": "engineering_back_points",
        "supercategory": "person",
        "keypoints": point_ids,
        "skeleton": [],
    }
    counts = {}
    for bucket in ("train", "val", "test"):
        images = []
        annotations = []
        ids = split_contract["sample_ids"][bucket]
        for local_id, sample_id in enumerate(ids, start=1):
            index = id_to_index[sample_id]
            uv = data["uv"][index] * scale
            visible = data["visible"][index].astype(bool)
            keypoints = []
            for point_uv, is_visible in zip(uv, visible):
                keypoints.extend([float(point_uv[0]), float(point_uv[1]), 2 if is_visible else 0])
            images.append({
                "id": local_id,
                "file_name": f"{sample_id}.png",
                "width": width,
                "height": height,
                "sample_id": sample_id,
            })
            annotations.append({
                "id": local_id,
                "image_id": local_id,
                "category_id": 1,
                "bbox": [0.0, 0.0, float(width), float(height)],
                "area": float(width * height),
                "iscrowd": 0,
                "num_keypoints": int(visible.sum()),
                "keypoints": keypoints,
            })
        write_json(annotation_dir / f"{bucket}.json", {
            "info": {"description": f"Frozen {args.split_id} {bucket}; engineering points, not medical truth."},
            "licenses": [],
            "images": images,
            "annotations": annotations,
            "categories": [category],
        })
        counts[bucket] = len(images)

    expected = split_contract["sample_counts"]
    passed = counts == {key: int(expected[key]) for key in ("train", "val", "test")}
    write_json(output / "conversion_verification.json", {
        "schema": "locator-capacity-coco-conversion-v1",
        "passed": passed,
        "split_id": args.split_id,
        "counts": counts,
        "point_ids": point_ids,
        "input_resolution": [width, height],
        "source_cache_sha256": sha256(args.cache),
        "source_split_sha256": sha256(args.splits),
        "coordinate_transform": [float(scale[0]), float(scale[1])],
        "medical_truth": False,
    })
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
