from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image


SCENE_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块\outputs\交付文件\2026-08-28_20-21-54")
LABEL_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块\outputs\交付文件\2026-08-29_16-21-55")
EXPECTED_COUNT = 30
EXPECTED_POINTS = 20
INPUT_WIDTH = 40
INPUT_HEIGHT = 32


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_record(path: Path) -> dict:
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def fail(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def build(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    scene_index = read_json(SCENE_ROOT / "dataset_index.json")
    derived_index = read_json(LABEL_ROOT / "derived_dataset_index.json")
    fail(len(scene_index) == EXPECTED_COUNT, f"scene index count is {len(scene_index)}")
    fail(len(derived_index) == EXPECTED_COUNT, f"derived index count is {len(derived_index)}")
    derived_by_id = {item["sample_id"]: item for item in derived_index}
    fail(len(derived_by_id) == EXPECTED_COUNT, "duplicate sample_id in derived index")

    samples: list[dict] = []
    images: list[np.ndarray] = []
    uv_all: list[np.ndarray] = []
    xyz_all: list[np.ndarray] = []
    visible_all: list[np.ndarray] = []
    point_order: list[str] | None = None
    gt_details: list[dict] = []
    max_depth_error = 0.0
    max_backprojection_error = 0.0
    overlay_paths_seen: list[str] = []

    for scene_entry in scene_index:
        sample_id = scene_entry["sample_id"]
        fail(sample_id in derived_by_id, f"missing derived sample {sample_id}")
        derived = derived_by_id[sample_id]
        for key in ("case", "shape_id", "pose_id", "camera_id"):
            fail(scene_entry[key] == derived[key], f"{sample_id} {key} mismatch")

        scene_dir = SCENE_ROOT / "samples" / sample_id
        label_dir = LABEL_ROOT / "samples" / sample_id
        paths = {
            "rgb": scene_dir / "rgb.png",
            "depth": scene_dir / "scene_depth_z.npy",
            "depth_valid_mask": scene_dir / "depth_valid_mask.png",
            "skin_mask": scene_dir / "skin_mask.png",
            "render_metadata": scene_dir / "render_metadata.json",
            "labels": label_dir / "labels.json",
        }
        for role, path in paths.items():
            fail(path.is_file(), f"{sample_id} missing {role}: {path}")
        # The derived delivery contains copied scene buffers. Their hashes must
        # still match the authoritative scene/RGB-D delivery byte for byte.
        copied_hashes = {}
        for name in ("rgb.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png", "render_metadata.json"):
            source = scene_dir / name
            copied = label_dir / name
            fail(copied.is_file(), f"{sample_id} missing derived copy {name}")
            source_hash = sha256(source)
            copied_hash = sha256(copied)
            fail(source_hash == copied_hash, f"{sample_id} copied buffer differs: {name}")
            copied_hashes[name] = source_hash

        labels = read_json(paths["labels"])
        metadata = read_json(paths["render_metadata"])
        fail(labels.get("medical_truth") is False, f"{sample_id} medical_truth must be false")
        fail(labels.get("derivation", {}).get("truth_status") == "engineering_reference", f"{sample_id} truth status mismatch")
        fail(labels.get("source_scene_snapshot_sha256") == scene_entry["snapshot_sha256"], f"{sample_id} snapshot hash mismatch")
        points = labels.get("points") or []
        fail(len(points) == EXPECTED_POINTS, f"{sample_id} has {len(points)} points")
        ids = [str(point["point_id"]) for point in points]
        if point_order is None:
            point_order = ids
        fail(ids == point_order, f"{sample_id} point order differs")
        fail(all("medical_validated=false" in str(point.get("notes", "")) for point in points), f"{sample_id} contains point without engineering-truth notice")

        with Image.open(paths["rgb"]) as image:
            image_rgb = image.convert("RGB")
            width, height = image_rgb.size
            reduced = image_rgb.resize((INPUT_WIDTH, INPUT_HEIGHT), Image.Resampling.BILINEAR)
            images.append(np.asarray(reduced, dtype=np.uint8))
        intrinsics = labels["camera"]["intrinsics"]
        fail(int(intrinsics["width"]) == width and int(intrinsics["height"]) == height, f"{sample_id} RGB/intrinsics resolution mismatch")
        fail(metadata["camera"]["intrinsics"] == intrinsics, f"{sample_id} metadata/labels intrinsics mismatch")

        depth = np.load(paths["depth"], allow_pickle=False)
        fail(depth.shape == (height, width), f"{sample_id} depth shape mismatch")
        with Image.open(paths["depth_valid_mask"]) as image:
            valid = np.asarray(image.convert("L"), dtype=np.uint8)
        with Image.open(paths["skin_mask"]) as image:
            skin = np.asarray(image.convert("L"), dtype=np.uint8)
        fail(valid.shape == depth.shape == skin.shape, f"{sample_id} buffer alignment mismatch")

        sample_uv = []
        sample_xyz = []
        sample_visible = []
        sample_depth_errors = []
        sample_backprojection_errors = []
        for point in points:
            u, v = map(float, point["uv_pixel_opencv"])
            xyz = np.asarray(point["xyz_camera_opencv_m"], dtype=np.float64)
            visible = bool(point["visible"])
            fail(math.isfinite(u) and math.isfinite(v), f"{sample_id}/{point['point_id']} non-finite UV")
            fail(visible, f"{sample_id}/{point['point_id']} is not visible; this frozen overfit set expects all points visible")
            col, row = int(math.floor(u)), int(math.floor(v))
            fail(0 <= col < width and 0 <= row < height, f"{sample_id}/{point['point_id']} outside image")
            observed = float(depth[row, col])
            fail(observed > 0 and valid[row, col] == 255 and skin[row, col] == 255, f"{sample_id}/{point['point_id']} invalid/foreign depth pixel")
            lifted = np.asarray([
                (u - float(intrinsics["cx"])) * observed / float(intrinsics["fx"]),
                (v - float(intrinsics["cy"])) * observed / float(intrinsics["fy"]),
                observed,
            ])
            depth_error = abs(observed - float(xyz[2]))
            backprojection_error = float(np.linalg.norm(lifted - xyz))
            fail(depth_error <= 0.003 and backprojection_error <= 0.003, f"{sample_id}/{point['point_id']} GT depth contract failed")
            max_depth_error = max(max_depth_error, depth_error)
            max_backprojection_error = max(max_backprojection_error, backprojection_error)
            sample_depth_errors.append(depth_error)
            sample_backprojection_errors.append(backprojection_error)
            gt_details.append({
                "sample_id": sample_id,
                "point_id": point["point_id"],
                "uv": [u, v],
                "pixel_col_row_floor": [col, row],
                "depth_z_m": observed,
                "depth_error_m": depth_error,
                "backprojection_error_m": backprojection_error,
            })
            sample_uv.append([u, v])
            sample_xyz.append(xyz.tolist())
            sample_visible.append(visible)
        uv_all.append(np.asarray(sample_uv, dtype=np.float32))
        xyz_all.append(np.asarray(sample_xyz, dtype=np.float32))
        visible_all.append(np.asarray(sample_visible, dtype=np.bool_))

        # Deliberately record but do not hash or expose overlay as a model input.
        for forbidden in (scene_dir / "overlay.png", label_dir / "overlay.png"):
            if forbidden.exists():
                overlay_paths_seen.append(str(forbidden))
        samples.append({
            "sample_id": sample_id,
            "case": scene_entry["case"],
            "shape_id": scene_entry["shape_id"],
            "pose_id": scene_entry["pose_id"],
            "camera_id": scene_entry["camera_id"],
            "resolution": [width, height],
            "source_scene_snapshot_sha256": scene_entry["snapshot_sha256"],
            "model_input": file_record(paths["rgb"]),
            "geometry_inputs": {key: file_record(paths[key]) for key in ("depth", "depth_valid_mask", "skin_mask", "render_metadata", "labels")},
            "derived_copy_hashes": copied_hashes,
            "point_count": len(points),
            "point_order_sha256": hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest(),
            "visible_count": sum(sample_visible),
            "gt_depth_max_error_m": max(sample_depth_errors),
            "gt_backprojection_max_error_m": max(sample_backprojection_errors),
        })

    fail(len(samples) == EXPECTED_COUNT, "manifest sample count mismatch")
    manifest = {
        "schema": "training-dataset-manifest-v1",
        "immutable": True,
        "purpose": "30-sample engineering overfit pipeline only",
        "medical_truth": False,
        "medical_validated": False,
        "source_scene_root": str(SCENE_ROOT),
        "source_label_root": str(LABEL_ROOT),
        "sample_count": len(samples),
        "point_count_per_sample": EXPECTED_POINTS,
        "point_order": point_order,
        "pairing_keys": ["sample_id", "case", "shape_id", "pose_id", "camera_id", "resolution", "source_scene_snapshot_sha256"],
        "model_input_contract": {
            "allowed": ["authoritative_scene_delivery/rgb.png"],
            "forbidden": ["overlay.png", "depth", "mask", "labels", "sample_id", "case/profile metadata"],
            "preprocess": f"RGB -> grayscale luminance -> bilinear {INPUT_WIDTH}x{INPUT_HEIGHT} -> dataset standardization",
            "overlay_files_detected_but_excluded": len(overlay_paths_seen),
        },
        "gt_uv_depth_contract": {
            "pixel_coordinate": "continuous edge coordinates; pixel center is (column+0.5,row+0.5)",
            "sampling": "floor(u), floor(v), no fallback/search/interpolation",
            "invalid_depth": "depth<=0 or valid_mask!=255 or skin_mask!=255 is invalid",
            "backprojection": "X=(u-cx)*Z/fx; Y=(v-cy)*Z/fy; Z=depth",
            "threshold_m": 0.003,
            "max_depth_error_m": max_depth_error,
            "max_backprojection_error_m": max_backprojection_error,
            "passed": True,
        },
        "samples": samples,
    }
    (output / "dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "gt_uv_depth_contract.json").write_text(json.dumps({
        "schema": "gt-uv-depth-contract-evidence-v1",
        "medical_truth": False,
        "summary": manifest["gt_uv_depth_contract"],
        "point_instance_count": len(gt_details),
        "details": gt_details,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(
        output / "training_cache.npz",
        images_rgb=np.stack(images),
        uv=np.stack(uv_all),
        xyz_camera=np.stack(xyz_all),
        visible=np.stack(visible_all),
        sample_ids=np.asarray([item["sample_id"] for item in samples]),
        point_ids=np.asarray(point_order),
        original_width=np.int32(samples[0]["resolution"][0]),
        original_height=np.int32(samples[0]["resolution"][1]),
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(args.output)
    print(json.dumps({
        "passed": True,
        "sample_count": manifest["sample_count"],
        "point_count": manifest["point_count_per_sample"],
        "max_gt_depth_error_m": manifest["gt_uv_depth_contract"]["max_depth_error_m"],
        "max_gt_backprojection_error_m": manifest["gt_uv_depth_contract"]["max_backprojection_error_m"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
