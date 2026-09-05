from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
AI_ROOT = HERE.parents[3]
CROSS_ROOT = AI_ROOT / "outputs" / "内部工程证据" / "2026-08-31_17-27-40_CROSS_GATE_RECONCILIATION_V1"
CAMERA_ROOT = AI_ROOT / "outputs" / "内部工程证据" / "2026-08-31_18-38-27_CAMERA_VISIBILITY_DIVERSITY_V1"
SEED = 20260831
MAIN_QUOTAS = {
    "NORMAL_MAIN": 144,
    "C1_MILD_OBLIQUE": 108,
    "C2_EDGE_CROP": 54,
    "C3_EXTERNAL_OCCLUDER": 54,
}
CHALLENGE_CAMERA = "C4_SELF_OCCLUSION_STRESS"
CHALLENGE_VARIANTS_PER_COMPATIBLE_CASE = 4
GEOMETRY_FILES = ("labels.json", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png")


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


def manifest(root: Path) -> dict:
    target = root / "SHA256SUMS.txt"
    rows = [
        f"{sha256(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != target
    ]
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"entries": len(rows), "manifest_sha256": sha256(target)}


def parse_case(case_id: str) -> tuple[str, str]:
    parts = case_id.split("__", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid case id: {case_id}")
    return parts[0], parts[1]


def deterministic_appearance(sample_id: str, variant_ordinal: int) -> dict:
    if variant_ordinal == 0:
        return {
            "kind": "IDENTITY",
            "global_exposure": 1.0,
            "gamma": 1.0,
            "skin_rgb_gain": [1.0, 1.0, 1.0],
            "non_skin_rgb_gain": [1.0, 1.0, 1.0],
            "image_space_gradient_amplitude": 0.0,
            "image_space_gradient_angle_degrees": 0.0,
        }
    state = int.from_bytes(hashlib.sha256(f"{SEED}|{sample_id}".encode("utf-8")).digest()[:8], "big")

    def unit() -> float:
        nonlocal state
        state = (6364136223846793005 * state + 1442695040888963407) & ((1 << 64) - 1)
        return state / float(1 << 64)

    def between(lo: float, hi: float) -> float:
        return lo + (hi - lo) * unit()

    return {
        "kind": "DETERMINISTIC_RGB_ONLY_PHOTOMETRIC",
        "global_exposure": round(between(0.85, 1.15), 8),
        "gamma": round(between(0.90, 1.10), 8),
        "skin_rgb_gain": [round(between(0.92, 1.08), 8) for _ in range(3)],
        "non_skin_rgb_gain": [round(between(0.88, 1.12), 8) for _ in range(3)],
        "image_space_gradient_amplitude": round(between(-0.12, 0.12), 8),
        "image_space_gradient_angle_degrees": round(between(0.0, 360.0), 8),
    }


def base_source(case_id: str, camera_id: str) -> Path:
    if camera_id == "NORMAL_MAIN":
        return CROSS_ROOT / "restricted_rgbd" / "samples" / case_id
    return CAMERA_ROOT / "matrix" / "samples" / f"{case_id}__{camera_id}"


def build_rows(case_ids: list[str], camera_id: str, quota: int, prefix: str) -> list[dict]:
    rows = []
    for index in range(quota):
        case_id = case_ids[index % len(case_ids)]
        variant = index // len(case_ids)
        shape_id, pose_id = parse_case(case_id)
        sample_id = f"{prefix}_{index + 1:04d}__{case_id}__{camera_id}__A{variant:02d}"
        rows.append({
            "sample_id": sample_id,
            "case_id": case_id,
            "shape_id": shape_id,
            "pose_id": pose_id,
            "camera_id": camera_id,
            "base_geometry_id": f"{case_id}__{camera_id}",
            "variant_ordinal": variant,
            "appearance": deterministic_appearance(sample_id, variant),
        })
    return rows


def split_payload(rows: list[dict], case_ids: list[str]) -> dict:
    combo_test = {
        "C02_SHORT_NARROW_THIN__P3_ELBOW_22",
        "C03_LONG_NARROW__D06_THORAX_EXTENSION_P4",
        "C06_THIN_NARROW__P4_ARMS_SLIGHTLY_OPEN",
    }
    combo_val = {
        "C02_SHORT_NARROW_THIN__D01_SCAPULA_ABDUCTION_PAIR_P6",
        "C03_LONG_NARROW__P2_HEAD_POS35",
        "C06_THIN_NARROW__D06_THORAX_EXTENSION_P4",
    }
    shape_test = {case for case in case_ids if case.startswith("C06_THIN_NARROW__")}
    shape_val = {
        "C02_SHORT_NARROW_THIN__D03_HEAD_EXTENSION_P6",
        "C03_LONG_NARROW__P4_ARMS_SLIGHTLY_OPEN",
    }
    pose_test = {case for case in case_ids if case.endswith("D01_SCAPULA_ABDUCTION_PAIR_P6")}
    pose_val = {case for case in case_ids if case.endswith("P3_ELBOW_22")}
    definitions = {
        "COMBINATION_HOLDOUT": {
            "purpose": "Shape and Pose are individually seen in train, but held-out Shape×Pose combinations are not.",
            "test_cases": combo_test,
            "val_cases": combo_val,
        },
        "SHAPE_HOLDOUT": {
            "purpose": "The entire C06_THIN_NARROW shape is absent from train/val and appears only in test.",
            "test_cases": shape_test,
            "val_cases": shape_val,
        },
        "POSE_HOLDOUT": {
            "purpose": "The entire D01_SCAPULA_ABDUCTION_PAIR_P6 pose is absent from train/val and appears only in test.",
            "test_cases": pose_test,
            "val_cases": pose_val,
        },
    }
    all_cases = set(case_ids)
    result = {}
    for split_id, definition in definitions.items():
        test_cases = set(definition["test_cases"])
        val_cases = set(definition["val_cases"])
        train_cases = all_cases - test_cases - val_cases
        members = {"train": [], "val": [], "test": []}
        for row in rows:
            bucket = "test" if row["case_id"] in test_cases else "val" if row["case_id"] in val_cases else "train"
            members[bucket].append(row["sample_id"])
        result[split_id] = {
            "purpose": definition["purpose"],
            "grouping_unit": "shape_pose_case_id",
            "train_case_ids": sorted(train_cases),
            "val_case_ids": sorted(val_cases),
            "test_case_ids": sorted(test_cases),
            "sample_ids": members,
            "sample_counts": {key: len(value) for key, value in members.items()},
        }
    return {
        "schema": "engineering-pilot-evaluation-splits-v1",
        "medical_truth": False,
        "primary_split": "COMBINATION_HOLDOUT",
        "splits": result,
    }


def verify_split_invariants(splits: dict, rows: list[dict]) -> dict:
    by_sample = {row["sample_id"]: row for row in rows}
    checks = {}
    for split_id, item in splits["splits"].items():
        train = set(item["train_case_ids"])
        val = set(item["val_case_ids"])
        test = set(item["test_case_ids"])
        sample_sets = {key: set(value) for key, value in item["sample_ids"].items()}
        checks[f"{split_id}_case_disjoint"] = not (train & val or train & test or val & test)
        checks[f"{split_id}_sample_disjoint"] = not (
            sample_sets["train"] & sample_sets["val"]
            or sample_sets["train"] & sample_sets["test"]
            or sample_sets["val"] & sample_sets["test"]
        )
        checks[f"{split_id}_all_samples_once"] = set().union(*sample_sets.values()) == set(by_sample)
    combo = splits["splits"]["COMBINATION_HOLDOUT"]
    train_rows = [by_sample[sample] for sample in combo["sample_ids"]["train"]]
    train_shapes = {row["shape_id"] for row in train_rows}
    train_poses = {row["pose_id"] for row in train_rows}
    combo_test_rows = [by_sample[sample] for sample in combo["sample_ids"]["test"]]
    checks["combination_holdout_components_seen"] = all(
        row["shape_id"] in train_shapes and row["pose_id"] in train_poses for row in combo_test_rows
    )
    shape = splits["splits"]["SHAPE_HOLDOUT"]
    shape_train = {by_sample[sample]["shape_id"] for sample in shape["sample_ids"]["train"]}
    shape_test = {by_sample[sample]["shape_id"] for sample in shape["sample_ids"]["test"]}
    checks["shape_holdout_shape_unseen"] = shape_train.isdisjoint(shape_test) and len(shape_test) == 1
    pose = splits["splits"]["POSE_HOLDOUT"]
    pose_train = {by_sample[sample]["pose_id"] for sample in pose["sample_ids"]["train"]}
    pose_test = {by_sample[sample]["pose_id"] for sample in pose["sample_ids"]["test"]}
    checks["pose_holdout_pose_unseen"] = pose_train.isdisjoint(pose_test) and len(pose_test) == 1
    return {"passed": all(checks.values()), "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    camera_verification = read_json(CAMERA_ROOT / "verification.json")
    cross_verification = read_json(CROSS_ROOT / "restricted_rgbd_verification.json")
    compatibility = read_json(CAMERA_ROOT / "QUALIFIED_CAMERA_SHAPE_POSE_COMPATIBILITY_V1.json")
    cross_set = read_json(CROSS_ROOT / "CROSS_QUALIFIED_SHAPE_POSE_SEARCH_V1.json")
    case_ids = sorted(item["case_id"] for item in cross_set["combinations"])
    if len(case_ids) != 17:
        raise RuntimeError(f"Expected 17 frozen cases, got {len(case_ids)}")

    main_rows = []
    for camera_id, quota in MAIN_QUOTAS.items():
        main_rows.extend(build_rows(case_ids, camera_id, quota, "PILOT"))
    stress_ids = compatibility["self_occlusion_stress_qualified_sample_ids"]
    challenge_cases = sorted(sample_id.rsplit(f"__{CHALLENGE_CAMERA}", 1)[0] for sample_id in stress_ids)
    challenge_rows = build_rows(
        challenge_cases,
        CHALLENGE_CAMERA,
        len(challenge_cases) * CHALLENGE_VARIANTS_PER_COMPATIBLE_CASE,
        "CHALLENGE",
    )

    source_rows = []
    point_order = None
    source_checks = []
    unique_bases = sorted({row["base_geometry_id"] for row in main_rows + challenge_rows})
    for base_id in unique_bases:
        case_id, camera_id = base_id.rsplit("__", 1)
        source = base_source(case_id, camera_id)
        files = {}
        for name in ("rgb.png",) + GEOMETRY_FILES:
            path = source / name
            source_checks.append(path.is_file())
            if path.is_file():
                files[name] = {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
        labels = read_json(source / "labels.json")
        current_order = [point["point_id"] for point in labels["points"]]
        point_order = current_order if point_order is None else point_order
        source_checks.append(current_order == point_order and len(current_order) == 20)
        source_rows.append({
            "base_geometry_id": base_id,
            "case_id": case_id,
            "camera_id": camera_id,
            "source_directory": str(source),
            "files": files,
            "visibility_counts": dict(Counter(point["visibility_reason"] for point in labels["points"])),
        })

    splits = split_payload(main_rows, case_ids)
    split_verification = verify_split_invariants(splits, main_rows)
    quota_counts = Counter(row["camera_id"] for row in main_rows)
    checks = {
        "camera_gate_passed": camera_verification.get("passed") is True,
        "cross_rgbd_gate_passed": cross_verification.get("passed") is True,
        "compatibility_count_54": compatibility.get("qualified_sample_count") == 54,
        "seventeen_case_ids": len(case_ids) == 17,
        "main_count_360": len(main_rows) == 360,
        "main_quotas_exact": dict(quota_counts) == MAIN_QUOTAS,
        "normal_main_preserved": quota_counts["NORMAL_MAIN"] == 144,
        "c4_absent_from_main": all(row["camera_id"] != CHALLENGE_CAMERA for row in main_rows),
        "c4_challenge_only_12": len(challenge_rows) == 12 and all(row["camera_id"] == CHALLENGE_CAMERA for row in challenge_rows),
        "only_three_c4_cases": len(challenge_cases) == 3,
        "unique_sample_ids": len({row["sample_id"] for row in main_rows + challenge_rows}) == 372,
        "all_source_files_present_and_point_order_stable": all(source_checks),
        "split_contract_passed": split_verification["passed"],
    }

    write_json(output / "pilot_sampling_contract_v1.json", {
        "schema": "engineering-pilot-sampling-contract-v1",
        "medical_truth": False,
        "seed": SEED,
        "main_sample_count": 360,
        "main_camera_quotas": MAIN_QUOTAS,
        "challenge_sample_count": len(challenge_rows),
        "challenge_camera_id": CHALLENGE_CAMERA,
        "challenge_policy": "CHALLENGE_ONLY_NOT_IN_TRAIN_VAL_TEST",
        "qualified_shape_pose_case_ids": case_ids,
        "c4_compatible_case_ids": challenge_cases,
        "c4_incompatible_sample_ids": compatibility["self_occlusion_stress_incompatible_sample_ids"],
        "sampling_rule": "Round-robin over frozen case ids within each exact camera quota; no continuous Shape/Pose/Camera sampling.",
    })
    write_json(output / "pilot_visibility_loss_contract_v1.json", {
        "schema": "engineering-pilot-visibility-loss-contract-v1",
        "medical_truth": False,
        "point_order": point_order,
        "heatmap_loss_weights": {
            "VISIBLE": 1.0,
            "OUT_OF_FRAME": 0.0,
            "SELF_OCCLUDED": 0.0,
            "EXTERNAL_OCCLUDED": 0.0,
            "BACK_FACING": 0.0,
            "BEHIND_CAMERA": 0.0,
        },
        "retained_for_all_points": ["uv_pixel_opencv", "xyz_world_blender_m", "xyz_camera_opencv_m", "visibility_reason"],
        "first_baseline_scope": "Visible-point 2D heatmap only; no visibility head and no hidden-point inference loss.",
    })
    write_json(output / "pilot_appearance_contract_v1.json", {
        "schema": "engineering-pilot-appearance-contract-v1",
        "medical_truth": False,
        "seed": SEED,
        "changes_rgb_only": True,
        "geometry_files_must_be_byte_identical_to_frozen_parent": list(GEOMETRY_FILES),
        "allowed": {
            "global_exposure": [0.85, 1.15],
            "gamma": [0.90, 1.10],
            "skin_rgb_gain_each": [0.92, 1.08],
            "non_skin_rgb_gain_each": [0.88, 1.12],
            "image_space_gradient_amplitude": [-0.12, 0.12],
        },
        "prohibited": ["spatial crop/resize/rotate/flip", "Depth noise", "distortion", "depth holes", "geometry changes"],
        "truthful_limit": "This is deterministic image-space photometric variation, not physically rerendered light/material variation.",
        "rgb_reproducibility": "Freeze every generated rgb.png by SHA-256; do not rely on Eevee rerender equality.",
    })
    write_json(output / "pilot_dataset_schema_v1.json", {
        "schema": "engineering-pilot-dataset-schema-v1",
        "medical_truth": False,
        "dataset_layout": {
            "rgb": "rgb/<sample_id>.png",
            "challenge_rgb": "challenge_rgb/<sample_id>.png",
            "base_geometry": "base_geometry/<base_geometry_id>/{labels.json,scene_depth_z.npy,depth_valid_mask.png,skin_mask.png}",
            "sample_index": "dataset_manifest.json",
        },
        "coordinate_convention": "OpenCV +X right, +Y down, +Z forward; continuous uv origin top-left.",
        "depth": "First-visible scene camera-Z in float32 metres; background 0.",
        "skin_mask": "255 only where first-visible surface is SKEL skin.",
        "immutable_versioning": "Dataset version is the directory plus SHA256SUMS.txt; generated RGB hashes are part of the manifest.",
    })
    write_json(output / "evaluation_splits_v1.json", splits)
    write_json(output / "pilot_plan_v1.json", {
        "schema": "engineering-pilot-plan-v1",
        "medical_truth": False,
        "main_samples": main_rows,
        "challenge_samples": challenge_rows,
    })
    write_json(output / "source_artifacts_v1.json", {
        "schema": "engineering-pilot-source-artifacts-v1",
        "medical_truth": False,
        "camera_gate": {"path": str(CAMERA_ROOT), "verification_sha256": sha256(CAMERA_ROOT / "verification.json")},
        "cross_gate": {"path": str(CROSS_ROOT), "verification_sha256": sha256(CROSS_ROOT / "restricted_rgbd_verification.json")},
        "base_sources": source_rows,
    })
    write_json(output / "verification.json", {
        "schema": "engineering-pilot-freeze-verification-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "split_verification": split_verification,
        "truth_status": {"kind": "ENGINEERING_QA", "medical_truth": False, "medical_validated": False},
        "next_gate": "Build the immutable 360-sample main Pilot plus 12-sample C4 challenge, then run dataset QC before training.",
    })
    result = manifest(output)
    print(json.dumps({"PILOT_FREEZE": "PASS" if all(checks.values()) else "FAIL", **result}, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
