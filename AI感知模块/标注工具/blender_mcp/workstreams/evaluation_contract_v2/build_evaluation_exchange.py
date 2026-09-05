from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--training-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    dataset_root = args.dataset.resolve()
    training_root = args.training_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    manifest = read_json(dataset_root / "dataset_manifest.json")
    main_by_id = {row["sample_id"]: row for row in manifest["main_samples"]}
    challenge_by_id = {row["sample_id"]: row for row in manifest["challenge_samples"]}
    cache = np.load(args.cache, allow_pickle=False)
    point_ids = cache["point_ids"].astype(str).tolist()
    reason_names = {
        0: "VISIBLE",
        1: "OUT_OF_FRAME",
        2: "SELF_OCCLUDED",
        3: "EXTERNAL_OCCLUDED",
        4: "BACK_FACING",
        5: "BEHIND_CAMERA",
    }

    label_cache: dict[str, dict] = {}
    rows: list[dict] = []

    def append_rows(
        split_id: str,
        bucket: str,
        sample_ids: list[str],
        predicted: np.ndarray,
        target: np.ndarray,
        visible: np.ndarray,
        reason_code: np.ndarray,
        case_ids: np.ndarray,
        shape_ids: np.ndarray,
        pose_ids: np.ndarray,
        camera_ids: np.ndarray,
        geometry_ids: np.ndarray,
        source_rows: dict[str, dict],
    ) -> None:
        for sample_index, sample_id in enumerate(sample_ids):
            source = source_rows[sample_id]
            relative_dir = source["geometry_relative_directory"]
            if relative_dir not in label_cache:
                label_cache[relative_dir] = read_json(dataset_root / relative_dir / "labels.json")
            labels = label_cache[relative_dir]
            intrinsics = labels["camera"]["intrinsics"]
            if [point["point_id"] for point in labels["points"]] != point_ids:
                raise RuntimeError(f"Point order mismatch: {sample_id}")
            for point_index, point in enumerate(labels["points"]):
                gt = target[sample_index, point_index]
                pred = predicted[sample_index, point_index]
                xyz = point["xyz_camera_opencv_m"]
                rows.append({
                    "split_id": split_id,
                    "bucket": bucket,
                    "sample_id": sample_id,
                    "case_id": str(case_ids[sample_index]),
                    "shape_id": str(shape_ids[sample_index]),
                    "pose_id": str(pose_ids[sample_index]),
                    "camera_id": str(camera_ids[sample_index]),
                    "base_geometry_id": str(geometry_ids[sample_index]),
                    "appearance_ordinal": int(source.get("variant_ordinal", 0)),
                    "point_index": point_index,
                    "point_id": point["point_id"],
                    "visibility_reason": reason_names[int(reason_code[sample_index, point_index])],
                    "visible": int(bool(visible[sample_index, point_index])),
                    "gt_u_original": float(gt[0]),
                    "gt_v_original": float(gt[1]),
                    "pred_u_original": float(pred[0]),
                    "pred_v_original": float(pred[1]),
                    "gt_x_camera_m": float(xyz[0]),
                    "gt_y_camera_m": float(xyz[1]),
                    "gt_z_camera_m": float(xyz[2]),
                    "original_width": int(intrinsics["width"]),
                    "original_height": int(intrinsics["height"]),
                    "fx": float(intrinsics["fx"]),
                    "fy": float(intrinsics["fy"]),
                    "cx": float(intrinsics["cx"]),
                    "cy": float(intrinsics["cy"]),
                    "depth_relative_path": f"{relative_dir}/scene_depth_z.npy",
                    "valid_mask_relative_path": f"{relative_dir}/depth_valid_mask.png",
                    "skin_mask_relative_path": f"{relative_dir}/skin_mask.png",
                })

    prediction_hashes = {}
    for split_id in SPLITS:
        prediction_path = training_root / split_id / "predictions.npz"
        prediction_hashes[split_id] = sha256(prediction_path)
        prediction = np.load(prediction_path, allow_pickle=False)
        test_indices = prediction["test_indices"].astype(np.int64)
        append_rows(
            split_id,
            "test",
            cache["sample_ids"][test_indices].astype(str).tolist(),
            prediction["test_predicted_uv"].astype(np.float64),
            cache["uv"][test_indices].astype(np.float64),
            cache["visible"][test_indices].astype(bool),
            cache["reason_code"][test_indices],
            cache["case_ids"][test_indices],
            cache["shape_ids"][test_indices],
            cache["pose_ids"][test_indices],
            cache["camera_ids"][test_indices],
            cache["geometry_ids"][test_indices],
            main_by_id,
        )
        append_rows(
            split_id,
            "challenge",
            cache["challenge_sample_ids"].astype(str).tolist(),
            prediction["challenge_predicted_uv"].astype(np.float64),
            cache["challenge_uv"].astype(np.float64),
            cache["challenge_visible"].astype(bool),
            cache["challenge_reason_code"],
            cache["challenge_case_ids"],
            cache["challenge_shape_ids"],
            cache["challenge_pose_ids"],
            cache["challenge_camera_ids"],
            cache["challenge_geometry_ids"],
            challenge_by_id,
        )

    exchange_path = output / "evaluation_exchange.csv"
    with exchange_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    contract = {
        "schema": "engineering-pilot-evaluation-coordinate-contract-v2",
        "medical_truth": False,
        "coordinate_space": {
            "evaluation_coordinate_space": "ORIGINAL_RENDER_CONTINUOUS_EDGE_COORDINATES",
            "origin": "top-left image edge",
            "axes": "+u right, +v down",
            "pixel_center": "pixel (column,row) center is (column+0.5,row+0.5)",
            "unit": "original-render pixel",
        },
        "resolutions": {
            "original_render": [1280, 1024],
            "network_input": [160, 128],
            "heatmap": [40, 32],
        },
        "transforms": {
            "original_to_input": "u_input=u_original*160/1280; v_input=v_original*128/1024; bilinear RGB resize",
            "original_to_heatmap_target": "x=u_original/1280*40-0.5; y=v_original/1024*32-0.5",
            "heatmap_to_original": "u=(E[x]+0.5)/40*1280; v=(E[y]+0.5)/32*1024",
            "letterbox_or_crop_in_network_preprocess": "NONE",
        },
        "decoder": {
            "name": "SPATIAL_SOFTMAX_EXPECTATION",
            "description": "softmax over all heatmap cells followed by expected x/y; not argmax or DARK",
        },
        "depth_sampling": {
            "rule": "floor continuous edge coordinate to (column,row); unfiltered scene camera-Z",
            "unit": "m",
            "valid_surface_for_final_3d": "depth valid and first surface is SKEL skin",
        },
        "evaluation_population": "Only VISIBLE rows are accuracy targets; other reasons remain diagnostics.",
    }
    write_json(output / "evaluation_coordinate_contract_v2.json", contract)
    metadata = {
        "schema": "engineering-pilot-evaluation-exchange-metadata-v2",
        "passed": True,
        "row_count": len(rows),
        "test_row_count": sum(row["bucket"] == "test" for row in rows),
        "challenge_row_count": sum(row["bucket"] == "challenge" for row in rows),
        "exchange_sha256": sha256(exchange_path),
        "source_cache_sha256": sha256(args.cache),
        "prediction_sha256": prediction_hashes,
        "dataset_root": str(dataset_root),
        "training_root": str(training_root),
        "note": "The evaluator consumes this CSV and original label/depth assets; it does not import training code.",
    }
    write_json(output / "evaluation_exchange_metadata.json", metadata)
    print(json.dumps({"EXCHANGE": "PASS", "rows": len(rows), "sha256": metadata["exchange_sha256"]}))


if __name__ == "__main__":
    main()
