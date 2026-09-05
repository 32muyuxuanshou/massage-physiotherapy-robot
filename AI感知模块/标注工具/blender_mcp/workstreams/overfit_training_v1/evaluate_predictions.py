from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def draw_curve(curve: list[dict], output: Path) -> None:
    width, height = 900, 520
    margin = 65
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((margin, 30, width - 25, height - margin), outline="black")
    epochs = [int(row["epoch"]) for row in curve]
    values = [max(1e-4, float(row["mean_pixel_error"])) for row in curve]
    log_values = [math.log10(value) for value in values]
    xmin, xmax = min(epochs), max(epochs) or 1
    ymin, ymax = min(log_values), max(log_values)
    if ymax <= ymin:
        ymax = ymin + 1
    coords = []
    for epoch, value in zip(epochs, log_values):
        x = margin + (epoch - xmin) / (xmax - xmin) * (width - margin - 25)
        y = 30 + (ymax - value) / (ymax - ymin) * (height - margin - 30)
        coords.append((x, y))
    if len(coords) > 1:
        draw.line(coords, fill=(28, 94, 168), width=3)
    draw.text((margin, 5), "Same-set mean pixel error (log10 scale)", fill="black")
    draw.text((width // 2 - 50, height - 35), "Epoch", fill="black")
    draw.text((5, 35), f"max {10**ymax:.3f}px", fill="black")
    draw.text((5, height - margin - 10), f"min {10**ymin:.3f}px", fill="black")
    canvas.save(output)


def make_overlay(image_path: Path, target: np.ndarray, prediction: np.ndarray, output: Path) -> None:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    for index, (gt, pred) in enumerate(zip(target, prediction), start=1):
        gx, gy = map(float, gt)
        px, py = map(float, pred)
        draw.line((gx, gy, px, py), fill=(255, 215, 0), width=2)
        draw.ellipse((gx - 4, gy - 4, gx + 4, gy + 4), outline=(0, 255, 0), width=2)
        draw.ellipse((px - 3, py - 3, px + 3, py + 3), outline=(255, 0, 0), width=2)
        draw.text((px + 4, py - 5), str(index), fill=(255, 255, 255))
    image.thumbnail((640, 512), Image.Resampling.LANCZOS)
    image.save(output)


def make_heatmap(prediction: np.ndarray, width: int, height: int, output: Path) -> None:
    heat_w, heat_h = 320, 256
    yy, xx = np.mgrid[0:heat_h, 0:heat_w]
    heat = np.zeros((heat_h, heat_w), dtype=np.float32)
    for u, v in prediction:
        x = float(u) / width * heat_w
        y = float(v) / height * heat_h
        heat += np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 2.0**2))
    heat = np.clip(heat / max(float(heat.max()), 1e-8), 0, 1)
    rgb = np.zeros((heat_h, heat_w, 3), dtype=np.uint8)
    rgb[..., 0] = np.asarray(255 * heat, dtype=np.uint8)
    rgb[..., 1] = np.asarray(255 * np.sqrt(heat), dtype=np.uint8)
    Image.fromarray(rgb, "RGB").save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = read_json(args.output / "dataset_manifest.json")
    metrics = read_json(args.output / "training_metrics.json")
    predictions = np.load(args.output / "predictions.npz", allow_pickle=False)
    pred_uv = predictions["predicted_uv"].astype(np.float64)
    target_uv = predictions["target_uv"].astype(np.float64)
    sample_ids = predictions["sample_ids"].tolist()
    point_ids = predictions["point_ids"].tolist()
    manifest_by_id = {item["sample_id"]: item for item in manifest["samples"]}

    details = []
    invalid_count = 0
    xyz_errors = []
    depth_z_errors = []
    for sample_index, sample_id in enumerate(sample_ids):
        item = manifest_by_id[str(sample_id)]
        paths = item["geometry_inputs"]
        labels = read_json(Path(paths["labels"]["path"]))
        depth = np.load(Path(paths["depth"]["path"]), allow_pickle=False)
        with Image.open(Path(paths["depth_valid_mask"]["path"])) as image:
            valid = np.asarray(image.convert("L"), dtype=np.uint8)
        with Image.open(Path(paths["skin_mask"]["path"])) as image:
            skin = np.asarray(image.convert("L"), dtype=np.uint8)
        intrinsics = labels["camera"]["intrinsics"]
        width, height = item["resolution"]
        for point_index, point_id in enumerate(point_ids):
            u, v = map(float, pred_uv[sample_index, point_index])
            col, row = int(math.floor(u)), int(math.floor(v))
            valid_prediction = 0 <= col < width and 0 <= row < height
            reason = "VALID"
            if not valid_prediction:
                reason = "OUT_OF_FRAME"
            elif float(depth[row, col]) <= 0 or valid[row, col] != 255:
                valid_prediction = False
                reason = "INVALID_DEPTH"
            elif skin[row, col] != 255:
                valid_prediction = False
                reason = "NON_SKIN_FIRST_SURFACE"
            gt_xyz = np.asarray(labels["points"][point_index]["xyz_camera_opencv_m"], dtype=np.float64)
            predicted_xyz = None
            xyz_error = None
            z_error = None
            depth_value = None
            if valid_prediction:
                depth_value = float(depth[row, col])
                predicted_xyz = [
                    (u - float(intrinsics["cx"])) * depth_value / float(intrinsics["fx"]),
                    (v - float(intrinsics["cy"])) * depth_value / float(intrinsics["fy"]),
                    depth_value,
                ]
                xyz_error = float(np.linalg.norm(np.asarray(predicted_xyz) - gt_xyz))
                z_error = abs(depth_value - float(gt_xyz[2]))
                xyz_errors.append(xyz_error)
                depth_z_errors.append(z_error)
            else:
                invalid_count += 1
            details.append({
                "sample_id": str(sample_id),
                "point_id": str(point_id),
                "target_uv": target_uv[sample_index, point_index].tolist(),
                "predicted_uv": [u, v],
                "pixel_error": float(np.linalg.norm(pred_uv[sample_index, point_index] - target_uv[sample_index, point_index])),
                "sample_pixel_col_row_floor": [col, row],
                "depth_valid": valid_prediction,
                "invalid_reason": None if valid_prediction else reason,
                "depth_z_m": depth_value,
                "predicted_xyz_camera_m": predicted_xyz,
                "target_xyz_camera_m": gt_xyz.tolist(),
                "depth_z_error_m": z_error,
                "xyz_camera_error_m": xyz_error,
            })

    evaluation = {
        "schema": "predicted-uv-depth-3d-evaluation-v1",
        "purpose": "same-set engineering overfit evaluation only",
        "medical_truth": False,
        "sampling_contract": {
            "method": "floor(predicted_u), floor(predicted_v), no interpolation and no nearest-valid search",
            "valid_if": "inside image AND depth>0 AND depth_valid_mask=255 AND skin_mask=255",
            "invalid_handling": "record invalid_reason and omit 3D error; never replace with GT depth or a neighboring pixel",
            "backprojection": "OpenCV X=(u-cx)Z/fx, Y=(v-cy)Z/fy, Z=scene_depth_z",
        },
        "point_instance_count": len(details),
        "valid_3d_count": len(xyz_errors),
        "invalid_3d_count": invalid_count,
        "mean_xyz_camera_error_m": float(np.mean(xyz_errors)) if xyz_errors else None,
        "median_xyz_camera_error_m": float(np.median(xyz_errors)) if xyz_errors else None,
        "max_xyz_camera_error_m": max(xyz_errors, default=None),
        "mean_depth_z_error_m": float(np.mean(depth_z_errors)) if depth_z_errors else None,
        "max_depth_z_error_m": max(depth_z_errors, default=None),
        "details": details,
        "claims": {
            "predicted_uv_to_depth_to_3d_pipeline_executed": len(xyz_errors) > 0,
            "generalization": False,
            "medical_accuracy": False,
        },
    }
    (args.output / "predicted_uv_depth_3d_metrics.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.output / "per_instance_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        columns = ["sample_id", "point_id", "pixel_error", "depth_valid", "invalid_reason", "depth_z_error_m", "xyz_camera_error_m"]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for item in details:
            writer.writerow({key: item[key] for key in columns})

    curve = []
    with (args.output / "training_curve.csv").open("r", newline="", encoding="utf-8") as handle:
        curve = list(csv.DictReader(handle))
    draw_curve(curve, args.output / "training_curve.png")
    visual_dir = args.output / "visual_evidence"
    visual_dir.mkdir(exist_ok=True)
    representative = [0, 9, 10, 19, 20, 29]
    overlay_images = []
    for index in representative:
        sample_id = str(sample_ids[index])
        image_path = Path(manifest_by_id[sample_id]["model_input"]["path"])
        overlay_path = visual_dir / f"{sample_id}_prediction_overlay.png"
        heatmap_path = visual_dir / f"{sample_id}_predicted_heatmap.png"
        make_overlay(image_path, target_uv[index], pred_uv[index], overlay_path)
        make_heatmap(pred_uv[index], manifest_by_id[sample_id]["resolution"][0], manifest_by_id[sample_id]["resolution"][1], heatmap_path)
        overlay_images.append(Image.open(overlay_path).copy())
    tile_w, tile_h = 640, 512
    montage = Image.new("RGB", (tile_w * 3, tile_h * 2), (30, 30, 30))
    for index, image in enumerate(overlay_images):
        montage.paste(image.resize((tile_w, tile_h), Image.Resampling.LANCZOS), ((index % 3) * tile_w, (index // 3) * tile_h))
    montage.save(args.output / "prediction_montage.png")

    verification = {
        "schema": "training-pipeline-v1-verification",
        "passed": bool(
            manifest["sample_count"] == 30
            and manifest["point_count_per_sample"] == 20
            and manifest["medical_truth"] is False
            and manifest["gt_uv_depth_contract"]["passed"] is True
            and metrics["claims"]["training_pipeline_can_memorize_30_engineering_samples"] is True
            and invalid_count == 0
        ),
        "checks": {
            "immutable_30_sample_pairing": manifest["sample_count"] == 30,
            "twenty_points_fixed_order": manifest["point_count_per_sample"] == 20,
            "medical_truth_false": manifest["medical_truth"] is False,
            "overlay_excluded_from_model_input": manifest["model_input_contract"]["forbidden"][0] == "overlay.png",
            "gt_uv_depth_xyz_contract_passed": manifest["gt_uv_depth_contract"]["passed"] is True,
            "same_set_overfit_passed": metrics["claims"]["training_pipeline_can_memorize_30_engineering_samples"] is True,
            "predicted_uv_depth_3d_all_valid": invalid_count == 0,
        },
        "headline_metrics": {
            "mean_pixel_error": metrics["mean_pixel_error"],
            "max_pixel_error": metrics["max_pixel_error"],
            "pck_same_set": metrics["pck_same_set"],
            "valid_3d_count": len(xyz_errors),
            "invalid_3d_count": invalid_count,
            "mean_xyz_camera_error_m": evaluation["mean_xyz_camera_error_m"],
            "max_xyz_camera_error_m": evaluation["max_xyz_camera_error_m"],
        },
        "allowed_conclusion": "The deterministic RGB-only training pipeline can memorize these same 30 engineering samples and its predicted UV can enter the frozen Depth-to-3D path.",
        "prohibited_conclusions": ["generalization", "medical accuracy", "clinical usability", "robot execution safety"],
    }
    (args.output / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": verification["passed"], **verification["headline_metrics"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
