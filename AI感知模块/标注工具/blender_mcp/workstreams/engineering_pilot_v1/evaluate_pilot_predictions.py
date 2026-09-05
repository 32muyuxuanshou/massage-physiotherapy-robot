from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summary(values: np.ndarray, *, millimetres: bool = False) -> dict:
    if values.size == 0:
        return {"count": 0, "mean": None, "median": None, "max": None}
    scale = 1000.0 if millimetres else 1.0
    return {
        "count": int(values.size),
        "mean": float(values.mean() * scale),
        "median": float(np.median(values) * scale),
        "max": float(values.max() * scale),
    }


def pixel_summary(values: np.ndarray) -> dict:
    result = summary(values)
    result["pck"] = {f"@{threshold}px": float((values <= threshold).mean()) if values.size else None for threshold in (5, 10, 20, 40)}
    return result


def evaluate_3d(dataset_root: Path, rows: list[dict], predicted: np.ndarray, visible: np.ndarray) -> dict:
    geometry_cache = {}
    errors = []
    invalid: dict[str, int] = defaultdict(int)
    details = []
    for sample_index, row in enumerate(rows):
        geometry_id = row["base_geometry_id"]
        if geometry_id not in geometry_cache:
            directory = dataset_root / row["geometry_relative_directory"]
            labels = read_json(directory / "labels.json")
            depth = np.load(directory / "scene_depth_z.npy", allow_pickle=False)
            with Image.open(directory / "depth_valid_mask.png") as image:
                valid = np.asarray(image.convert("L"), dtype=np.uint8)
            with Image.open(directory / "skin_mask.png") as image:
                skin = np.asarray(image.convert("L"), dtype=np.uint8)
            geometry_cache[geometry_id] = labels, depth, valid, skin
        labels, depth, valid, skin = geometry_cache[geometry_id]
        intrinsics = labels["camera"]["intrinsics"]
        for point_index, point in enumerate(labels["points"]):
            if not visible[sample_index, point_index]:
                continue
            u, v = map(float, predicted[sample_index, point_index])
            col, pix_row = int(math.floor(u)), int(math.floor(v))
            reason = None
            if not (0 <= col < depth.shape[1] and 0 <= pix_row < depth.shape[0]):
                reason = "PREDICTED_OUT_OF_FRAME"
            elif depth[pix_row, col] <= 0 or valid[pix_row, col] != 255:
                reason = "INVALID_DEPTH"
            elif skin[pix_row, col] != 255:
                reason = "NON_SKIN_FIRST_SURFACE"
            if reason is not None:
                invalid[reason] += 1
                continue
            z = float(depth[pix_row, col])
            xyz = np.asarray([
                (u - float(intrinsics["cx"])) * z / float(intrinsics["fx"]),
                (v - float(intrinsics["cy"])) * z / float(intrinsics["fy"]),
                z,
            ], dtype=np.float64)
            target = np.asarray(point["xyz_camera_opencv_m"], dtype=np.float64)
            error = float(np.linalg.norm(xyz - target))
            errors.append(error)
            details.append({"sample_id": row["sample_id"], "point_id": point["point_id"], "xyz_error_m": error})
    array = np.asarray(errors, dtype=np.float64)
    return {
        "visible_instance_count": int(visible.sum()),
        "valid_3d_count": int(array.size),
        "invalid_3d_count": int(visible.sum() - array.size),
        "invalid_reasons": dict(invalid),
        "xyz_error_mm": summary(array, millimetres=True),
        "details": details,
    }


def group_errors(errors: np.ndarray, visible: np.ndarray, groups: np.ndarray) -> dict:
    output = {}
    for group in sorted(set(groups.tolist())):
        selected = groups == group
        output[str(group)] = pixel_summary(errors[selected][visible[selected]])
    return output


def draw_overlay(rgb_path: Path, labels: dict, prediction: np.ndarray, output: Path) -> None:
    with Image.open(rgb_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    for index, point in enumerate(labels["points"]):
        if point["visibility_reason"] != "VISIBLE":
            continue
        target_u, target_v = map(float, point["uv_pixel_opencv"])
        pred_u, pred_v = map(float, prediction[index])
        draw.line((target_u, target_v, pred_u, pred_v), fill=(255, 220, 0), width=2)
        draw.ellipse((target_u - 4, target_v - 4, target_u + 4, target_v + 4), outline=(0, 255, 0), width=2)
        draw.ellipse((pred_u - 3, pred_v - 3, pred_u + 3, pred_v + 3), outline=(255, 0, 0), width=2)
    image.thumbnail((640, 512), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--training", type=Path, required=True)
    args = parser.parse_args()
    dataset_root = args.dataset.resolve()
    training = args.training.resolve()
    dataset = read_json(dataset_root / "dataset_manifest.json")
    train_verification = read_json(training / "verification.json")
    cache_report = read_json(args.cache.with_suffix(".json"))
    if not train_verification["passed"] or sha256(args.cache) != cache_report["cache_sha256"]:
        raise RuntimeError("Training or cache verification failed")
    data = np.load(args.cache, allow_pickle=False)
    predictions = np.load(training / "predictions.npz", allow_pickle=False)
    test_indices = predictions["test_indices"].astype(np.int64)
    test_pred = predictions["test_predicted_uv"].astype(np.float64)
    test_target = data["uv"][test_indices].astype(np.float64)
    test_visible = data["visible"][test_indices].astype(bool)
    test_errors = np.linalg.norm(test_pred - test_target, axis=2)
    main_by_id = {row["sample_id"]: row for row in dataset["main_samples"]}
    test_sample_ids = data["sample_ids"][test_indices].astype(str).tolist()
    test_rows = [main_by_id[sample_id] for sample_id in test_sample_ids]
    three_d = evaluate_3d(dataset_root, test_rows, test_pred, test_visible)

    reason_codes = {int(value): key for key, value in cache_report["reason_codes"].items()}
    reason_metrics = {}
    for code in sorted(set(data["reason_code"][test_indices].reshape(-1).tolist())):
        selected = data["reason_code"][test_indices] == code
        reason_metrics[reason_codes[int(code)]] = pixel_summary(test_errors[selected])
    per_point = {
        str(point_id): pixel_summary(test_errors[:, index][test_visible[:, index]])
        for index, point_id in enumerate(data["point_ids"].tolist())
    }
    worst = []
    for sample_index, sample_id in enumerate(test_sample_ids):
        for point_index, point_id in enumerate(data["point_ids"].tolist()):
            if test_visible[sample_index, point_index]:
                worst.append({
                    "sample_id": sample_id,
                    "point_id": str(point_id),
                    "pixel_error": float(test_errors[sample_index, point_index]),
                    "camera_id": str(data["camera_ids"][test_indices[sample_index]]),
                    "shape_id": str(data["shape_ids"][test_indices[sample_index]]),
                    "pose_id": str(data["pose_ids"][test_indices[sample_index]]),
                })
    worst.sort(key=lambda item: item["pixel_error"], reverse=True)

    challenge_pred = predictions["challenge_predicted_uv"].astype(np.float64)
    challenge_target = data["challenge_uv"].astype(np.float64)
    challenge_visible = data["challenge_visible"].astype(bool)
    challenge_errors = np.linalg.norm(challenge_pred - challenge_target, axis=2)
    challenge_by_id = {row["sample_id"]: row for row in dataset["challenge_samples"]}
    challenge_ids = data["challenge_sample_ids"].astype(str).tolist()
    challenge_rows = [challenge_by_id[sample_id] for sample_id in challenge_ids]
    challenge_3d = evaluate_3d(dataset_root, challenge_rows, challenge_pred, challenge_visible)

    independent = {
        "schema": "engineering-pilot-independent-evaluation-v1",
        "medical_truth": False,
        "split_id": read_json(training / "training_config.json")["split_id"],
        "test": {
            "visible_2d": pixel_summary(test_errors[test_visible]),
            "by_camera": group_errors(test_errors, test_visible, data["camera_ids"][test_indices].astype(str)),
            "by_shape": group_errors(test_errors, test_visible, data["shape_ids"][test_indices].astype(str)),
            "by_pose": group_errors(test_errors, test_visible, data["pose_ids"][test_indices].astype(str)),
            "by_point": per_point,
            "diagnostic_by_visibility_reason": reason_metrics,
            "depth_to_3d": {key: value for key, value in three_d.items() if key != "details"},
        },
        "challenge": {
            "challenge_only_not_training": True,
            "visible_2d": pixel_summary(challenge_errors[challenge_visible]),
            "depth_to_3d": {key: value for key, value in challenge_3d.items() if key != "details"},
        },
        "interpretation": "Only VISIBLE points are training/evaluation targets. Other reason metrics are diagnostics because their heatmap loss weight is zero.",
    }
    write_json(training / "independent_evaluation.json", independent)
    write_json(training / "failure_map.json", {
        "schema": "engineering-pilot-failure-map-v1",
        "medical_truth": False,
        "split_id": independent["split_id"],
        "by_camera": independent["test"]["by_camera"],
        "by_shape": independent["test"]["by_shape"],
        "by_pose": independent["test"]["by_pose"],
        "by_point": independent["test"]["by_point"],
        "by_visibility_reason_diagnostic": reason_metrics,
        "worst_20_visible_instances": worst[:20],
    })

    visual_dir = training / "visuals"
    chosen_indices = np.linspace(0, len(test_rows) - 1, min(6, len(test_rows)), dtype=int)
    visuals = []
    tiles = []
    for index in chosen_indices:
        row = test_rows[index]
        labels = read_json(dataset_root / row["geometry_relative_directory"] / "labels.json")
        target = visual_dir / f"{row['sample_id']}_prediction.png"
        draw_overlay(dataset_root / row["rgb"]["relative_path"], labels, test_pred[index], target)
        visuals.append({"sample_id": row["sample_id"], "relative_path": target.relative_to(training).as_posix()})
        with Image.open(target) as image:
            tiles.append(image.convert("RGB").copy())
    montage = Image.new("RGB", (640 * 3, 512 * 2), (28, 28, 28))
    for index, image in enumerate(tiles):
        montage.paste(image.resize((640, 512), Image.Resampling.LANCZOS), ((index % 3) * 640, (index // 3) * 512))
    montage_path = visual_dir / "test_prediction_montage.png"
    montage.save(montage_path)
    challenge_visuals = []
    challenge_tiles = []
    challenge_indices = np.linspace(0, len(challenge_rows) - 1, min(6, len(challenge_rows)), dtype=int)
    for index in challenge_indices:
        row = challenge_rows[index]
        labels = read_json(dataset_root / row["geometry_relative_directory"] / "labels.json")
        target = visual_dir / f"{row['sample_id']}_challenge_prediction.png"
        draw_overlay(dataset_root / row["rgb"]["relative_path"], labels, challenge_pred[index], target)
        challenge_visuals.append({"sample_id": row["sample_id"], "relative_path": target.relative_to(training).as_posix()})
        with Image.open(target) as image:
            challenge_tiles.append(image.convert("RGB").copy())
    challenge_montage = Image.new("RGB", (640 * 3, 512 * 2), (28, 28, 28))
    for index, image in enumerate(challenge_tiles):
        challenge_montage.paste(image.resize((640, 512), Image.Resampling.LANCZOS), ((index % 3) * 640, (index // 3) * 512))
    challenge_montage_path = visual_dir / "challenge_prediction_montage.png"
    challenge_montage.save(challenge_montage_path)
    write_json(training / "visual_index.json", {
        "schema": "engineering-pilot-prediction-visual-index-v1",
        "items": visuals,
        "montage": montage_path.relative_to(training).as_posix(),
        "challenge_items": challenge_visuals,
        "challenge_montage": challenge_montage_path.relative_to(training).as_posix(),
    })

    reported = read_json(training / "metrics.json")["reports"]["test"]["visible_metrics"]
    independently_computed = independent["test"]["visible_2d"]
    checks = {
        "training_verification_passed": train_verification["passed"],
        "test_prediction_shape": test_pred.shape == test_target.shape == test_visible.shape + (2,),
        "reported_count_matches": int(reported["count"]) == independently_computed["count"],
        "reported_mean_matches": abs(float(reported["mean_px"]) - independently_computed["mean"]) <= 1e-5,
        "visible_depth_to_3d_executed": three_d["valid_3d_count"] > 0,
        "challenge_kept_separate": all(row["partition"] == "challenge" for row in challenge_rows),
        "visuals_created": len(visuals) > 0,
    }
    write_json(training / "independent_verification.json", {
        "schema": "engineering-pilot-independent-verification-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "performance_gate": "No accuracy threshold in V1; low metrics remain valid failure-map evidence.",
        "truth_status": {"kind": "ENGINEERING_MODEL_EVALUATION", "medical_truth": False, "medical_validated": False},
    })
    print(json.dumps({
        "INDEPENDENT_EVAL": "PASS" if all(checks.values()) else "FAIL",
        "split": independent["split_id"],
        "test_mean_px": independent["test"]["visible_2d"]["mean"],
        "test_valid_3d": three_d["valid_3d_count"],
        "challenge_mean_px": independent["challenge"]["visible_2d"]["mean"],
    }, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
