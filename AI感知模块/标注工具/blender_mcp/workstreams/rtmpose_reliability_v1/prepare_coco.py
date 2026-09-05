from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


POINT_IDS = [
    "GV14_MIDLINE", "BL13_LEFT", "BL13_RIGHT", "GV9_MIDLINE", "BL17_LEFT",
    "BL17_RIGHT", "GV6_MIDLINE", "BL20_LEFT", "BL20_RIGHT", "GV4_MIDLINE",
    "BL23_LEFT", "BL23_RIGHT", "BL25_LEFT", "BL25_RIGHT", "BL28_LEFT",
    "BL28_RIGHT", "GB21_LEFT", "GB21_RIGHT", "SI15_LEFT", "SI15_RIGHT",
]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = args.source_root.resolve()
    output = args.output.resolve()
    manifest = read(source / "selected_dataset_manifest.json")
    image_dir = output / "images"
    ann_dir = output / "annotations"
    image_dir.mkdir(parents=True, exist_ok=False)
    ann_dir.mkdir(parents=True, exist_ok=False)

    category = {
        "id": 1,
        "name": "engineering_back_points",
        "supercategory": "person",
        "keypoints": POINT_IDS,
        "skeleton": [],
    }
    buckets = {
        "RELIABILITY_TRAIN": "reliability_train",
        "CALIBRATION": "calibration",
        "UNTOUCHED_TEST": "untouched_test",
    }
    counts = {}
    for partition, bucket in buckets.items():
        images, annotations = [], []
        selected = [row for row in manifest["selected_samples"] if row["partition"] == partition]
        for image_id, row in enumerate(selected, start=1):
            sample = Path(row["sample"])
            labels = read(sample / "labels.json")
            point_by_id = {point["point_id"]: point for point in labels["points"]}
            if set(point_by_id) != set(POINT_IDS):
                raise ValueError(f"Unexpected point set in {sample}")
            destination = image_dir / f"{row['sample_id']}.png"
            shutil.copy2(sample / "rgb_model.png", destination)
            keypoints = []
            visible_count = 0
            for point_id in POINT_IDS:
                point = point_by_id[point_id]
                visible = bool(point["visible"] and point["visibility_reason"] == "VISIBLE")
                u, v = map(float, point["uv_pixel_opencv"])
                keypoints.extend([u, v, 2 if visible else 0])
                visible_count += int(visible)
            images.append({
                "id": image_id,
                "file_name": destination.name,
                "width": 1280,
                "height": 1024,
                "sample_id": row["sample_id"],
            })
            annotations.append({
                "id": image_id,
                "image_id": image_id,
                "category_id": 1,
                "bbox": [0.0, 0.0, 1280.0, 1024.0],
                "area": 1280.0 * 1024.0,
                "iscrowd": 0,
                "num_keypoints": visible_count,
                "keypoints": keypoints,
            })
        write(ann_dir / f"{bucket}.json", {
            "info": {"description": f"{partition}; engineering points, not medical truth."},
            "licenses": [],
            "images": images,
            "annotations": annotations,
            "categories": [category],
        })
        counts[partition] = len(images)

    expected = manifest["sample_counts"]
    passed = counts == {key: int(expected[key]) for key in buckets}
    write(output / "conversion_verification.json", {
        "schema": "rtmpose-reliability-coco-v1",
        "passed": passed,
        "counts": counts,
        "point_ids": POINT_IDS,
        "medical_truth": False,
    })
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
