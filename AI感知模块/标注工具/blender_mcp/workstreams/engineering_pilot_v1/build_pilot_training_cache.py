from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


REASON_CODES = {
    "VISIBLE": 0,
    "OUT_OF_FRAME": 1,
    "SELF_OCCLUDED": 2,
    "EXTERNAL_OCCLUDED": 3,
    "BACK_FACING": 4,
    "BEHIND_CAMERA": 5,
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(root: Path, rows: list[dict], point_order: list[str], width: int, height: int, label: str) -> dict[str, np.ndarray]:
    output: dict[str, list] = {
        "images_rgb": [],
        "uv": [],
        "visible": [],
        "reason_code": [],
        "sample_ids": [],
        "case_ids": [],
        "shape_ids": [],
        "pose_ids": [],
        "camera_ids": [],
        "geometry_ids": [],
    }
    for index, row in enumerate(rows, start=1):
        rgb_path = root / row["rgb"]["relative_path"]
        if sha256(rgb_path) != row["rgb"]["sha256"]:
            raise RuntimeError(f"Frozen RGB changed: {rgb_path}")
        with Image.open(rgb_path) as image:
            resized = image.convert("RGB").resize((width, height), Image.Resampling.BILINEAR)
            output["images_rgb"].append(np.asarray(resized, dtype=np.uint8))
        labels = read_json(root / row["geometry_relative_directory"] / "labels.json")
        if [point["point_id"] for point in labels["points"]] != point_order:
            raise RuntimeError(f"Point order changed: {row['sample_id']}")
        output["uv"].append([[float(value) for value in point["uv_pixel_opencv"]] for point in labels["points"]])
        output["visible"].append([point["visibility_reason"] == "VISIBLE" for point in labels["points"]])
        output["reason_code"].append([REASON_CODES[point["visibility_reason"]] for point in labels["points"]])
        for key, source_key in (
            ("sample_ids", "sample_id"),
            ("case_ids", "case_id"),
            ("shape_ids", "shape_id"),
            ("pose_ids", "pose_id"),
            ("camera_ids", "camera_id"),
            ("geometry_ids", "base_geometry_id"),
        ):
            output[key].append(row[source_key])
        if index % 100 == 0 or index == len(rows):
            print(f"{label}_CACHE {index}/{len(rows)}", flush=True)
    arrays = {key: np.asarray(value) for key, value in output.items()}
    arrays["images_rgb"] = arrays["images_rgb"].astype(np.uint8)
    arrays["uv"] = arrays["uv"].astype(np.float32)
    arrays["visible"] = arrays["visible"].astype(np.uint8)
    arrays["reason_code"] = arrays["reason_code"].astype(np.uint8)
    return arrays


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--height", type=int, default=128)
    args = parser.parse_args()
    root = args.dataset.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    qc = read_json(root / "qc_verification.json")
    visual = read_json(root / "visual_review.json")
    dataset = read_json(root / "dataset_manifest.json")
    contract = read_json(root / "contracts" / "pilot_visibility_loss_contract_v1.json")
    if not qc["passed"] or not visual["passed"]:
        raise RuntimeError("Dataset QC and visual review must pass before cache build")
    point_order = contract["point_order"]
    main_data = collect(root, dataset["main_samples"], point_order, args.width, args.height, "MAIN")
    challenge_data = collect(root, dataset["challenge_samples"], point_order, args.width, args.height, "CHALLENGE")
    np.savez_compressed(
        output,
        **main_data,
        **{f"challenge_{key}": value for key, value in challenge_data.items()},
        point_ids=np.asarray(point_order),
        original_width=np.asarray(1280, dtype=np.int32),
        original_height=np.asarray(1024, dtype=np.int32),
        input_width=np.asarray(args.width, dtype=np.int32),
        input_height=np.asarray(args.height, dtype=np.int32),
    )
    report = {
        "schema": "engineering-pilot-training-cache-v1",
        "passed": True,
        "medical_truth": False,
        "sample_count": int(main_data["sample_ids"].size),
        "challenge_sample_count": int(challenge_data["sample_ids"].size),
        "point_count": len(point_order),
        "input_resolution": [args.width, args.height],
        "source_dataset": str(root),
        "source_dataset_manifest_sha256": sha256(root / "dataset_manifest.json"),
        "cache_path": str(output),
        "cache_sha256": sha256(output),
        "model_input_arrays": ["images_rgb", "challenge_images_rgb"],
        "target_arrays": ["uv", "visible", "challenge_uv", "challenge_visible"],
        "metadata_not_model_input": ["sample_ids", "case_ids", "shape_ids", "pose_ids", "camera_ids", "geometry_ids", "reason_code"],
        "forbidden_inputs": ["Depth", "Mask", "labels", "overlay", "case/shape/pose/camera identifiers"],
        "reason_codes": REASON_CODES,
    }
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"CACHE": "PASS", "sha256": report["cache_sha256"], "samples": report["sample_count"], "challenge": report["challenge_sample_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
