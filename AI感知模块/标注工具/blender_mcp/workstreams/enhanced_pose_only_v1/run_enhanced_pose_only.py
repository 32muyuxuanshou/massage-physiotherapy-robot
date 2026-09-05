#!/usr/bin/env python3
"""Orchestrate ENHANCED_POSE_ONLY_V1 inside the authorized B output root."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path


AI_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
TOOL_ROOT = AI_ROOT / "标注工具" / "blender_mcp"
WS = Path(__file__).resolve().parent
OUT = AI_ROOT / "outputs" / "交付文件" / "2026-08-31_13-36-44" / "B_pose_only"
SOURCE_30 = AI_ROOT / "outputs" / "交付文件" / "2026-08-28_20-21-54"
SOURCE_MANUAL = AI_ROOT / "outputs" / "交付文件" / "2026-08-29_16-21-55"
ATLAS = SOURCE_MANUAL / "source_atlas_v5.json"
CONFIG = WS / "pose_only_config_v1.json"
AUDIT = WS / "audit_existing_poses.py"
PROBE = WS / "probe_pose_case.py"
NATURAL = TOOL_ROOT / "workstreams" / "natural_prone_pose"
BASE_PROFILE = NATURAL / "natural_prone_pose_profile.json"
GENERATE = NATURAL / "generate_native_pose.py"
CONTRACT = NATURAL / "fixed_scene_contract.json"
PREPARE = TOOL_ROOT / "workstreams" / "prone_rgbd" / "prepare_prone_scene.py"
PREVIEW = NATURAL / "render_preview.py"
WORKBENCH = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_完整版" / "医生穴位标注工作台_v2.3.0_完整版"
BLENDER = WORKBENCH / "runtime" / "blender" / "blender.exe"
PYTHON = TOOL_ROOT / ".venv" / "Scripts" / "python.exe"
CANONICAL = AI_ROOT / "模型资源" / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发" / "templates" / "SKEL" / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
CORE_PARENT = AI_ROOT / "标注工具" / "blender_addons" / "modules"
KIN_SKEL = AI_ROOT / "模型资源" / "SKEL" / "loader" / "skel" / "kin_skel.py"
SELF_INTERSECTION = TOOL_ROOT / "workstreams" / "qa_infrastructure_v1" / "self_intersection_probe.py"
MEASUREMENT_CONTRACT_V2 = AI_ROOT / "outputs" / "交付文件" / "2026-08-31_13-36-44" / "F_qa" / "body_measurement_contract_v2.json"
LIGHT_SCRIPT = WS / "freeze_apply_light_contract.py"
RUN_ROOT = OUT / "fixed_light_run_v3"
POSE_INDEX = {
    "pelvis_tilt": 0, "pelvis_list": 1, "pelvis_rotation": 2, "hip_flexion_r": 3, "hip_adduction_r": 4,
    "hip_rotation_r": 5, "knee_angle_r": 6, "ankle_angle_r": 7, "subtalar_angle_r": 8, "mtp_angle_r": 9,
    "hip_flexion_l": 10, "hip_adduction_l": 11, "hip_rotation_l": 12, "knee_angle_l": 13,
    "ankle_angle_l": 14, "subtalar_angle_l": 15, "mtp_angle_l": 16, "lumbar_bending": 17,
    "lumbar_extension": 18, "lumbar_twist": 19, "thorax_bending": 20, "thorax_extension": 21,
    "thorax_twist": 22, "head_bending": 23, "head_extension": 24, "head_twist": 25,
    "scapula_abduction_r": 26, "scapula_elevation_r": 27, "scapula_upward_rot_r": 28,
    "shoulder_r_x": 29, "shoulder_r_y": 30, "shoulder_r_z": 31, "elbow_flexion_r": 32,
    "pro_sup_r": 33, "wrist_flexion_r": 34, "wrist_deviation_r": 35, "scapula_abduction_l": 36,
    "scapula_elevation_l": 37, "scapula_upward_rot_l": 38, "shoulder_l_x": 39,
    "shoulder_l_y": 40, "shoulder_l_z": 41, "elbow_flexion_l": 42, "pro_sup_l": 43,
    "wrist_flexion_l": 44, "wrist_deviation_l": 45,
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def matrix_error(first, second) -> float:
    return max(abs(float(left) - float(right)) for row_a, row_b in zip(first, second) for left, right in zip(row_a, row_b))


def run(command: list[str], sentinel: str | None = None, timeout: int = 900) -> str:
    result = subprocess.run(command, cwd=str(TOOL_ROOT), env=environment(), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    combined = result.stdout + "\n" + result.stderr
    if result.returncode != 0 or (sentinel and sentinel not in combined):
        raise RuntimeError(combined[-12000:])
    return combined


def environment():
    value = os.environ.copy()
    value.update({
        "BLENDER_USER_RESOURCES": str(WORKBENCH / "user_resources"),
        "ACUPOINT_MCP_PROJECT_ROOT": str(AI_ROOT),
        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
    })
    return value


def build_profile(definition: dict) -> dict:
    profile = read(BASE_PROFILE)
    profile["profile_id"] = definition["pose_id"]
    profile["medical_truth"] = False
    profile["betas"] = [0.0] * 10
    profile["source_kind"] = definition["kind"]
    profile["diagnostic_intent"] = definition["diagnostic_intent"]
    for name, degrees in definition["overrides_degrees"].items():
        profile["pose_degrees"][name] = float(degrees)
        profile["pose_vector_degrees"][POSE_INDEX[name]] = float(degrees)
    if len(profile["pose_vector_degrees"]) != 46:
        raise ValueError("profile must contain 46 pose values")
    return profile


def source_hashes() -> dict:
    paths = [CONFIG, AUDIT, PROBE, Path(__file__), WS / "run_pose_determinism.py", WS / "finalize_pose_only.py",
             WS / "record_visual_review.py", LIGHT_SCRIPT,
             BASE_PROFILE, GENERATE, CONTRACT, PREPARE, PREVIEW, CANONICAL, ATLAS,
             SELF_INTERSECTION, MEASUREMENT_CONTRACT_V2, KIN_SKEL]
    paths += sorted((CORE_PARENT / "training_export_core").glob("*.py"))
    return {str(path): sha256(path) for path in paths}


def audit_only() -> None:
    allowed_retry_files = {
        "pose_only_config_v1.json", "source_hashes_before.json", "existing_pose_audit.json",
        "profiles", "preparation_report.json", "README.md",
        "FAILED_DO_NOT_DELIVER_UNFROZEN_LIGHTS.json", "native", "snapshots", "prepare", "probes",
        "previews", "self_intersections", "batch_progress.json", "fixed_light_run",
        "FAILED_DO_NOT_DELIVER_EXACT_FLOAT_LIGHT_COMPARE.json",
    }
    existing = {path.name for path in OUT.iterdir()} if OUT.exists() else set()
    if existing - allowed_retry_files:
        raise FileExistsError(f"B output already contains non-retry files: {sorted(existing - allowed_retry_files)}")
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG, OUT / CONFIG.name)
    write(OUT / "source_hashes_before.json", source_hashes())
    run([str(PYTHON), str(AUDIT), "--output", str(OUT / "existing_pose_audit.json")])
    config = read(CONFIG)
    profiles = OUT / "profiles"
    profiles.mkdir(exist_ok=True)
    for definition in config["profiles"]:
        write(profiles / f"{definition['pose_id']}.json", build_profile(definition))
    payload = {
        "schema": "enhanced-pose-only-preparation-v1",
        "passed": read(OUT / "existing_pose_audit.json")["passed"],
        "profile_count": len(config["profiles"]),
        "existing_evidence_count": sum(item["kind"] == "existing_evidence" for item in config["profiles"]),
        "new_diagnostic_count": sum(item["kind"] == "new_diagnostic" for item in config["profiles"]),
        "heavy_blender_batch_started": False,
        "qualification_status": "BLOCKED_PENDING_F_SELF_INTERSECTION_AND_HEAVY_BATCH",
        "f_self_intersection_gate_available": SELF_INTERSECTION.is_file(),
        "measurement_contract_v2_available": MEASUREMENT_CONTRACT_V2.is_file(),
        "measurement_contract_v2_sha256": sha256(MEASUREMENT_CONTRACT_V2),
        "scope": "beta=0 only; no Shape x Pose; no training",
    }
    write(OUT / "preparation_report.json", payload)
    (OUT / "README.md").write_text(
        "# ENHANCED_POSE_ONLY_V1\n\n"
        "当前完成既有5种 Pose 的46维参数审计与新增7种诊断 Profile 冻结。"
        "重型 Blender 批次尚未启动；F 自相交门未接入，因此不得生成 qualified 结论。\n\n"
        "所有结果限定在 beta=0、固定 Camera/Bed/Light/工程参考 Atlas；当前20点不是医学穴位。\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False))


def blender_batch() -> None:
    if not read(OUT / "preparation_report.json")["passed"]:
        raise RuntimeError("static preparation gate has not passed")
    if read(OUT / "source_hashes_before.json") != source_hashes():
        raise RuntimeError("B-line source hashes changed after preparation")
    config = read(CONFIG)
    if RUN_ROOT.exists() and any(RUN_ROOT.iterdir()):
        raise FileExistsError(f"refusing to overwrite fixed-light run: {RUN_ROOT}")
    for subdir in ("native", "snapshots", "prepare", "probes", "previews", "self_intersections", "lights"):
        (RUN_ROOT / subdir).mkdir(parents=True, exist_ok=True)
    light_contract = RUN_ROOT / "fixed_light_contract_v1.json"
    invariant_baseline = None
    cases = []
    for index, definition in enumerate(config["profiles"]):
        pose_id = definition["pose_id"]
        profile = OUT / "profiles" / f"{pose_id}.json"
        native = RUN_ROOT / "native" / pose_id
        if not native.exists():
            run([str(PYTHON), str(GENERATE), "--profile", str(profile), "--output", str(native)])
        snapshot = RUN_ROOT / "snapshots" / f"{pose_id}.blend"
        prepare = RUN_ROOT / "prepare" / f"{pose_id}.json"
        run([str(BLENDER), "--background", str(CANONICAL), "--python", str(PREPARE), "--",
             "--snapshot", str(snapshot), "--result", str(prepare), "--native-pose-dir", str(native),
             "--pose-profile", str(profile), "--fixed-scene-contract", str(CONTRACT), "--width", "1280", "--height", "1024"],
            "ACU_PREPARE_PRONE_SCENE=PASS")
        light_result = RUN_ROOT / "lights" / f"{pose_id}.json"
        mode = "freeze" if index == 0 else "apply"
        run([str(BLENDER), "--background", str(snapshot), "--python", str(LIGHT_SCRIPT), "--",
             "--mode", mode, "--contract", str(light_contract), "--result", str(light_result)],
            "ACU_FIXED_LIGHT_CONTRACT=PASS")
        probe = RUN_ROOT / "probes" / f"{pose_id}.json"
        run([str(BLENDER), "--background", str(snapshot), "--python", str(PROBE), "--",
             "--atlas", str(ATLAS), "--profile", str(profile), "--native-parameters", str(native / "parameters.json"),
             "--core-parent", str(CORE_PARENT), "--output", str(probe), "--width", "1280", "--height", "1024"],
            "ACU_ENHANCED_POSE_PROBE=PASS")
        preview = RUN_ROOT / "previews" / f"{pose_id}.png"
        run([str(BLENDER), "--background", str(snapshot), "--python", str(PREVIEW), "--", str(preview)],
            "ACU_NATURAL_PRONE_PREVIEW=PASS")
        self_intersection = RUN_ROOT / "self_intersections" / f"{pose_id}.json"
        si_result = subprocess.run(
            [str(BLENDER), "--background", str(snapshot), "--python", str(SELF_INTERSECTION), "--",
             "--object", "SKEL-skin-female", "--output", str(self_intersection),
             "--anchor-atlas", str(ATLAS), "--anchor-rings", "2", "--max-pairs", "20000"],
            cwd=str(TOOL_ROOT), env=environment(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=900,
        )
        if si_result.returncode not in (0, 2) or not self_intersection.is_file():
            raise RuntimeError((si_result.stdout + "\n" + si_result.stderr)[-12000:])
        si = read(self_intersection)
        result = read(probe)
        invariants = {
            "camera_name": result["camera"]["name"], "camera_type": result["camera"]["type"],
            "camera_matrix_world": result["camera"]["matrix_world"],
            "bed_name": result["bed"]["name"], "bed_type": result["bed"]["type"],
            "bed_matrix_world": result["bed"]["matrix_world"], "bed_top_z_m": result["bed"]["top_z_m"],
            "body_name": "SKEL-skin-female", "body_type": "MESH", "body_matrix_world": result["model"]["matrix_world"],
        }
        if invariant_baseline is None:
            invariant_baseline = invariants
            write(RUN_ROOT / "fixed_scene_invariant_baseline.json", invariant_baseline)
        camera_matrix_error = matrix_error(invariant_baseline["camera_matrix_world"], invariants["camera_matrix_world"])
        bed_matrix_error = matrix_error(invariant_baseline["bed_matrix_world"], invariants["bed_matrix_world"])
        body_matrix_error = matrix_error(invariant_baseline["body_matrix_world"], invariants["body_matrix_world"])
        checks = {
            "pose_chain": result["pose_control_chain_verified"],
            "beta_zero": result["betas"] == [0.0] * 10,
            "topology": result["model"]["topology_signature_sha256"] == "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733",
            "point_count": len(result["points"]) == 20,
            "bed_clearance": result["bed"]["minimum_body_clearance_m"] >= 0.0,
            "all_visible": result["visibility_count"] == 20,
            "anchor_2ring_overlap_zero": si["anchor_scope"]["overlap_pair_count"] == 0 and si["passed"],
            "fixed_light_contract": read(light_result)["passed"] and read(light_result)["max_matrix_abs_error"] <= 1e-6 and read(light_result)["contract_sha256"] == sha256(light_contract),
            "fixed_camera_object_and_matrix": invariants["camera_name"] == invariant_baseline["camera_name"] and invariants["camera_type"] == invariant_baseline["camera_type"] and camera_matrix_error <= 1e-6,
            "fixed_bed_object_matrix_and_top": invariants["bed_name"] == invariant_baseline["bed_name"] and invariants["bed_type"] == invariant_baseline["bed_type"] and bed_matrix_error <= 1e-6 and abs(float(invariants["bed_top_z_m"]) - float(invariant_baseline["bed_top_z_m"])) <= 1e-9,
            "fixed_body_object_matrix": invariants["body_name"] == invariant_baseline["body_name"] and invariants["body_type"] == invariant_baseline["body_type"] and body_matrix_error <= 1e-6,
        }
        cases.append({"pose_id": pose_id, "kind": definition["kind"], "checks": checks, "passed_automatic_gates": all(checks.values()),
                      "bed_clearance_m": result["bed"]["minimum_body_clearance_m"], "visibility_count": result["visibility_count"],
                      "anchor_2ring_overlap_pair_count": si["anchor_scope"]["overlap_pair_count"],
                      "global_nonadjacent_overlap_pair_count": si["nonadjacent_intersection_pair_count"],
                      "global_self_intersection_clear": si["global_self_intersection_clear"],
                      "self_intersection_status": si["status"],
                      "scene_invariant_errors": {"camera_matrix_max_abs": camera_matrix_error, "bed_matrix_max_abs": bed_matrix_error, "body_matrix_max_abs": body_matrix_error,
                                                   "bed_top_abs_m": abs(float(invariants["bed_top_z_m"]) - float(invariant_baseline["bed_top_z_m"]))}})
        write(RUN_ROOT / "batch_progress.json", cases)
        print(f"POSE {index + 1}/{len(config['profiles'])} {pose_id}: {'PASS' if all(checks.values()) else 'FAIL'}", flush=True)
    write(OUT / "source_hashes_after.json", source_hashes())
    batch_complete = len(cases) == len(config["profiles"])
    eligible_count = sum(case["passed_automatic_gates"] for case in cases)
    all_profiles_passed = batch_complete and eligible_count == len(cases)
    qualification_batch_passed = batch_complete and eligible_count >= 8
    write(OUT / "pose_only_report.json", {
        "schema": "enhanced-pose-only-report-v1", "medical_truth": False, "medical_validated": False,
        "beta_scope": [0.0] * 10, "case_count": len(cases), "cases": cases,
        "batch_complete": batch_complete,
        "eligible_profile_count": eligible_count,
        "all_profiles_passed": all_profiles_passed,
        "qualification_batch_passed": qualification_batch_passed,
        "qualification_status": "CANDIDATE_SET_PENDING_RESTORE_DETERMINISM_AND_FINAL_REVIEW" if qualification_batch_passed else "INSUFFICIENT_ELIGIBLE_PROFILES",
        "qualified_profile_set_name_reserved": "QUALIFIED_POSE_PROFILES_BASE_SHAPE_V1",
        "self_intersection_gate": {
            "anchor_rings": 2,
            "required_anchor_overlap_pair_count": 0,
            "global_zero_required": False,
            "known_baseline_global_overlap_count": 293,
            "notice": "A zero anchor-neighborhood count is the hard B-line gate; global counts are diagnostic and do not support a complete-body self-intersection-free claim.",
        },
        "fixed_light_contract": {"path": str(light_contract), "sha256": sha256(light_contract), "verified_all_profiles": all(case["checks"]["fixed_light_contract"] for case in cases)},
        "source_inputs_unchanged": read(OUT / "source_hashes_before.json") == read(OUT / "source_hashes_after.json"),
        "not_run": ["Shape x Pose", "training", "medical validation"],
    })
    print(json.dumps({"batch_complete": batch_complete, "eligible_profiles": eligible_count, "all_profiles_passed": all_profiles_passed, "qualified": False}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--run-blender-batch", action="store_true")
    args = parser.parse_args()
    if args.audit_only == args.run_blender_batch:
        raise SystemExit("choose exactly one mode")
    audit_only() if args.audit_only else blender_batch()
