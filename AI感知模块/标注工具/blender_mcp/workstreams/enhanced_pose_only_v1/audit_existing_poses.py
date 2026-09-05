#!/usr/bin/env python3
"""Audit the five already-delivered pose profiles without calling Blender."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


AI_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
SOURCE = AI_ROOT / "outputs" / "交付文件" / "2026-08-28_20-21-54"
CONFIG = Path(__file__).with_name("pose_only_config_v1.json")
KIN_SKEL = AI_ROOT / "模型资源" / "SKEL" / "loader" / "skel" / "kin_skel.py"
POSE_NAMES = (
    "pelvis_tilt", "pelvis_list", "pelvis_rotation", "hip_flexion_r", "hip_adduction_r", "hip_rotation_r",
    "knee_angle_r", "ankle_angle_r", "subtalar_angle_r", "mtp_angle_r", "hip_flexion_l", "hip_adduction_l",
    "hip_rotation_l", "knee_angle_l", "ankle_angle_l", "subtalar_angle_l", "mtp_angle_l", "lumbar_bending",
    "lumbar_extension", "lumbar_twist", "thorax_bending", "thorax_extension", "thorax_twist", "head_bending",
    "head_extension", "head_twist", "scapula_abduction_r", "scapula_elevation_r", "scapula_upward_rot_r",
    "shoulder_r_x", "shoulder_r_y", "shoulder_r_z", "elbow_flexion_r", "pro_sup_r", "wrist_flexion_r",
    "wrist_deviation_r", "scapula_abduction_l", "scapula_elevation_l", "scapula_upward_rot_l", "shoulder_l_x",
    "shoulder_l_y", "shoulder_l_z", "elbow_flexion_l", "pro_sup_l", "wrist_flexion_l", "wrist_deviation_l",
)
EXPECTED_CASES = {
    "P0_BASE": ("S0_P0.json", "sample_000001"),
    "P1_HEAD_NEG20": ("S0_P1.json", "sample_000003"),
    "P2_HEAD_POS35": ("S0_P2.json", "sample_000005"),
    "P3_ELBOW_22": ("S0_P3.json", "sample_000007"),
    "P4_ARMS_SLIGHTLY_OPEN": ("S0_P4.json", "sample_000009"),
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(root: Path) -> dict:
    sums = root / "SHA256SUMS.txt"
    missing, mismatch, count = [], [], 0
    for line in sums.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = root / Path(relative)
        count += 1
        if not path.is_file():
            missing.append(relative)
        elif sha256(path).lower() != expected.lower():
            mismatch.append(relative)
    return {
        "sha256sums_sha256": sha256(sums),
        "entry_count": count,
        "missing": missing,
        "mismatch": mismatch,
        "passed": not missing and not mismatch,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = read(CONFIG)
    definitions = {item["pose_id"]: item for item in config["profiles"] if item["kind"] == "existing_evidence"}
    rows = []
    for pose_id, (profile_name, sample_id) in EXPECTED_CASES.items():
        profile_path = SOURCE / "profiles" / profile_name
        labels_path = SOURCE / "samples" / sample_id / "labels.json"
        profile, labels = read(profile_path), read(labels_path)
        vector = [float(value) for value in profile["pose_vector_degrees"]]
        label_map = labels["scene"]["native_pose_parameters_degrees"]
        # Delivered labels intentionally store the sparse nonzero dictionary;
        # absent names therefore mean an exact zero, not missing evidence.
        label_vector = [float(label_map.get(name, 0.0)) for name in POSE_NAMES]
        expected_vector = read(SOURCE / "profiles" / profile_name)["pose_vector_degrees"]
        shape_variants = []
        pose_unchanged_across_shapes = True
        for shape_prefix in ("S0", "S1", "S2"):
            candidate_path = SOURCE / "profiles" / f"{shape_prefix}_{profile_name.split('_', 1)[1]}"
            candidate = read(candidate_path)
            candidate_vector = [float(value) for value in candidate["pose_vector_degrees"]]
            pose_unchanged_across_shapes &= candidate_vector == vector
            shape_variants.append({"path": str(candidate_path), "sha256": sha256(candidate_path), "betas": candidate["betas"]})
        checks = {
            "profile_has_46_values": len(vector) == 46,
            "s0_betas_are_zero": [float(value) for value in profile["betas"]] == [0.0] * 10,
            "labels_match_profile_46d": len(label_vector) == 46 and max(abs(a - b) for a, b in zip(vector, label_vector)) <= 1e-9,
            "pose_vector_identical_across_three_shapes": pose_unchanged_across_shapes,
            "config_override_matches_profile": all(
                abs(vector[POSE_NAMES.index(name)] - float(value)) <= 1e-9
                for name, value in definitions[pose_id]["overrides_degrees"].items()
            ),
            "existing_sample_qc_passed": read(SOURCE / "qc_reports" / f"{sample_id}_strict.json")["passed"],
        }
        rows.append({
            "pose_id": pose_id,
            "status": "EXISTING_EVIDENCE_NOT_FIRST_EXPERIMENT",
            "profile_path": str(profile_path),
            "profile_sha256": sha256(profile_path),
            "labels_path": str(labels_path),
            "labels_sha256": sha256(labels_path),
            "pose_vector_degrees_46": vector,
            "nonzero_parameters": {POSE_NAMES[index]: value for index, value in enumerate(vector) if abs(value) > 1e-12},
            "shape_variants": shape_variants,
            "checks": checks,
            "passed": all(checks.values()),
        })
    manifest = verify_manifest(SOURCE)
    payload = {
        "schema": "enhanced-pose-existing-evidence-audit-v1",
        "medical_truth": False,
        "source": str(SOURCE),
        "source_manifest": manifest,
        "pose_parameter_names_46": list(POSE_NAMES),
        "pose_parameter_definition_source": {"path": str(KIN_SKEL), "sha256": sha256(KIN_SKEL)},
        "existing_pose_count": len(rows),
        "existing_poses": rows,
        "passed": manifest["passed"] and len(rows) == 5 and all(row["passed"] for row in rows),
        "conclusion": "The five poses are frozen existing evidence and must not be described as first-time experiments.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": payload["passed"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
