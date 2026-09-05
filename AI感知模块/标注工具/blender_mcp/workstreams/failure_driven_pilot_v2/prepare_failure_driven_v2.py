from __future__ import annotations

import argparse
import hashlib
import json
import math
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
TRAIN_APPEARANCE_ORDINALS = (0, 1, 2, 3)
HOLDOUT_APPEARANCE_ORDINAL = 4
SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path) -> dict:
    manifest = root / "SHA256SUMS.txt"
    failures = []
    count = 0
    for line in manifest.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        count += 1
        expected, relative = line.split("  ", 1)
        target = root / relative
        if not target.is_file() or sha256(target) != expected.lower():
            failures.append(relative)
    return {"passed": not failures, "entries": count, "failures": failures, "sha256": sha256(manifest)}


def apply_appearance(rgb_path: Path, skin_mask_path: Path, params: dict, output: Path) -> None:
    with Image.open(rgb_path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    with Image.open(skin_mask_path) as image:
        skin = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    skin = np.clip(skin, 0.0, 1.0)[..., None]
    height, width = rgb.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    nx = (xx + 0.5) / width * 2.0 - 1.0
    ny = (yy + 0.5) / height * 2.0 - 1.0
    angle = math.radians(float(params["image_space_gradient_angle_degrees"]))
    gradient = 1.0 + float(params["image_space_gradient_amplitude"]) * (
        nx * math.cos(angle) + ny * math.sin(angle)
    )
    gradient = np.clip(gradient, 0.75, 1.25)[..., None]
    skin_gain = np.asarray(params["skin_rgb_gain"], dtype=np.float32).reshape(1, 1, 3)
    non_skin_gain = np.asarray(params["non_skin_rgb_gain"], dtype=np.float32).reshape(1, 1, 3)
    gain = skin * skin_gain + (1.0 - skin) * non_skin_gain
    adjusted = np.clip(rgb * gain * gradient * float(params["global_exposure"]), 0.0, 1.0)
    adjusted = np.power(adjusted, 1.0 / float(params["gamma"]))
    encoded = np.asarray(np.clip(np.rint(adjusted * 255.0), 0, 255), dtype=np.uint8)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(encoded, mode="RGB").save(output, format="PNG", compress_level=6)


def resized_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB").resize((160, 128), Image.Resampling.BILINEAR), dtype=np.uint8)


def labels_arrays(labels: dict, point_order: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if [point["point_id"] for point in labels["points"]] != point_order:
        raise RuntimeError("Point order differs from frozen V1")
    uv = np.asarray([point["uv_pixel_opencv"] for point in labels["points"]], dtype=np.float32)
    reasons = [point["visibility_reason"] for point in labels["points"]]
    visible = np.asarray([reason == "VISIBLE" for reason in reasons], dtype=np.uint8)
    reason_code = np.asarray([REASON_CODES[reason] for reason in reasons], dtype=np.uint8)
    return uv, visible, reason_code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-dataset", type=Path, required=True)
    parser.add_argument("--v1-cache", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    v1_dataset = args.v1_dataset.resolve()
    v1_cache_path = args.v1_cache.resolve()
    gate = args.gate.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)

    v1_manifest = verify_manifest(v1_dataset)
    gate_manifest = verify_manifest(gate)
    gate_verification = read_json(gate / "final_verification.json")
    if not v1_manifest["passed"] or not gate_manifest["passed"] or not gate_verification["passed"]:
        raise RuntimeError("Frozen inputs failed hash or gate verification")

    v1_dataset_manifest = read_json(v1_dataset / "dataset_manifest.json")
    v1_splits = read_json(v1_dataset / "contracts" / "evaluation_splits_v1.json")
    v1_cache_report = read_json(v1_cache_path.with_suffix(".json"))
    if sha256(v1_cache_path) != v1_cache_report["cache_sha256"]:
        raise RuntimeError("V1 cache changed")
    v1 = np.load(v1_cache_path, allow_pickle=False)
    point_order = v1["point_ids"].astype(str).tolist()

    appearances = {}
    for row in v1_dataset_manifest["main_samples"]:
        ordinal = int(row["variant_ordinal"])
        if ordinal <= HOLDOUT_APPEARANCE_ORDINAL and ordinal not in appearances:
            appearances[ordinal] = row["appearance"]
    if set(appearances) != set(range(HOLDOUT_APPEARANCE_ORDINAL + 1)):
        raise RuntimeError("Could not freeze A00-A04 appearance parameters")

    case_meta = {}
    for row in v1_dataset_manifest["main_samples"]:
        case_meta.setdefault(row["case_id"], {"shape_id": row["shape_id"], "pose_id": row["pose_id"]})

    gate_matrix = read_json(gate / "truncation_matrix_report.json")
    gate_rows = sorted(gate_matrix["samples"], key=lambda item: item["sample_id"])
    if len(gate_rows) != 68 or not all(item["passed"] for item in gate_rows):
        raise RuntimeError("Gate must contain 68 qualified cells")

    train_new = {key: [] for key in (
        "images_rgb", "uv", "visible", "reason_code", "sample_ids", "case_ids",
        "shape_ids", "pose_ids", "camera_ids", "geometry_ids",
    )}
    holdout = {key: [] for key in train_new}
    manifest_train = []
    manifest_holdout = []

    for cell_index, cell in enumerate(gate_rows, start=1):
        case_id = cell["case_id"]
        camera_id = cell["camera_id"]
        if case_id not in case_meta:
            raise RuntimeError(f"Unknown V1 case: {case_id}")
        sample_dir = Path(cell["sample"])
        labels_path = sample_dir / "labels.json"
        rgb_source = sample_dir / "rgb.png"
        skin_path = sample_dir / "skin_mask.png"
        labels = read_json(labels_path)
        uv, visible, reason_code = labels_arrays(labels, point_order)
        geometry_id = f"{case_id}__{camera_id}"

        for ordinal in (*TRAIN_APPEARANCE_ORDINALS, HOLDOUT_APPEARANCE_ORDINAL):
            sample_id = f"TRUNCV2__{case_id}__{camera_id}__A{ordinal:02d}"
            partition = "train_pool" if ordinal in TRAIN_APPEARANCE_ORDINALS else "holdout"
            target = output / "rgb" / partition / f"{sample_id}.png"
            apply_appearance(rgb_source, skin_path, appearances[ordinal], target)
            destination = train_new if ordinal in TRAIN_APPEARANCE_ORDINALS else holdout
            destination["images_rgb"].append(resized_rgb(target))
            destination["uv"].append(uv)
            destination["visible"].append(visible)
            destination["reason_code"].append(reason_code)
            destination["sample_ids"].append(sample_id)
            destination["case_ids"].append(case_id)
            destination["shape_ids"].append(case_meta[case_id]["shape_id"])
            destination["pose_ids"].append(case_meta[case_id]["pose_id"])
            destination["camera_ids"].append(camera_id)
            destination["geometry_ids"].append(geometry_id)
            entry = {
                "sample_id": sample_id,
                "case_id": case_id,
                "shape_id": case_meta[case_id]["shape_id"],
                "pose_id": case_meta[case_id]["pose_id"],
                "camera_id": camera_id,
                "subject_side_clipped": cell["subject_side_clipped"],
                "severity_class": cell["severity_class"],
                "appearance_ordinal": ordinal,
                "rgb_relative_path": target.relative_to(output).as_posix(),
                "rgb_sha256": sha256(target),
                "gate_sample_directory": str(sample_dir),
                "labels_sha256": sha256(labels_path),
            }
            (manifest_train if destination is train_new else manifest_holdout).append(entry)
        if cell_index % 8 == 0 or cell_index == len(gate_rows):
            print(f"TRUNCATION RGB {cell_index}/{len(gate_rows)}", flush=True)

    def array(value: list, dtype=None) -> np.ndarray:
        return np.asarray(value, dtype=dtype)

    new_arrays = {
        "images_rgb": array(train_new["images_rgb"], np.uint8),
        "uv": array(train_new["uv"], np.float32),
        "visible": array(train_new["visible"], np.uint8),
        "reason_code": array(train_new["reason_code"], np.uint8),
        **{key: array(train_new[key]) for key in ("sample_ids", "case_ids", "shape_ids", "pose_ids", "camera_ids", "geometry_ids")},
    }
    combined = {}
    main_keys = ("images_rgb", "uv", "visible", "reason_code", "sample_ids", "case_ids", "shape_ids", "pose_ids", "camera_ids", "geometry_ids")
    for key in main_keys:
        combined[key] = np.concatenate((v1[key], new_arrays[key]), axis=0)
    for key in v1.files:
        if key not in main_keys:
            combined[key] = v1[key]
    cache_path = output / "training_cache_v2.npz"
    np.savez_compressed(cache_path, **combined)

    holdout_arrays = {
        "images_rgb": array(holdout["images_rgb"], np.uint8),
        "uv": array(holdout["uv"], np.float32),
        "visible": array(holdout["visible"], np.uint8),
        "reason_code": array(holdout["reason_code"], np.uint8),
        **{key: array(holdout[key]) for key in ("sample_ids", "case_ids", "shape_ids", "pose_ids", "camera_ids", "geometry_ids")},
        "point_ids": v1["point_ids"],
    }
    holdout_path = output / "truncation_holdout_v2.npz"
    np.savez_compressed(holdout_path, **holdout_arrays)

    contracts = output / "contracts"
    contracts.mkdir(parents=True, exist_ok=True)
    v2_splits = json.loads(json.dumps(v1_splits))
    split_checks = {}
    new_sample_case = dict(zip(new_arrays["sample_ids"].astype(str), new_arrays["case_ids"].astype(str)))
    all_new_ids = set(new_sample_case)
    holdout_ids = set(holdout_arrays["sample_ids"].astype(str).tolist())
    for split_id in SPLITS:
        old = v1_splits["splits"][split_id]
        new = v2_splits["splits"][split_id]
        additions = [sample_id for sample_id, case_id in new_sample_case.items() if case_id in set(old["train_case_ids"])]
        new["sample_ids"]["train"] = list(old["sample_ids"]["train"]) + sorted(additions)
        new["sample_counts"] = {bucket: len(new["sample_ids"][bucket]) for bucket in ("train", "val", "test")}
        new["v2_truncation_train_addition_count"] = len(additions)
        split_checks[split_id] = {
            "v1_val_ids_exact": new["sample_ids"]["val"] == old["sample_ids"]["val"],
            "v1_test_ids_exact": new["sample_ids"]["test"] == old["sample_ids"]["test"],
            "all_new_train_cases_are_original_train_cases": all(new_sample_case[sample_id] in set(old["train_case_ids"]) for sample_id in additions),
            "no_holdout_image_in_train": not bool(set(new["sample_ids"]["train"]) & holdout_ids),
            "all_unselected_new_samples_unused": all(sample_id in additions or sample_id not in new["sample_ids"]["train"] for sample_id in all_new_ids),
            "addition_count": len(additions),
        }
    write_json(contracts / "evaluation_splits_v1.json", v2_splits)

    cache_report = {
        "schema": "failure-driven-pilot-training-cache-v2",
        "passed": True,
        "medical_truth": False,
        "sample_count": int(combined["sample_ids"].size),
        "v1_sample_count": int(v1["sample_ids"].size),
        "truncation_train_pool_count": int(new_arrays["sample_ids"].size),
        "challenge_sample_count": int(v1["challenge_sample_ids"].size),
        "cache_path": str(cache_path),
        "cache_sha256": sha256(cache_path),
        "reason_codes": REASON_CODES,
        "model_input_arrays": ["images_rgb", "challenge_images_rgb"],
        "forbidden_inputs": ["Depth", "Mask", "labels", "overlay", "case/shape/pose/camera identifiers"],
    }
    write_json(cache_path.with_suffix(".json"), cache_report)
    write_json(holdout_path.with_suffix(".json"), {
        "schema": "failure-driven-truncation-holdout-v2",
        "passed": True,
        "sample_count": int(holdout_arrays["sample_ids"].size),
        "appearance_ordinal": HOLDOUT_APPEARANCE_ORDINAL,
        "cache_sha256": sha256(holdout_path),
        "selection_rule": "For each split, evaluate only case_ids frozen in that split's V1 test_case_ids.",
    })
    write_json(output / "dataset_manifest.json", {
        "schema": "failure-driven-pilot-dataset-v2",
        "medical_truth": False,
        "v1_dataset": str(v1_dataset),
        "v1_dataset_manifest_sha256": sha256(v1_dataset / "dataset_manifest.json"),
        "truncation_gate": str(gate),
        "v1_main_samples_reused": 360,
        "truncation_train_pool": manifest_train,
        "truncation_holdout": manifest_holdout,
        "training_change": "Only true-camera left/right mild/moderate truncation RGB samples were added to each split's original train cases.",
    })
    checks = {
        "v1_dataset_manifest_passed": v1_manifest["passed"],
        "truncation_gate_manifest_passed": gate_manifest["passed"],
        "gate_final_verification_passed": gate_verification["passed"],
        "gate_cells_68": len(gate_rows) == 68,
        "train_pool_272": len(manifest_train) == 272,
        "holdout_68": len(manifest_holdout) == 68,
        "v1_cache_prefix_exact": all(np.array_equal(combined[key][: len(v1[key])], v1[key]) for key in main_keys),
        "v1_challenge_arrays_exact": all(np.array_equal(combined[key], v1[key]) for key in v1.files if key.startswith("challenge_")),
        "all_split_leakage_checks_pass": all(all(value for key, value in item.items() if key != "addition_count") for item in split_checks.values()),
        "all_generated_rgb_unique": len({item["rgb_sha256"] for item in manifest_train + manifest_holdout}) == 340,
    }
    passed = all(checks.values())
    write_json(output / "qc_verification.json", {
        "schema": "failure-driven-pilot-data-qc-v2",
        "passed": passed,
        "checks": checks,
        "split_checks": split_checks,
        "truth_status": {"kind": "ENGINEERING_QA", "medical_truth": False, "medical_validated": False},
    })
    write_json(output / "visual_review.json", {
        "schema": "failure-driven-pilot-visual-review-placeholder-v2",
        "passed": passed,
        "scope": "Inherited gate visual review plus deterministic image-space appearance transform; a V2 montage is still required before final freeze.",
    })
    print(json.dumps({"PREPARE_V2": "PASS" if passed else "FAIL", "cache": str(cache_path), "split_additions": {key: value["addition_count"] for key, value in split_checks.items()}}, ensure_ascii=False))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
