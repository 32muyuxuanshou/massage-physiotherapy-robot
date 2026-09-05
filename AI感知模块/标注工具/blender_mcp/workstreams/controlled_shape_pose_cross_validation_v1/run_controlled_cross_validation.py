#!/usr/bin/env python3
"""Controlled 7x9 SKEL Shape x Pose cross-validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


AI_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
TOOL_ROOT = AI_ROOT / "标注工具" / "blender_mcp"
WS = Path(__file__).resolve().parent
SHARED_WS = TOOL_ROOT / "workstreams" / "enhanced_shape_only_v1"
A_WS = TOOL_ROOT / "workstreams" / "candidate_shape_combination_v1"
QA_WS = TOOL_ROOT / "workstreams" / "qa_infrastructure_v1"
sys.path.insert(0, str(SHARED_WS))
import run_enhanced_shape_only as shared  # noqa: E402


PARENT = AI_ROOT / "outputs" / "交付文件" / "2026-08-31_13-36-44"
A_ROOT = PARENT / "A_shape_combination"
B_ROOT = PARENT / "B_pose_only"
F_ROOT = PARENT / "F_qa"
SHAPE_SET = A_ROOT / "QUALIFIED_SHAPE_PROFILES_FIXED_PRONE_V1.json"
POSE_SET = B_ROOT / "QUALIFIED_POSE_PROFILES_BASE_SHAPE_V1.json"
ATLAS = A_ROOT / "source_atlas_v5.json"
MEASUREMENT_CONTRACT = F_ROOT / "body_measurement_contract_v2.json"
LIGHT_CONTRACT = A_ROOT / "fixed_prone_light_contract_v1.json"
LIGHT_SCRIPT = A_WS / "freeze_scene_lights.py"
SHAPE_PROBE = A_WS / "probe_shape_combination_case.py"
GEOMETRY_PROBE = WS / "geometry_scene_probe.py"
EXPECTED_TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"
MIN_CLEARANCE_M = 0.003
MATRIX_TOLERANCE = 1e-6

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

SMOKE_PAIRS = (
    ("S0_BASE", "P0_BASE"),
    ("C05_THICK_UPPER_WIDE", "D06_THORAX_EXTENSION_P4"),
    ("C07_SHOULDER_UPPER_WIDE", "D01_SCAPULA_ABDUCTION_PAIR_P6"),
    ("C08_LOWER_PELVIS_WIDE", "D05_LUMBAR_BENDING_P4"),
    ("C03_LONG_NARROW", "P4_ARMS_SLIGHTLY_OPEN"),
    ("C02_SHORT_NARROW_THIN", "D07_THORAX_TWIST_P4"),
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path) -> dict:
    manifest = root / "SHA256SUMS.txt"
    missing, mismatches = [], []
    rows = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        rows.append(relative)
        target = root / relative
        if not target.is_file():
            missing.append(relative)
        elif sha256(target) != expected:
            mismatches.append(relative)
    return {
        "root": str(root), "entries": len(rows), "manifest_sha256": sha256(manifest),
        "missing": missing, "mismatches": mismatches,
        "passed": not missing and not mismatches,
    }


def case_id(shape_id: str, pose_id: str) -> str:
    return f"{shape_id}__{pose_id}"


def case_kind(shape_id: str, pose_id: str) -> str:
    if shape_id == "S0_BASE" and pose_id == "P0_BASE":
        return "baseline"
    if pose_id == "P0_BASE":
        return "shape_only_control"
    if shape_id == "S0_BASE":
        return "pose_only_control"
    return "novel_interaction"


def build_profile(shape: dict, pose_id: str) -> dict:
    pose = read_json(B_ROOT / "profiles" / f"{pose_id}.json")
    profile = json.loads(json.dumps(pose))
    profile.update({
        "schema": "controlled-skel-shape-pose-profile-v1",
        "profile_id": case_id(shape["profile_id"], pose_id),
        "shape_profile_id": shape["profile_id"],
        "pose_profile_id": pose_id,
        "betas": [float(value) for value in shape["betas"]],
        "medical_truth": False,
        "medical_validated": False,
        "cross_validation_scope": "fixed-prone engineering scene only",
    })
    return profile


def protected_sources() -> dict:
    files = {
        "canonical_skel": shared.CANONICAL,
        "shape_set": SHAPE_SET,
        "pose_set": POSE_SET,
        "engineering_atlas": ATLAS,
        "measurement_contract_v2": MEASUREMENT_CONTRACT,
        "fixed_scene_contract": shared.CONTRACT_SCENE,
        "fixed_light_contract": LIGHT_CONTRACT,
        "native_generator": shared.GENERATE,
        "prone_scene_builder": shared.PREPARE,
        "training_exporter": shared.EXPORT,
        "shape_probe": SHAPE_PROBE,
        "geometry_scene_probe": GEOMETRY_PROBE,
        "training_surface_binding": shared.CORE_PARENT / "training_export_core" / "surface_binding.py",
        "training_camera_geometry": shared.CORE_PARENT / "training_export_core" / "camera_geometry.py",
        "training_visibility": shared.CORE_PARENT / "training_export_core" / "visibility.py",
        "training_depth_raycast": shared.CORE_PARENT / "training_export_core" / "depth_raycast.py",
    }
    for pose_id in read_json(POSE_SET)["profiles"]:
        files[f"pose_profile::{pose_id}"] = B_ROOT / "profiles" / f"{pose_id}.json"
    return {name: {"path": str(path), "sha256": sha256(path)} for name, path in files.items()}


def prepare(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "shape_pose_cross_config_v1.json"
    if config_path.is_file():
        before = read_json(root / "source_hashes_before.json")
        if before != protected_sources():
            raise RuntimeError("protected source hashes changed since X0")
        print("X0_ALREADY_PREPARED=PASS", flush=True)
        return

    if any(root.iterdir()):
        raise RuntimeError(f"X0 output must be empty: {root}")
    source_manifests = {
        "A_shape_combination": verify_manifest(A_ROOT),
        "B_pose_only": verify_manifest(B_ROOT),
        "F_qa": verify_manifest(F_ROOT),
    }
    if not all(item["passed"] for item in source_manifests.values()):
        raise RuntimeError("source delivery manifest verification failed")
    shapes = read_json(SHAPE_SET)["profiles"]
    poses = read_json(POSE_SET)["profiles"]
    if len(shapes) != 7 or len(poses) != 9:
        raise RuntimeError("expected frozen 7 Shape x 9 Pose inputs")

    fixture = shared.make_fixture(read_json(ATLAS))
    write_json(root / "engineering_fixture_manual20.json", fixture)
    shutil.copy2(MEASUREMENT_CONTRACT, root / "body_measurement_contract_v2.json")
    shutil.copy2(LIGHT_CONTRACT, root / "fixed_prone_light_contract_v1.json")
    profiles = []
    cells = []
    for shape in shapes:
        for pose_id in poses:
            profile = build_profile(shape, pose_id)
            path = root / "profiles" / f"{profile['profile_id']}.json"
            write_json(path, profile)
            profiles.append({"case_id": profile["profile_id"], "path": str(path), "sha256": sha256(path)})
            cells.append({
                "case_id": profile["profile_id"],
                "shape_id": shape["profile_id"], "pose_id": pose_id,
                "kind": case_kind(shape["profile_id"], pose_id),
                "betas": profile["betas"], "pose_vector_degrees_46": profile["pose_vector_degrees"],
            })
    source_hashes = protected_sources()
    write_json(root / "source_hashes_before.json", source_hashes)
    write_json(root / "cross_input_manifest.json", {
        "schema": "controlled-shape-pose-cross-input-manifest-v1",
        "medical_truth": False, "medical_validated": False,
        "source_manifests": source_manifests, "protected_sources": source_hashes,
        "profiles": profiles,
    })
    write_json(config_path, {
        "schema": "controlled-shape-pose-cross-config-v1",
        "medical_truth": False, "medical_validated": False,
        "matrix_absolute_tolerance": MATRIX_TOLERANCE,
        "minimum_fixed_bed_clearance_m": MIN_CLEARANCE_M,
        "shape_count": len(shapes), "pose_count": len(poses), "matrix_cell_count": len(cells),
        "control_cell_count": sum(item["kind"] != "novel_interaction" for item in cells),
        "novel_interaction_count": sum(item["kind"] == "novel_interaction" for item in cells),
        "shape_order": [item["profile_id"] for item in shapes],
        "pose_order": list(poses), "cells": cells,
        "smoke_pairs": [{"shape_id": shape, "pose_id": pose, "case_id": case_id(shape, pose)} for shape, pose in SMOKE_PAIRS],
        "fixed_controls": ["Camera", "Bed", "Light", "Material", "rigid prone transform", "engineering Atlas", "RGB-D contract"],
        "status_contract": [
            "QUALIFIED", "REJECT_BED_CLEARANCE", "REJECT_TARGET_LOCAL_INTERSECTION",
            "CAUTION_THREE_RING_INTERSECTION", "CAUTION_NEW_GLOBAL_OVERLAP", "ERROR_GEOMETRY",
        ],
    })
    print(json.dumps({"X0": "PASS", "root": str(root), "cells": len(cells)}, ensure_ascii=False), flush=True)


def matrix_error(left, right) -> float:
    return float(np.max(np.abs(np.asarray(left, dtype=float) - np.asarray(right, dtype=float))))


def scene_contract_comparison(base: dict, current: dict) -> dict:
    exact_keys = ("frame", "unit_system", "unit_scale_length", "render_engine", "resolution", "pixel_aspect", "world_color")
    exact = {key: base[key] == current[key] for key in exact_keys}
    matrix_errors = {
        "camera": matrix_error(base["camera"]["matrix_world"], current["camera"]["matrix_world"]),
        "bed": matrix_error(base["bed"]["matrix_world"], current["bed"]["matrix_world"]),
        "target": matrix_error(base["target"]["matrix_world"], current["target"]["matrix_world"]),
    }
    object_exact = {
        "camera_name": base["camera"]["name"] == current["camera"]["name"],
        "bed_name_material": base["bed"]["name"] == current["bed"]["name"] and base["bed"]["materials"] == current["bed"]["materials"],
        "target_name_material": base["target"]["name"] == current["target"]["name"] and base["target"]["materials"] == current["target"]["materials"],
    }
    base_lights = {item["name"]: item for item in base["lights"]}
    current_lights = {item["name"]: item for item in current["lights"]}
    light_details = {}
    if set(base_lights) == set(current_lights):
        for name in sorted(base_lights):
            left, right = base_lights[name], current_lights[name]
            error = matrix_error(left["matrix_world"], right["matrix_world"])
            details_equal = all(left[key] == right[key] for key in ("name", "type", "energy", "color", "size"))
            light_details[name] = {"matrix_max_abs_error": error, "data_equal": details_equal, "passed": details_equal and error <= MATRIX_TOLERANCE}
    else:
        light_details["__set__"] = {"passed": False, "base": sorted(base_lights), "current": sorted(current_lights)}
    checks = {
        **exact, **object_exact,
        "camera_matrix": matrix_errors["camera"] <= MATRIX_TOLERANCE,
        "bed_matrix": matrix_errors["bed"] <= MATRIX_TOLERANCE,
        "target_matrix": matrix_errors["target"] <= MATRIX_TOLERANCE,
        "lights": bool(light_details) and all(item["passed"] for item in light_details.values()),
    }
    return {"passed": all(checks.values()), "checks": checks, "matrix_max_abs_error": matrix_errors, "lights": light_details}


def control_chain(profile: dict, native: dict, probe: dict) -> dict:
    requested_betas = [float(value) for value in profile["betas"]]
    native_betas = [float(value) for value in native["betas"]]
    requested_pose = [float(value) for value in profile["pose_vector_degrees"]]
    native_pose = [math.degrees(float(value)) for value in native["pose"]]
    scene_map = probe["pose_degrees"]
    scene_pose = [float(scene_map.get(name, 0.0)) for name in POSE_NAMES]
    beta_error = max(abs(a - b) for a, b in zip(requested_betas, native_betas))
    pose_error = max(abs(a - b) for vectors in ((requested_pose, native_pose), (requested_pose, scene_pose)) for a, b in zip(*vectors))
    checks = {
        "ten_betas": len(requested_betas) == len(native_betas) == 10,
        "forty_six_pose_values": len(requested_pose) == len(native_pose) == len(scene_pose) == 46,
        "beta_profile_native_equal": beta_error <= 1e-9,
        "beta_profile_scene_equal": bool(probe["beta_control_chain_verified"]) and probe["requested_betas"] == requested_betas,
        "pose_profile_native_scene_equal": pose_error <= 1e-6,
    }
    return {"passed": all(checks.values()), "checks": checks, "max_beta_error": beta_error, "max_pose_error_deg": pose_error}


def bindings_and_points(probe: dict, fixture: dict) -> dict:
    expected = {item["point_id"]: item for item in fixture["anchors"]}
    actual = {item["point_id"]: item for item in probe["points"]}
    bindings_equal = set(expected) == set(actual) and all(
        all(actual[key][field] == expected[key][field] for field in ("face_index", "vertex_indices", "barycentric"))
        for key in expected
    )
    allowed_reasons = {"VISIBLE", "OUT_OF_FRAME", "BEHIND_CAMERA", "BACK_FACING", "SELF_OCCLUDED", "EXTERNAL_OCCLUDED"}
    visibility_consistent = all(
        item["visibility_reason"] in allowed_reasons and bool(item["visible"]) == (item["visibility_reason"] == "VISIBLE")
        for item in actual.values()
    )
    triangles_valid = all(
        float(item["triangle_area_m2"]) > 1e-12
        and all(math.isfinite(float(value)) and float(value) > 0 for value in item["triangle_edge_lengths_m"])
        and all(math.isfinite(float(value)) for value in item["normal_world"])
        for item in actual.values()
    )
    checks = {
        "point_count_20": len(actual) == len(expected) == 20,
        "bindings_frozen": bindings_equal,
        "visibility_contract_consistent": visibility_consistent,
        "triangles_and_normals_finite": triangles_valid,
    }
    return {"passed": all(checks.values()), "checks": checks}


def run_case(root: Path, phase: str, cell: dict, output_id: str, temp_parent: Path, *, export_rgbd: bool = False, temporary_sample: bool = False) -> dict:
    phase_root = root / phase
    probe_path = phase_root / "probes" / f"{output_id}.json"
    geometry_path = phase_root / "geometry" / f"{output_id}.json"
    meta_path = phase_root / "case_meta" / f"{output_id}.json"
    preview_path = phase_root / "previews" / f"{output_id}.png"
    overlay_path = phase_root / "overlays" / f"{output_id}.png"
    sample_path = (temp_parent / output_id / "sample") if temporary_sample else (phase_root / "samples" / output_id)
    for path in (probe_path, geometry_path, meta_path, preview_path, overlay_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    if meta_path.is_file() and probe_path.is_file() and geometry_path.is_file() and preview_path.is_file() and (not export_rgbd or (sample_path / "labels.json").is_file()):
        return read_json(meta_path)

    profile_path = root / "profiles" / f"{cell['case_id']}.json"
    profile = read_json(profile_path)
    temp_case = temp_parent / output_id
    native = temp_case / "native"
    snapshot = temp_case / f"{output_id}.blend"
    native.parent.mkdir(parents=True, exist_ok=True)
    shared.run([sys.executable, str(shared.GENERATE), "--profile", str(profile_path), "--output", str(native)])
    shared.bj(shared.CANONICAL, shared.PREPARE, [
        "--snapshot", snapshot, "--result", temp_case / "prepare.json",
        "--native-pose-dir", native, "--pose-profile", profile_path,
        "--fixed-scene-contract", shared.CONTRACT_SCENE, "--width", 1280, "--height", 1024,
    ], "ACU_PREPARE_PRONE_SCENE=PASS")
    shared.bj(snapshot, LIGHT_SCRIPT, ["--apply", LIGHT_CONTRACT, "--save", snapshot], "ACU_FIXED_SCENE_LIGHTS=PASS")
    shared.bj(snapshot, SHAPE_PROBE, [
        "--atlas", ATLAS, "--contract", MEASUREMENT_CONTRACT,
        "--profile", profile_path, "--native-parameters", native / "parameters.json",
        "--core-parent", shared.CORE_PARENT, "--output", probe_path, "--width", 1280, "--height", 1024,
    ], "ACU_SHAPE_COMBINATION_PROBE=PASS")
    shared.bj(snapshot, GEOMETRY_PROBE, [
        "--atlas", ATLAS, "--output", geometry_path, "--qa-root", QA_WS, "--epsilon", "1e-7",
    ], "ACU_SHAPE_POSE_GEOMETRY_SCENE_PROBE=PASS")
    shared.bj(snapshot, shared.RENDER, [preview_path], "ACU_NATURAL_PRONE_PREVIEW=PASS")
    probe = read_json(probe_path)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    shared.overlay_from_probe(preview_path, probe, overlay_path)

    native_parameters = read_json(native / "parameters.json")
    meta = {
        "schema": "controlled-shape-pose-case-meta-v1",
        "medical_truth": False, "medical_validated": False,
        "output_id": output_id, "case_id": cell["case_id"], "shape_id": cell["shape_id"], "pose_id": cell["pose_id"], "kind": cell["kind"],
        "profile_sha256": sha256(profile_path),
        "native_hashes": {name: sha256(native / name) for name in ("parameters.json", "skin_female.obj", "skeleton_female.obj", "joints_female.json")},
        "control_chain": control_chain(profile, native_parameters, probe),
        "probe": str(probe_path.relative_to(root)), "geometry": str(geometry_path.relative_to(root)),
        "preview": str(preview_path.relative_to(root)), "overlay": str(overlay_path.relative_to(root)),
    }
    if export_rgbd:
        export_result = phase_root / "export" / f"{output_id}.json"
        shared.bj(snapshot, shared.EXPORT, [
            "--fixture", root / "engineering_fixture_manual20.json", "--output", sample_path,
            "--result", export_result, "--width", 1280, "--height", 1024,
        ], "ACU_EXPORT_PRONE_SAMPLE=PASS")
        shared.overlay_from_probe(sample_path / "rgb.png", probe, sample_path / "overlay.png")
        qc = shared.strict_sample_qc(sample_path, read_json(root / "engineering_fixture_manual20.json"), [float(value) for value in profile["betas"]])
        labels = read_json(sample_path / "labels.json")
        pose_recorded = labels["scene"]["native_pose_parameters_degrees"] == profile["pose_degrees"]
        qc["checks"]["pose_recorded"] = pose_recorded
        qc["passed"] = bool(qc["passed"] and pose_recorded)
        qc_path = phase_root / "qc" / f"{output_id}.json"
        write_json(qc_path, qc)
        meta.update({"sample": str(sample_path), "qc": str(qc_path.relative_to(root)), "qc_passed": qc["passed"]})
    write_json(meta_path, meta)
    return meta


def load_case(root: Path, phase: str, output_id: str) -> tuple[dict, dict, dict]:
    return (
        read_json(root / phase / "case_meta" / f"{output_id}.json"),
        read_json(root / phase / "probes" / f"{output_id}.json"),
        read_json(root / phase / "geometry" / f"{output_id}.json"),
    )


def system_checks(root: Path, phase: str, output_id: str, baseline_scene: dict) -> dict:
    meta, probe, geometry = load_case(root, phase, output_id)
    fixture = read_json(root / "engineering_fixture_manual20.json")
    point_check = bindings_and_points(probe, fixture)
    scene_check = scene_contract_comparison(baseline_scene, geometry["scene_contract"])
    checks = {
        "control_chain": meta["control_chain"]["passed"],
        "topology": probe["model"]["topology_signature_sha256"] == EXPECTED_TOPOLOGY and probe["model"]["vertex_count"] == 6890 and probe["model"]["face_count"] == 13776,
        "bindings_points_visibility": point_check["passed"],
        "frozen_scene_contract": scene_check["passed"],
        "global_pair_list_complete": geometry["geometry"]["pair_list_complete"] is True,
    }
    return {"passed": all(checks.values()), "checks": checks, "point_details": point_check, "scene_details": scene_check}


def compare_replay(root: Path, phase: str, first: str, second: str) -> dict:
    _, probe_a, geometry_a = load_case(root, phase, first)
    _, probe_b, geometry_b = load_case(root, phase, second)
    probe_comparison = shared.compare_probes(probe_a, probe_b)
    pairs_equal = geometry_a["geometry"]["global_nonadjacent_overlap_pairs"] == geometry_b["geometry"]["global_nonadjacent_overlap_pairs"]
    ring_equal = all(geometry_a["geometry"][key] == geometry_b["geometry"][key] for key in ("ring2_overlap_pairs", "ring3_overlap_pairs"))
    scene_equal = scene_contract_comparison(geometry_a["scene_contract"], geometry_b["scene_contract"])
    return {"passed": probe_comparison["passed"] and pairs_equal and ring_equal and scene_equal["passed"], "probe": probe_comparison, "global_pairs_equal": pairs_equal, "ring_pairs_equal": ring_equal, "scene": scene_equal}


def draw_montage(items: list[tuple[str, Path, str]], output: Path, columns: int, thumb=(240, 192)) -> None:
    rows_count = math.ceil(len(items) / columns)
    cell_h = thumb[1] + 34
    canvas = Image.new("RGB", (columns * thumb[0], rows_count * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    colors = {
        "QUALIFIED": (40, 165, 85), "CAUTION": (235, 160, 35),
        "REJECT": (215, 60, 60), "ERROR": (170, 40, 180), "SMOKE": (55, 120, 210),
    }
    for index, (label, path, status) in enumerate(items):
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail(thumb, Image.Resampling.LANCZOS)
        x, y = (index % columns) * thumb[0], (index // columns) * cell_h
        canvas.paste(image, (x + (thumb[0] - image.width) // 2, y + 30))
        group = next((key for key in colors if status.startswith(key)), "SMOKE")
        draw.rectangle((x + 1, y + 1, x + thumb[0] - 2, y + cell_h - 2), outline=colors[group], width=3)
        draw.text((x + 5, y + 5), label[:38], fill="black", font=font)
        draw.text((x + 5, y + 17), status, fill=colors[group], font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def run_smoke(root: Path) -> None:
    prepare(root)
    config = read_json(root / "shape_pose_cross_config_v1.json")
    by_id = {item["case_id"]: item for item in config["cells"]}
    baseline_id = case_id("S0_BASE", "P0_BASE")
    with tempfile.TemporaryDirectory(prefix="acu_cross_smoke_") as temporary_name:
        temporary = Path(temporary_name)
        for index, (shape_id, pose_id) in enumerate(SMOKE_PAIRS, start=1):
            identifier = case_id(shape_id, pose_id)
            run_case(root, "smoke", by_id[identifier], identifier, temporary)
            print(f"SMOKE {index}/{len(SMOKE_PAIRS)} {identifier}", flush=True)
        run_case(root, "smoke", by_id[baseline_id], "SMOKE_R_BASE", temporary)
        repeat_id = case_id("C05_THICK_UPPER_WIDE", "D06_THORAX_EXTENSION_P4")
        run_case(root, "smoke", by_id[repeat_id], f"SMOKE_REPEAT__{repeat_id}", temporary)

    _, _, base_geometry = load_case(root, "smoke", baseline_id)
    cases = []
    for shape_id, pose_id in SMOKE_PAIRS:
        identifier = case_id(shape_id, pose_id)
        checks = system_checks(root, "smoke", identifier, base_geometry["scene_contract"])
        _, probe, geometry = load_case(root, "smoke", identifier)
        cases.append({
            "case_id": identifier, "pipeline_passed": checks["passed"], "system_checks": checks,
            "candidate_geometry_status": (
                "REJECT_BED_CLEARANCE" if float(probe["bed"]["minimum_body_clearance_m"]) < MIN_CLEARANCE_M
                else "REJECT_TARGET_LOCAL_INTERSECTION" if int(geometry["geometry"]["ring2_overlap_pair_count"]) > 0
                else "SMOKE_GEOMETRY_CLEAR"
            ),
            "bed_clearance_m": probe["bed"]["minimum_body_clearance_m"],
            "ring2_overlap_pair_count": geometry["geometry"]["ring2_overlap_pair_count"],
            "global_overlap_pair_count": geometry["geometry"]["global_nonadjacent_overlap_pair_count"],
        })
    restore = compare_replay(root, "smoke", baseline_id, "SMOKE_R_BASE")
    repeat_id = case_id("C05_THICK_UPPER_WIDE", "D06_THORAX_EXTENSION_P4")
    repeat = compare_replay(root, "smoke", repeat_id, f"SMOKE_REPEAT__{repeat_id}")
    baseline_hard_gate = next(item for item in cases if item["case_id"] == baseline_id)
    passed = all(item["pipeline_passed"] for item in cases) and baseline_hard_gate["candidate_geometry_status"] == "SMOKE_GEOMETRY_CLEAR" and restore["passed"] and repeat["passed"]
    report = {
        "schema": "controlled-shape-pose-smoke-verification-v1", "passed": passed,
        "pipeline_gate_definition": "High-risk candidates may be legitimately rejected; Smoke passes when the pipeline classifies them deterministically without contract errors.",
        "cases": cases, "baseline_restore": restore, "high_risk_repeat": repeat,
    }
    write_json(root / "smoke_verification.json", report)
    draw_montage([(item["case_id"], root / "smoke" / "overlays" / f"{item['case_id']}.png", "SMOKE") for item in cases], root / "smoke_montage.png", columns=3, thumb=(320, 256))
    print(json.dumps({"SMOKE": "PASS" if passed else "FAIL", "cases": len(cases)}, ensure_ascii=False), flush=True)
    if not passed:
        raise SystemExit(2)


def interaction_residual(probes: dict[str, dict], cell: dict) -> dict:
    identifier = cell["case_id"]
    s0p0 = probes[case_id("S0_BASE", "P0_BASE")]
    sp = probes[identifier]
    sp0 = probes[case_id(cell["shape_id"], "P0_BASE")]
    s0p = probes[case_id("S0_BASE", cell["pose_id"])]
    maps = [{item["point_id"]: item for item in source["points"]} for source in (sp, sp0, s0p, s0p0)]
    rows = []
    for point_id in maps[0]:
        a, b, c, d = (mapping[point_id] for mapping in maps)
        xyz = np.asarray(a["xyz_world_m"]) - np.asarray(b["xyz_world_m"]) - np.asarray(c["xyz_world_m"]) + np.asarray(d["xyz_world_m"])
        camera = np.asarray(a["xyz_camera_opencv_m"]) - np.asarray(b["xyz_camera_opencv_m"]) - np.asarray(c["xyz_camera_opencv_m"]) + np.asarray(d["xyz_camera_opencv_m"])
        uv = np.asarray(a["uv_pixel_opencv"]) - np.asarray(b["uv_pixel_opencv"]) - np.asarray(c["uv_pixel_opencv"]) + np.asarray(d["uv_pixel_opencv"])
        expected_normal = np.asarray(b["normal_world"]) + np.asarray(c["normal_world"]) - np.asarray(d["normal_world"])
        if np.linalg.norm(expected_normal) > 0:
            expected_normal /= np.linalg.norm(expected_normal)
        actual_normal = np.asarray(a["normal_world"])
        normal_angle = math.degrees(math.acos(float(np.clip(np.dot(actual_normal, expected_normal), -1.0, 1.0))))
        area_residual = float(a["triangle_area_m2"] - b["triangle_area_m2"] - c["triangle_area_m2"] + d["triangle_area_m2"])
        edge_residual = np.asarray(a["triangle_edge_lengths_m"]) - np.asarray(b["triangle_edge_lengths_m"]) - np.asarray(c["triangle_edge_lengths_m"]) + np.asarray(d["triangle_edge_lengths_m"])
        rows.append({
            "point_id": point_id, "xyz_world_residual_mm": float(np.linalg.norm(xyz) * 1000.0),
            "xyz_camera_residual_mm": float(np.linalg.norm(camera) * 1000.0), "uv_residual_px": float(np.linalg.norm(uv)),
            "normal_interaction_angle_deg": normal_angle, "triangle_area_residual_mm2": area_residual * 1e6,
            "triangle_edge_residual_norm_mm": float(np.linalg.norm(edge_residual) * 1000.0),
        })
    clearance = float(sp["bed"]["minimum_body_clearance_m"] - sp0["bed"]["minimum_body_clearance_m"] - s0p["bed"]["minimum_body_clearance_m"] + s0p0["bed"]["minimum_body_clearance_m"])
    fields = ["xyz_world_residual_mm", "xyz_camera_residual_mm", "uv_residual_px", "normal_interaction_angle_deg", "triangle_area_residual_mm2", "triangle_edge_residual_norm_mm"]
    summary = {f"max_{field}": max(row[field] for row in rows) for field in fields}
    summary.update({f"mean_{field}": float(np.mean([row[field] for row in rows])) for field in fields})
    summary["clearance_interaction_residual_mm"] = clearance * 1000.0
    return {"case_id": identifier, "shape_id": cell["shape_id"], "pose_id": cell["pose_id"], "summary": summary, "points": rows}


def run_preflight(root: Path) -> None:
    if not read_json(root / "smoke_verification.json")["passed"]:
        raise RuntimeError("Smoke must pass before the 63-cell preflight")
    config = read_json(root / "shape_pose_cross_config_v1.json")
    cells = config["cells"]
    with tempfile.TemporaryDirectory(prefix="acu_cross_preflight_") as temporary_name:
        temporary = Path(temporary_name)
        for index, cell in enumerate(cells, start=1):
            run_case(root, "preflight", cell, cell["case_id"], temporary)
            write_json(root / "preflight_progress.json", {"completed": index, "total": len(cells), "last_case": cell["case_id"]})
            print(f"PREFLIGHT {index}/{len(cells)} {cell['case_id']}", flush=True)

    baseline_id = case_id("S0_BASE", "P0_BASE")
    _, _, base_geometry = load_case(root, "preflight", baseline_id)
    probes, geometries = {}, {}
    for cell in cells:
        _, probes[cell["case_id"]], geometries[cell["case_id"]] = load_case(root, "preflight", cell["case_id"])
    rows = []
    for cell in cells:
        identifier = cell["case_id"]
        probe, geometry = probes[identifier], geometries[identifier]
        systems = system_checks(root, "preflight", identifier, base_geometry["scene_contract"])
        current_pairs = {tuple(pair) for pair in geometry["geometry"]["global_nonadjacent_overlap_pairs"]}
        baseline_pairs = {tuple(pair) for pair in geometries[baseline_id]["geometry"]["global_nonadjacent_overlap_pairs"]}
        current_ring3_pairs = {tuple(pair) for pair in geometry["geometry"]["ring3_overlap_pairs"]}
        baseline_ring3_pairs = {tuple(pair) for pair in geometries[baseline_id]["geometry"]["ring3_overlap_pairs"]}
        shape_parent = case_id(cell["shape_id"], "P0_BASE")
        pose_parent = case_id("S0_BASE", cell["pose_id"])
        parent_union = {
            tuple(pair) for pair in geometries[shape_parent]["geometry"]["global_nonadjacent_overlap_pairs"]
        } | {
            tuple(pair) for pair in geometries[pose_parent]["geometry"]["global_nonadjacent_overlap_pairs"]
        }
        parent_ring3_union = {
            tuple(pair) for pair in geometries[shape_parent]["geometry"]["ring3_overlap_pairs"]
        } | {
            tuple(pair) for pair in geometries[pose_parent]["geometry"]["ring3_overlap_pairs"]
        }
        interaction_new = sorted(current_pairs - parent_union)
        added_vs_baseline = sorted(current_pairs - baseline_pairs)
        # Absolute ring-3 is not a useful warning because the frozen baseline
        # already contains 33 historical pairs in that wider neighborhood.
        # Controls are compared to baseline; novel interactions are compared
        # to the union of their already-qualified Shape-only/Pose-only parents.
        ring3_new = sorted(
            current_ring3_pairs
            - (parent_ring3_union if cell["kind"] == "novel_interaction" else baseline_ring3_pairs)
        )
        clearance = float(probe["bed"]["minimum_body_clearance_m"])
        ring2_count = int(geometry["geometry"]["ring2_overlap_pair_count"])
        ring3_count = int(geometry["geometry"]["ring3_overlap_pair_count"])
        if not systems["passed"]:
            status = "ERROR_GEOMETRY"
        elif clearance < MIN_CLEARANCE_M:
            status = "REJECT_BED_CLEARANCE"
        elif ring2_count > 0:
            status = "REJECT_TARGET_LOCAL_INTERSECTION"
        elif ring3_new:
            status = "CAUTION_THREE_RING_INTERSECTION"
        elif interaction_new:
            status = "CAUTION_NEW_GLOBAL_OVERLAP"
        else:
            status = "QUALIFIED"
        rows.append({
            **cell, "status": status, "system_checks": systems,
            "bed_clearance_m": clearance, "visible_count": sum(bool(item["visible"]) for item in probe["points"]),
            "global_overlap_pair_count": len(current_pairs), "ring2_overlap_pair_count": ring2_count,
            "ring3_overlap_pair_count": ring3_count,
            "ring3_new_pair_count": len(ring3_new), "ring3_new_pairs": [list(pair) for pair in ring3_new],
            "new_vs_baseline_pair_count": len(added_vs_baseline), "new_vs_baseline_pairs": [list(pair) for pair in added_vs_baseline],
            "interaction_new_pair_count": len(interaction_new), "interaction_new_pairs": [list(pair) for pair in interaction_new],
        })
    interaction_rows = [interaction_residual(probes, cell) for cell in cells if cell["kind"] == "novel_interaction"]
    write_json(root / "geometry_preflight_report.json", {
        "schema": "controlled-shape-pose-geometry-preflight-v1", "medical_truth": False,
        "passed": len(rows) == 63 and not any(item["status"] == "ERROR_GEOMETRY" for item in rows),
        "baseline_global_overlap_count": geometries[baseline_id]["geometry"]["global_nonadjacent_overlap_pair_count"],
        "classification_policy": {
            "hard_clearance_m": MIN_CLEARANCE_M,
            "ring2": "absolute hard reject",
            "ring3": "caution only for pairs new versus baseline (control cells) or parent union (novel interactions)",
            "interaction_new_global_pairs": "caution pending visual review",
            "interaction_pair_definition": "G(s,p) minus union(G(s,p0), G(s0,p))",
        },
        "cells": rows,
    })
    write_json(root / "interaction_residual_report.json", {
        "schema": "shape-pose-interaction-residual-v1", "medical_truth": False,
        "definition": "P(s,p)-P(s,p0)-P(s0,p)+P(s0,p0)", "novel_interaction_count": len(interaction_rows), "cases": interaction_rows,
    })
    with (root / "shape_pose_cross_matrix.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case_id", "shape_id", "pose_id", "kind", "status", "bed_clearance_m", "visible_count", "global_overlap_pair_count", "ring2_overlap_pair_count", "ring3_overlap_pair_count", "ring3_new_pair_count", "new_vs_baseline_pair_count", "interaction_new_pair_count"])
        writer.writeheader()
        for item in rows:
            writer.writerow({key: item[key] for key in writer.fieldnames})
    draw_montage(
        [(item["case_id"], root / "preflight" / "overlays" / f"{item['case_id']}.png", item["status"]) for item in rows],
        root / "shape_pose_matrix_montage.png", columns=9, thumb=(200, 160),
    )
    cautions = [item for item in rows if item["status"].startswith("CAUTION")]
    if cautions:
        draw_montage(
            [(item["case_id"], root / "preflight" / "overlays" / f"{item['case_id']}.png", item["status"]) for item in cautions],
            root / "caution_montage.png", columns=4, thumb=(320, 256),
        )
    counts = {status: sum(item["status"] == status for item in rows) for status in sorted({item["status"] for item in rows})}
    print(json.dumps({"PREFLIGHT": "PASS", "counts": counts}, ensure_ascii=False), flush=True)


def run_rgbd(root: Path) -> None:
    preflight = read_json(root / "geometry_preflight_report.json")
    if not preflight["passed"]:
        raise RuntimeError("geometry preflight must pass before RGB-D")
    config = read_json(root / "shape_pose_cross_config_v1.json")
    by_id = {item["case_id"]: item for item in config["cells"]}
    qualified = [item for item in preflight["cells"] if item["status"] == "QUALIFIED"]
    results = []
    with tempfile.TemporaryDirectory(prefix="acu_cross_rgbd_") as temporary_name:
        temporary = Path(temporary_name)
        for index, item in enumerate(qualified, start=1):
            identifier = item["case_id"]
            run_case(root, "rgbd", by_id[identifier], identifier, temporary, export_rgbd=True)
            meta, probe, geometry = load_case(root, "rgbd", identifier)
            _, pre_probe, pre_geometry = load_case(root, "preflight", identifier)
            geometry_replay = shared.compare_probes(pre_probe, probe)
            pairs_equal = pre_geometry["geometry"]["global_nonadjacent_overlap_pairs"] == geometry["geometry"]["global_nonadjacent_overlap_pairs"]
            qc = read_json(root / "rgbd" / "qc" / f"{identifier}.json")
            passed = bool(meta.get("qc_passed") and geometry_replay["passed"] and pairs_equal)
            results.append({
                "case_id": identifier, "passed": passed, "qc": qc, "geometry_replay": geometry_replay,
                "intersection_pairs_equal_to_preflight": pairs_equal,
                "sample": str((root / "rgbd" / "samples" / identifier).relative_to(root)),
            })
            write_json(root / "rgbd_progress.json", {"completed": index, "total": len(qualified), "last_case": identifier})
            print(f"RGBD {index}/{len(qualified)} {identifier}: {'PASS' if passed else 'FAIL'}", flush=True)
    report = {
        "schema": "controlled-shape-pose-rgbd-report-v1", "medical_truth": False,
        "passed": len(results) == len(qualified) and all(item["passed"] for item in results),
        "qualified_input_count": len(qualified), "cases": results,
        "rgb_exact_hash_required": False, "geometry_depth_valid_skin_masks_are_hard_gates": True,
    }
    write_json(root / "rgbd_report.json", report)
    if not report["passed"]:
        raise SystemExit(3)


def compare_buffers(primary: Path, replay: Path) -> dict:
    names = ("rgb.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png")
    details = {}
    for name in names:
        left, right = sha256(primary / name), sha256(replay / name)
        details[name] = {"primary": left, "replay": right, "equal": left == right, "required": name != "rgb.png"}
    return {"passed": all(item["equal"] for item in details.values() if item["required"]), "files": details}


def run_determinism(root: Path) -> None:
    rgbd = read_json(root / "rgbd_report.json")
    if not rgbd["passed"]:
        raise RuntimeError("RGB-D stage must pass before determinism")
    config = read_json(root / "shape_pose_cross_config_v1.json")
    by_id = {item["case_id"]: item for item in config["cells"]}
    results = []
    with tempfile.TemporaryDirectory(prefix="acu_cross_determinism_") as temporary_name:
        temporary = Path(temporary_name)
        for index, primary in enumerate(rgbd["cases"], start=1):
            identifier = primary["case_id"]
            run_case(root, "determinism", by_id[identifier], identifier, temporary, export_rgbd=True, temporary_sample=True)
            _, probe, geometry = load_case(root, "determinism", identifier)
            _, primary_probe, primary_geometry = load_case(root, "rgbd", identifier)
            geometry_compare = shared.compare_probes(primary_probe, probe)
            pairs_equal = primary_geometry["geometry"]["global_nonadjacent_overlap_pairs"] == geometry["geometry"]["global_nonadjacent_overlap_pairs"]
            buffer_compare = compare_buffers(root / "rgbd" / "samples" / identifier, temporary / identifier / "sample")
            qc = read_json(root / "determinism" / "qc" / f"{identifier}.json")
            passed = bool(geometry_compare["passed"] and pairs_equal and buffer_compare["passed"] and qc["passed"])
            results.append({"case_id": identifier, "passed": passed, "geometry": geometry_compare, "intersection_pairs_equal": pairs_equal, "buffers": buffer_compare, "qc": qc})
            write_json(root / "determinism_progress.json", {"completed": index, "total": len(rgbd["cases"]), "last_case": identifier})
            print(f"DETERMINISM {index}/{len(rgbd['cases'])} {identifier}: {'PASS' if passed else 'FAIL'}", flush=True)

        baseline_id = case_id("S0_BASE", "P0_BASE")
        run_case(root, "determinism", by_id[baseline_id], "R_BASE", temporary)
    restore = compare_replay(root, "determinism", baseline_id, "R_BASE") if (root / "determinism" / "case_meta" / f"{baseline_id}.json").is_file() else None
    # The baseline is always a qualified RGB-D case and therefore already replayed above.
    if restore is None:
        raise RuntimeError("determinism baseline replay is missing")
    report = {
        "schema": "controlled-shape-pose-determinism-v1", "medical_truth": False,
        "passed": all(item["passed"] for item in results) and restore["passed"],
        "fresh_native_generation_and_blender_process_per_case": True,
        "rgb_exact_hash_reported_not_required": True, "cases": results, "baseline_restore": restore,
    }
    write_json(root / "determinism_report.json", report)
    if not report["passed"]:
        raise SystemExit(4)


def build_manifest(root: Path) -> dict:
    manifest = root / "SHA256SUMS.txt"
    rows = [
        f"{sha256(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*")) if path.is_file() and path != manifest
    ]
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"entries": len(rows), "manifest_sha256": sha256(manifest)}


def finalize(root: Path) -> None:
    preflight = read_json(root / "geometry_preflight_report.json")
    rgbd = read_json(root / "rgbd_report.json")
    determinism = read_json(root / "determinism_report.json")
    visual_path = root / "visual_review.json"
    if not visual_path.is_file():
        raise RuntimeError("visual_review.json is required before finalization")
    visual = read_json(visual_path)
    rgbd_by_id = {item["case_id"]: item for item in rgbd["cases"]}
    det_by_id = {item["case_id"]: item for item in determinism["cases"]}
    qualified, cautions, rejected = [], [], []
    for cell in preflight["cells"]:
        record = {key: cell[key] for key in ("case_id", "shape_id", "pose_id", "kind", "status", "bed_clearance_m", "visible_count", "global_overlap_pair_count", "ring2_overlap_pair_count", "ring3_overlap_pair_count", "ring3_new_pair_count", "interaction_new_pair_count")}
        if cell["status"] == "QUALIFIED" and rgbd_by_id.get(cell["case_id"], {}).get("passed") and det_by_id.get(cell["case_id"], {}).get("passed"):
            record["qualification"] = "FIXED_PRONE_ENGINEERING_SCENE_ONLY"
            qualified.append(record)
        elif cell["status"].startswith("CAUTION"):
            cautions.append(record)
        else:
            rejected.append(record)
    write_json(root / "QUALIFIED_SHAPE_POSE_COMBINATIONS_FIXED_PRONE_V1.json", {
        "schema": "qualified-shape-pose-combinations-fixed-prone-v1", "medical_truth": False, "medical_validated": False,
        "scope": "fixed canonical SKEL/fixed prone scene/fixed bed-camera-light-material/current 20 engineering points",
        "combination_count": len(qualified), "combinations": qualified,
        "not_claimed": ["continuous parameter-space safety", "complete-body zero self-intersection", "medical validity", "real mattress contact", "robot safety"],
    })
    write_json(root / "caution_combinations.json", {"schema": "shape-pose-caution-combinations-v1", "medical_truth": False, "count": len(cautions), "combinations": cautions})
    write_json(root / "rejected_combinations.json", {"schema": "shape-pose-rejected-combinations-v1", "medical_truth": False, "count": len(rejected), "combinations": rejected})
    source_unchanged = read_json(root / "source_hashes_before.json") == protected_sources()
    novel_qualified = sum(item["kind"] == "novel_interaction" for item in qualified)
    verification = {
        "schema": "controlled-shape-pose-cross-validation-verification-v1",
        "passed": bool(
            read_json(root / "smoke_verification.json")["passed"]
            and preflight["passed"] and rgbd["passed"] and determinism["passed"]
            and visual.get("passed") is True and source_unchanged and len(preflight["cells"]) == 63
            and novel_qualified > 0
        ),
        "matrix_cells": 63, "control_cells": 15, "novel_interaction_cells": 48,
        "qualified_count": len(qualified), "qualified_novel_interaction_count": novel_qualified,
        "caution_count": len(cautions), "rejected_or_error_count": len(rejected),
        "smoke_passed": read_json(root / "smoke_verification.json")["passed"],
        "geometry_preflight_passed": preflight["passed"], "rgbd_passed": rgbd["passed"],
        "determinism_and_restore_passed": determinism["passed"], "visual_review_passed": visual.get("passed") is True,
        "protected_sources_unchanged": source_unchanged,
        "truth_status": {"kind": "ENGINEERING_REFERENCE", "medical_truth": False, "medical_validated": False},
        "limitations": [
            "Qualified means only the frozen prone engineering scene and discrete tested combinations.",
            "Caution combinations are not promoted to qualified.",
            "The frozen baseline has known global nonadjacent triangle overlaps.",
            "No medical, real-camera, real-mattress, generalization, or robot-safety claim is made.",
        ],
    }
    write_json(root / "verification.json", verification)
    counts = {status: sum(item["status"] == status for item in preflight["cells"]) for status in sorted({item["status"] for item in preflight["cells"]})}
    lines = [
        "# CONTROLLED_SHAPE_POSE_CROSS_VALIDATION_V1", "",
        f"结果：**{'PASS' if verification['passed'] else 'FAIL'}**。63 格（15 回归对照 + 48 新交互）完成几何预检；最终冻结 {len(qualified)} 个固定俯卧工程组合，其中 {novel_qualified} 个为真正新交互。", "",
        "## 分类", "", *(f"- `{key}`：{value}" for key, value in counts.items()), "",
        "## 边界", "",
        "- E01–E20 是工程参考点，不是医学穴位。",
        "- `QUALIFIED` 只代表当前离散 Shape×Pose、固定 Camera/Bed/Light/Material 和刚性俯卧场景。",
        "- CAUTION 未自动提升；完整人体零自交、软床接触、医学和机器人安全均未成立。",
        "- 完整证据保留在本机内部目录；GPT 网页端另生成精简审查包。",
    ]
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = build_manifest(root)
    print(json.dumps({"FINAL": "PASS" if verification["passed"] else "FAIL", **result, "qualified": len(qualified)}, ensure_ascii=False), flush=True)
    if not verification["passed"]:
        raise SystemExit(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "smoke", "preflight", "rgbd", "determinism", "finalize"))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.root)
    elif args.mode == "smoke":
        run_smoke(args.root)
    elif args.mode == "preflight":
        run_preflight(args.root)
    elif args.mode == "rgbd":
        run_rgbd(args.root)
    elif args.mode == "determinism":
        run_determinism(args.root)
    else:
        finalize(args.root)


if __name__ == "__main__":
    main()
