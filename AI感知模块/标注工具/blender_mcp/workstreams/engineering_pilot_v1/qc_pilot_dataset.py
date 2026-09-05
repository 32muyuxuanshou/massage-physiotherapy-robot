from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.item() if isinstance(value, np.generic) else str(value),
        )
        + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path) -> dict:
    target = root / "SHA256SUMS.txt"
    failures = []
    rows = [line for line in target.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    for line in rows:
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != expected.lower():
            failures.append(relative)
    return {"passed": not failures, "entries": len(rows), "failures": failures, "manifest_sha256": sha256(target)}


def build_manifest(root: Path) -> dict:
    target = root / "SHA256SUMS.txt"
    rows = [
        f"{sha256(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != target
    ]
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"entries": len(rows), "manifest_sha256": sha256(target)}


def base_qc(root: Path, base: dict, weights: dict, point_order: list[str]) -> dict:
    directory = root / "base_geometry" / base["base_geometry_id"]
    hashes = {}
    hash_ok = True
    for name, info in base["files"].items():
        path = root / info["relative_path"]
        actual = sha256(path)
        hashes[name] = actual
        hash_ok = hash_ok and actual == info["sha256"] == info["source_sha256"]
    labels = read_json(directory / "labels.json")
    depth = np.load(directory / "scene_depth_z.npy", allow_pickle=False)
    with Image.open(directory / "depth_valid_mask.png") as image:
        valid = np.asarray(image.convert("L"), dtype=np.uint8)
    with Image.open(directory / "skin_mask.png") as image:
        skin = np.asarray(image.convert("L"), dtype=np.uint8)
    width = int(labels["camera"]["intrinsics"]["width"])
    height = int(labels["camera"]["intrinsics"]["height"])
    checks = {
        "hashes_match_parent": hash_ok,
        "resolution_consistent": depth.shape == valid.shape == skin.shape == (height, width),
        "depth_float32": depth.dtype == np.float32,
        "point_order": [point["point_id"] for point in labels["points"]] == point_order,
        "medical_truth_false": labels.get("medical_truth") is False,
    }
    point_rows = []
    for point in labels["points"]:
        reason = point["visibility_reason"]
        visible = reason == "VISIBLE"
        u, v = map(float, point["uv_pixel_opencv"])
        in_frame = 0.0 <= u < width and 0.0 <= v < height
        col, row = int(math.floor(u)), int(math.floor(v))
        observed = float(depth[row, col]) if in_frame else None
        point_z = float(point["camera_depth_z_m"])
        depth_error = abs(observed - point_z) if visible and observed is not None else None
        item_checks = {
            "loss_weight": reason in weights and float(weights[reason]) == (1.0 if visible else 0.0),
            "visible_flag": bool(point["visible"]) == visible,
        }
        if reason == "VISIBLE":
            item_checks.update({
                "in_frame": in_frame,
                "valid_depth": in_frame and valid[row, col] == 255 and observed is not None and observed > 0,
                "skin_first_surface": in_frame and skin[row, col] == 255,
                "depth_error_le_3mm": depth_error is not None and depth_error <= 0.003,
            })
        elif reason == "OUT_OF_FRAME":
            item_checks["outside_frame"] = not in_frame
        elif reason == "EXTERNAL_OCCLUDED":
            item_checks.update({
                "in_frame": in_frame,
                "valid_scene_depth": in_frame and valid[row, col] == 255 and observed is not None and observed > 0,
                "not_skin_first_surface": in_frame and skin[row, col] == 0,
                "occluder_in_front": observed is not None and 0 < observed < point_z,
                "ray_hit_external": point.get("ray_hit_object") == "__ACU_EXTERNAL_OCCLUDER__",
            })
        elif reason == "BACK_FACING":
            item_checks["front_facing_false"] = point.get("front_facing") is False
        elif reason == "SELF_OCCLUDED":
            item_checks["ray_hit_target_skin"] = point.get("ray_hit_object") == point.get("target_mesh")
        point_rows.append({
            "point_id": point["point_id"],
            "reason": reason,
            "passed": all(item_checks.values()),
            "checks": item_checks,
            "depth_error_m": depth_error,
        })
    checks["all_point_contracts"] = all(row["passed"] for row in point_rows)
    max_depth = max((row["depth_error_m"] for row in point_rows if row["depth_error_m"] is not None), default=0.0)
    return {
        "base_geometry_id": base["base_geometry_id"],
        "passed": all(checks.values()),
        "checks": checks,
        "reason_counts": dict(Counter(row["reason"] for row in point_rows)),
        "max_visible_depth_error_m": max_depth,
        "points": point_rows,
        "hashes": hashes,
    }


def split_qc(dataset: dict, splits: dict) -> dict:
    rows = {row["sample_id"]: row for row in dataset["main_samples"]}
    checks = {}
    details = {}
    for split_id, split in splits["splits"].items():
        case_sets = {key: set(split[f"{key}_case_ids"]) for key in ("train", "val", "test")}
        sample_sets = {key: set(split["sample_ids"][key]) for key in ("train", "val", "test")}
        split_checks = {
            "case_disjoint": not (
                case_sets["train"] & case_sets["val"]
                or case_sets["train"] & case_sets["test"]
                or case_sets["val"] & case_sets["test"]
            ),
            "sample_disjoint": not (
                sample_sets["train"] & sample_sets["val"]
                or sample_sets["train"] & sample_sets["test"]
                or sample_sets["val"] & sample_sets["test"]
            ),
            "all_main_samples_once": set().union(*sample_sets.values()) == set(rows),
            "group_membership_exact": all(
                all(rows[sample_id]["case_id"] in case_sets[bucket] for sample_id in sample_sets[bucket])
                for bucket in sample_sets
            ),
        }
        split_checks["all_camera_profiles_represented"] = all(
            {rows[sample_id]["camera_id"] for sample_id in sample_sets[bucket]}
            == {"NORMAL_MAIN", "C1_MILD_OBLIQUE", "C2_EDGE_CROP", "C3_EXTERNAL_OCCLUDER"}
            for bucket in sample_sets
        )
        details[split_id] = {"passed": all(split_checks.values()), "checks": split_checks}
        checks[split_id] = details[split_id]["passed"]
    return {"passed": all(checks.values()), "checks": checks, "details": details}


def draw_overlay(rgb_path: Path, labels: dict, output: Path) -> None:
    with Image.open(rgb_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    colors = {
        "VISIBLE": (0, 255, 80),
        "OUT_OF_FRAME": (255, 210, 0),
        "EXTERNAL_OCCLUDED": (255, 60, 60),
        "SELF_OCCLUDED": (255, 0, 200),
        "BACK_FACING": (255, 145, 0),
    }
    for index, point in enumerate(labels["points"], start=1):
        u, v = map(float, point["uv_pixel_opencv"])
        if not (0 <= u < image.width and 0 <= v < image.height):
            continue
        color = colors.get(point["visibility_reason"], (255, 255, 255))
        draw.ellipse((u - 5, v - 5, u + 5, v + 5), outline=color, width=3)
        draw.text((u + 6, v - 6), str(index), fill=color)
    image.thumbnail((640, 512), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def visual_review_assets(root: Path, dataset: dict) -> list[dict]:
    rows = dataset["main_samples"] + dataset["challenge_samples"]
    preferred_case = "C03_LONG_NARROW__D06_THORAX_EXTENSION_P4"
    selected = []
    for camera in ("NORMAL_MAIN", "C1_MILD_OBLIQUE", "C2_EDGE_CROP", "C3_EXTERNAL_OCCLUDER", "C4_SELF_OCCLUSION_STRESS"):
        candidates = [row for row in rows if row["camera_id"] == camera and row["case_id"] == preferred_case and row["variant_ordinal"] == 1]
        if not candidates:
            candidates = [row for row in rows if row["camera_id"] == camera]
        row = candidates[0]
        rgb_path = root / row["rgb"]["relative_path"]
        labels = read_json(root / row["geometry_relative_directory"] / "labels.json")
        target = root / "qc_visuals" / f"{camera}_overlay.png"
        draw_overlay(rgb_path, labels, target)
        selected.append({"camera_id": camera, "sample_id": row["sample_id"], "relative_path": target.relative_to(root).as_posix()})
    tile_w, tile_h = 640, 512
    montage = Image.new("RGB", (tile_w * 3, tile_h * 2), (28, 28, 28))
    for index, item in enumerate(selected):
        with Image.open(root / item["relative_path"]) as image:
            montage.paste(image.convert("RGB").resize((tile_w, tile_h), Image.Resampling.LANCZOS), ((index % 3) * tile_w, (index // 3) * tile_h))
    montage_path = root / "qc_visuals" / "pilot_camera_appearance_montage.png"
    montage.save(montage_path)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    root = args.dataset.resolve()
    original_manifest = verify_manifest(root)
    build = read_json(root / "build_verification.json")
    dataset = read_json(root / "dataset_manifest.json")
    weights_contract = read_json(root / "contracts" / "pilot_visibility_loss_contract_v1.json")
    splits = read_json(root / "contracts" / "evaluation_splits_v1.json")
    weights = weights_contract["heatmap_loss_weights"]
    point_order = weights_contract["point_order"]

    base_reports = []
    for index, base in enumerate(dataset["base_geometry"], start=1):
        report = base_qc(root, base, weights, point_order)
        base_reports.append(report)
        if index % 15 == 0 or index == len(dataset["base_geometry"]):
            print(f"BASE_QC {index}/{len(dataset['base_geometry'])}", flush=True)

    rgb_checks = []
    rgb_hashes = []
    for index, row in enumerate(dataset["main_samples"] + dataset["challenge_samples"], start=1):
        path = root / row["rgb"]["relative_path"]
        actual = sha256(path)
        with Image.open(path) as image:
            resolution = image.size
        rgb_checks.append(actual == row["rgb"]["sha256"] and resolution == (1280, 1024))
        rgb_hashes.append(actual)
        if index % 100 == 0 or index == dataset["main_sample_count"] + dataset["challenge_sample_count"]:
            print(f"RGB_QC {index}/{dataset['main_sample_count'] + dataset['challenge_sample_count']}", flush=True)

    split_report = split_qc(dataset, splits)
    main_camera_counts = Counter(row["camera_id"] for row in dataset["main_samples"])
    base_by_id = {row["base_geometry_id"]: row for row in base_reports}
    aggregate_reasons = Counter()
    by_camera_reasons = defaultdict(Counter)
    for row in dataset["main_samples"]:
        counts = base_by_id[row["base_geometry_id"]]["reason_counts"]
        aggregate_reasons.update(counts)
        by_camera_reasons[row["camera_id"]].update(counts)
    selected_visuals = visual_review_assets(root, dataset)
    max_depth = max(report["max_visible_depth_error_m"] for report in base_reports)
    checks = {
        "original_dataset_manifest_passed": original_manifest["passed"],
        "build_passed": build["passed"],
        "main_count_360": len(dataset["main_samples"]) == 360,
        "challenge_count_12": len(dataset["challenge_samples"]) == 12,
        "main_camera_quotas_exact": main_camera_counts == Counter({
            "NORMAL_MAIN": 144,
            "C1_MILD_OBLIQUE": 108,
            "C2_EDGE_CROP": 54,
            "C3_EXTERNAL_OCCLUDER": 54,
        }),
        "c4_challenge_only": all(row["camera_id"] != "C4_SELF_OCCLUSION_STRESS" for row in dataset["main_samples"])
        and all(row["camera_id"] == "C4_SELF_OCCLUSION_STRESS" for row in dataset["challenge_samples"]),
        "all_base_geometry_passed": all(report["passed"] for report in base_reports),
        "max_visible_depth_error_le_3mm": max_depth <= 0.003,
        "all_rgb_hash_and_resolution_checks": all(rgb_checks),
        "all_rgb_unique": len(set(rgb_hashes)) == len(rgb_hashes),
        "split_qc_passed": split_report["passed"],
        "visual_assets_created": len(selected_visuals) == 5,
    }
    write_json(root / "dataset_statistics.json", {
        "schema": "engineering-pilot-dataset-statistics-v1",
        "medical_truth": False,
        "main_camera_counts": dict(main_camera_counts),
        "main_visibility_reason_counts": dict(aggregate_reasons),
        "main_visibility_reason_counts_by_camera": {key: dict(value) for key, value in by_camera_reasons.items()},
        "main_point_instances": sum(aggregate_reasons.values()),
        "max_visible_depth_error_m": max_depth,
        "rgb_count": len(rgb_hashes),
        "unique_rgb_count": len(set(rgb_hashes)),
    })
    write_json(root / "split_qc_report.json", split_report)
    write_json(root / "base_geometry_qc_report.json", {
        "schema": "engineering-pilot-base-geometry-qc-v1",
        "passed": all(report["passed"] for report in base_reports),
        "base_count": len(base_reports),
        "max_visible_depth_error_m": max_depth,
        "bases": base_reports,
    })
    write_json(root / "visual_review_index.json", {
        "schema": "engineering-pilot-visual-review-index-v1",
        "medical_truth": False,
        "items": selected_visuals,
        "montage": "qc_visuals/pilot_camera_appearance_montage.png",
        "review_required": True,
    })
    write_json(root / "qc_verification.json", {
        "schema": "engineering-pilot-dataset-qc-verification-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "headline": {
            "main_samples": 360,
            "challenge_samples": 12,
            "base_geometry": len(base_reports),
            "unique_rgb": len(set(rgb_hashes)),
            "max_visible_depth_error_mm": max_depth * 1000.0,
        },
        "truth_status": {"kind": "ENGINEERING_QA", "medical_truth": False, "medical_validated": False},
        "next_gate": "Only if this QC passes and representative images are visually accepted may the three grouped generalization baselines train.",
    })
    result = build_manifest(root)
    print(json.dumps({"PILOT_QC": "PASS" if all(checks.values()) else "FAIL", **result}, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
