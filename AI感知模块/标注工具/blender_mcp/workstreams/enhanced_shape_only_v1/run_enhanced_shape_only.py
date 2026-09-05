#!/usr/bin/env python3
"""Run and finalize ENHANCED_SHAPE_ONLY_V1 without touching frozen inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


AI_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
TOOL_ROOT = AI_ROOT / "标注工具" / "blender_mcp"
WS = Path(__file__).resolve().parent
NATURAL_WS = TOOL_ROOT / "workstreams" / "natural_prone_pose"
PRONE_WS = TOOL_ROOT / "workstreams" / "prone_rgbd"
VERIFY_WS = TOOL_ROOT / "workstreams" / "independent_verifier"
SHAPE_WS = TOOL_ROOT / "workstreams" / "prone_shape_regression"
WORKBENCH = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_完整版" / "医生穴位标注工作台_v2.3.0_完整版"
BLENDER = WORKBENCH / "runtime" / "blender" / "blender.exe"
CANONICAL = AI_ROOT / "模型资源" / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发" / "templates" / "SKEL" / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
ATLAS = AI_ROOT / "outputs" / "交付文件" / "2026-08-29_16-21-55" / "source_atlas_v5.json"
PARENT_SCENES = AI_ROOT / "outputs" / "交付文件" / "2026-08-28_20-21-54"
PARENT_LABELS = AI_ROOT / "outputs" / "交付文件" / "2026-08-29_16-21-55"
PROFILE_BASE = NATURAL_WS / "natural_prone_pose_profile.json"
CONTRACT_SCENE = NATURAL_WS / "fixed_scene_contract.json"
GENERATE = NATURAL_WS / "generate_native_pose.py"
PREPARE = PRONE_WS / "prepare_prone_scene.py"
EXPORT = PRONE_WS / "export_prone_sample.py"
RENDER = NATURAL_WS / "render_preview.py"
VERIFY_SAMPLE = VERIFY_WS / "verify_sample.py"
PROTECTED_MANIFEST = VERIFY_WS / "protected_assets.json"
BUILD_CONTRACT = WS / "build_measurement_contract.py"
PROBE = WS / "probe_enhanced_shape_case.py"
OLD_SMOKE = AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "prone_shape_regression" / "2026-08-28_16-44-42_shape_smoke" / "shape_smoke_report.json"
SAFE_SET = SHAPE_WS / "safe_shape_set_v1.json"
CORE_PARENT = AI_ROOT / "标注工具" / "blender_addons" / "modules"
EXPECTED_TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"
DEPTH_THRESHOLD_M = 0.003
BACKPROJECT_THRESHOLD_M = 0.003


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run(command: list[str], *, sentinel: str | None = None, env=None, timeout=1800) -> str:
    result = subprocess.run(command, cwd=str(TOOL_ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    combined = result.stdout + "\n" + result.stderr
    if result.returncode != 0 or (sentinel and sentinel not in combined):
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{combined[-14000:]}")
    return combined


def blender_env() -> dict[str, str]:
    value = os.environ.copy()
    value.update({
        "BLENDER_USER_RESOURCES": str(WORKBENCH / "user_resources"),
        "ACUPOINT_MCP_PROJECT_ROOT": str(AI_ROOT),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    return value


def bj(blend: Path, script: Path, args: list[object], sentinel: str | None) -> str:
    return run([str(BLENDER), "--background", str(blend), "--python", str(script), "--", *map(str, args)], sentinel=sentinel, env=blender_env())


def make_profile(base: dict, case: str, beta_index: int | None, value: float) -> dict:
    profile = json.loads(json.dumps(base))
    betas = [0.0] * 10
    if beta_index is not None:
        betas[beta_index] = value
    profile.update({
        "schema": "enhanced-skel-shape-only-profile-v1",
        "profile_id": case,
        "medical_truth": False,
        "betas": betas,
        "shape_test": {"beta_index_zero_based": beta_index, "value": value},
    })
    return profile


def case_definitions(include_restore: bool = False):
    cases = [("A_BASE", None, 0.0)]
    cases += [(f"B{index + 1:02d}_{suffix}", index, value) for index in range(10) for suffix, value in (("NEG", -0.5), ("POS", 0.5))]
    if include_restore:
        cases.append(("R_BASE", None, 0.0))
    return cases


def make_fixture(atlas: dict) -> dict:
    return {
        "schema": "manual-atlas-v5-engineering-fixture-v1",
        "medical_truth": False,
        "medical_validated": False,
        "acceptance_must_not_reselect": True,
        "model": atlas["model"],
        "anchors": [dict(item) for item in atlas["annotations"]],
        "notices": [
            "Converted losslessly from the current plugin schema-v5 engineering/reference Atlas.",
            "These records are not doctor-confirmed medical ground truth.",
        ],
    }


def overlay_from_probe(rgb: Path, probe: dict, output: Path) -> None:
    with Image.open(rgb) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    source_width, source_height = probe["camera"]["resolution"]
    scale_x = image.width / float(source_width)
    scale_y = image.height / float(source_height)
    for point in probe["points"]:
        u, v = point["uv_pixel_opencv"]
        u, v = float(u) * scale_x, float(v) * scale_y
        if not (0 <= u < image.width and 0 <= v < image.height):
            continue
        color = (0, 255, 110) if point["visible"] else (255, 80, 80)
        draw.ellipse((u - 4, v - 4, u + 4, v + 4), fill=color, outline="white", width=1)
        draw.text((u + 6, v - 7), point["point_id"], fill="black", stroke_width=2, stroke_fill="white", font=font)
    image.save(output)


def strict_sample_qc(sample: Path, fixture: dict, expected_betas: list[float]) -> dict:
    labels = read_json(sample / "labels.json")
    depth = np.load(sample / "scene_depth_z.npy", allow_pickle=False)
    with Image.open(sample / "skin_mask.png") as image:
        skin = np.asarray(image.convert("L"))
    with Image.open(sample / "depth_valid_mask.png") as image:
        valid = np.asarray(image.convert("L"))
    k = labels["camera"]["intrinsics"]
    expected = {item["point_id"]: item for item in fixture["anchors"]}
    details = []
    for point in labels["points"]:
        anchor = expected[point["point_id"]]
        binding = all(point[key] == anchor[key] for key in ("face_index", "vertex_indices", "barycentric", "side"))
        u, v = map(float, point["uv_pixel_opencv"])
        in_frame = 0 <= u < depth.shape[1] and 0 <= v < depth.shape[0]
        observed = float(depth[int(v), int(u)]) if in_frame else 0.0
        gt = [float(value) for value in point["xyz_camera_opencv_m"]]
        if point["visible"] and in_frame and observed > 0:
            lifted = [(u - k["cx"]) * observed / k["fx"], (v - k["cy"]) * observed / k["fy"], observed]
            depth_error = abs(observed - gt[2])
            backproject_error = math.dist(lifted, gt)
            pixel_ok = skin[int(v), int(u)] == 255 and valid[int(v), int(u)] == 255
            passed = binding and pixel_ok and point["ray_hit_object"] == "SKEL-skin-female" and depth_error <= DEPTH_THRESHOLD_M and backproject_error <= BACKPROJECT_THRESHOLD_M
        else:
            depth_error = None
            backproject_error = None
            passed = binding and point["visibility_reason"] != "VISIBLE"
        details.append({"point_id": point["point_id"], "passed": bool(passed), "depth_error_m": depth_error, "backprojection_error_m": backproject_error})
    visible_depth = [item["depth_error_m"] for item in details if item["depth_error_m"] is not None]
    visible_back = [item["backprojection_error_m"] for item in details if item["backprojection_error_m"] is not None]
    checks = {
        "resolution": list(depth.shape[::-1]) == [int(k["width"]), int(k["height"])],
        "point_count": len(details) == len(fixture["anchors"]) == 20,
        "shape_recorded": [float(v) for v in labels["scene"]["native_shape_betas"]] == expected_betas,
        "bindings_and_visibility": all(item["passed"] for item in details),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "points": details,
        "visible_count": sum(bool(point["visible"]) for point in labels["points"]),
        "max_depth_error_m": max(visible_depth, default=0.0),
        "max_backprojection_error_m": max(visible_back, default=0.0),
    }


def source_hashes() -> dict:
    files = {
        "canonical_skel": CANONICAL,
        "current_manual_atlas": ATLAS,
        "parent_scene_dataset_index": PARENT_SCENES / "dataset_index.json",
        "parent_manual_label_qc": PARENT_LABELS / "dataset_qc_report.json",
        "natural_pose_profile": PROFILE_BASE,
        "fixed_scene_contract": CONTRACT_SCENE,
        "old_shape_smoke": OLD_SMOKE,
        "safe_shape_set": SAFE_SET,
        "skel_bridge": AI_ROOT / "模型资源" / "SKEL" / "skel_blender_bridge.py",
    }
    return {name: {"path": str(path), "sha256": sha256(path)} for name, path in files.items()}


def generate_one(root: Path, temporary: Path, run_id: str, case: str, beta_index: int | None, value: float, contract: Path | None, fixture_path: Path, *, export_rgbd: bool) -> tuple[dict, Path, Path]:
    run_root = root / "runs" / run_id
    profiles = run_root / "profiles"
    snapshots = run_root / "snapshots"
    probes = run_root / "probes"
    samples = run_root / "samples"
    for folder in (profiles, snapshots, probes, samples):
        folder.mkdir(parents=True, exist_ok=True)
    profile = make_profile(read_json(PROFILE_BASE), case, beta_index, value)
    profile_path = profiles / f"{case}.json"
    write_json(profile_path, profile)
    native = temporary / run_id / case / "native"
    native.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, str(GENERATE), "--profile", str(profile_path), "--output", str(native)])
    snapshot = snapshots / f"{case}.blend"
    prepare_result = run_root / "prepare" / f"{case}.json"
    bj(CANONICAL, PREPARE, ["--snapshot", snapshot, "--result", prepare_result, "--native-pose-dir", native, "--pose-profile", profile_path, "--fixed-scene-contract", CONTRACT_SCENE, "--width", 1280, "--height", 1024], "ACU_PREPARE_PRONE_SCENE=PASS")
    if contract is None:
        raise ValueError("measurement contract is required before probing")
    probe_path = probes / f"{case}.json"
    bj(snapshot, PROBE, ["--atlas", ATLAS, "--contract", contract, "--profile", profile_path, "--native-parameters", native / "parameters.json", "--core-parent", CORE_PARENT, "--output", probe_path, "--width", 1280, "--height", 1024], "ACU_ENHANCED_SHAPE_PROBE=PASS")
    probe = read_json(probe_path)
    sample_path = samples / case
    if export_rgbd:
        export_result = run_root / "export" / f"{case}.json"
        bj(snapshot, EXPORT, ["--fixture", fixture_path, "--output", sample_path, "--result", export_result, "--width", 1280, "--height", 1024], "ACU_EXPORT_PRONE_SAMPLE=PASS")
        overlay_from_probe(sample_path / "rgb.png", probe, sample_path / "overlay.png")
    else:
        sample_path.mkdir(parents=True, exist_ok=True)
        preview = sample_path / "rgb_preview.png"
        bj(snapshot, RENDER, [preview], "ACU_NATURAL_PRONE_PREVIEW=PASS")
        overlay_from_probe(preview, probe, sample_path / "overlay.png")
    return probe, snapshot, sample_path


def generate() -> Path:
    required = [BLENDER, CANONICAL, ATLAS, PROFILE_BASE, CONTRACT_SCENE, GENERATE, PREPARE, EXPORT, PROBE, BUILD_CONTRACT, OLD_SMOKE, SAFE_SET]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    root = AI_ROOT / "outputs" / "交付文件" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    root.mkdir(parents=True, exist_ok=False)
    initial_hashes = source_hashes()
    write_json(root / "source_hashes_before.json", initial_hashes)
    atlas = read_json(ATLAS)
    shutil.copy2(ATLAS, root / "source_atlas_v5.json")
    fixture = make_fixture(atlas)
    fixture_path = root / "engineering_fixture_manual20.json"
    write_json(fixture_path, fixture)
    configuration = {
        "schema": "enhanced-shape-only-config-v1",
        "medical_truth": False,
        "resolution": [1280, 1024],
        "pose_profile": str(PROFILE_BASE),
        "camera_bed_scene_contract": str(CONTRACT_SCENE),
        "atlas": str(ATLAS),
        "expected_fail": {"case": "B02_NEG", "reason": "BED_INCOMPATIBLE", "known_prior_penetration_m": 0.007701006717979908},
        "cases": [{"case": case, "beta_index_zero_based": index, "value": value, "requested_betas": make_profile(read_json(PROFILE_BASE), case, index, value)["betas"]} for case, index, value in case_definitions()],
    }
    write_json(root / "shape_only_config_v1.json", configuration)

    with tempfile.TemporaryDirectory(prefix="acu_enhanced_shape_") as temp_name:
        temporary = Path(temp_name)
        # Generate beta-zero first, then freeze the measurement vertex sets.
        base_profile = make_profile(read_json(PROFILE_BASE), "A_BASE", None, 0.0)
        pre_profile = root / "runs" / "A" / "profiles" / "A_BASE.json"
        write_json(pre_profile, base_profile)
        native = temporary / "A" / "A_BASE" / "native"
        native.parent.mkdir(parents=True, exist_ok=True)
        run([sys.executable, str(GENERATE), "--profile", str(pre_profile), "--output", str(native)])
        base_snapshot = root / "runs" / "A" / "snapshots" / "A_BASE.blend"
        prepare_result = root / "runs" / "A" / "prepare" / "A_BASE.json"
        bj(CANONICAL, PREPARE, ["--snapshot", base_snapshot, "--result", prepare_result, "--native-pose-dir", native, "--pose-profile", pre_profile, "--fixed-scene-contract", CONTRACT_SCENE, "--width", 1280, "--height", 1024], "ACU_PREPARE_PRONE_SCENE=PASS")
        measurement_contract = root / "body_measurement_contract_v1.json"
        bj(base_snapshot, BUILD_CONTRACT, ["--atlas", ATLAS, "--output", measurement_contract], "ACU_BODY_MEASUREMENT_CONTRACT=PASS")

        results_a = []
        for ordinal, (case, index, value) in enumerate(case_definitions(), start=1):
            if case == "A_BASE":
                probe_path = root / "runs" / "A" / "probes" / "A_BASE.json"
                probe_path.parent.mkdir(parents=True, exist_ok=True)
                bj(base_snapshot, PROBE, ["--atlas", ATLAS, "--contract", measurement_contract, "--profile", pre_profile, "--native-parameters", native / "parameters.json", "--core-parent", CORE_PARENT, "--output", probe_path, "--width", 1280, "--height", 1024], "ACU_ENHANCED_SHAPE_PROBE=PASS")
                probe, snapshot = read_json(probe_path), base_snapshot
                sample = root / "runs" / "A" / "samples" / case
                export_result = root / "runs" / "A" / "export" / f"{case}.json"
                bj(snapshot, EXPORT, ["--fixture", fixture_path, "--output", sample, "--result", export_result, "--width", 1280, "--height", 1024], "ACU_EXPORT_PRONE_SAMPLE=PASS")
                overlay_from_probe(sample / "rgb.png", probe, sample / "overlay.png")
            else:
                expected_fail = case == "B02_NEG"
                probe, snapshot, sample = generate_one(root, temporary, "A", case, index, value, measurement_contract, fixture_path, export_rgbd=not expected_fail)
            clearance = float(probe["bed"]["minimum_body_clearance_m"])
            expected_fail = case == "B02_NEG"
            status = "EXPECTED_FAIL_BED_INCOMPATIBLE" if expected_fail and clearance < 0 else ("UNEXPECTED_RESULT" if expected_fail else "PASS")
            qc = None
            if not expected_fail:
                qc = strict_sample_qc(sample, fixture, probe["effective_betas"])
                write_json(root / "runs" / "A" / "qc" / f"{case}.json", qc)
                if not qc["passed"]:
                    status = "FAIL"
            results_a.append({"case": case, "status": status, "clearance_m": clearance, "probe": str((root / "runs" / "A" / "probes" / f"{case}.json").relative_to(root)), "sample": str(sample.relative_to(root)), "qc": qc})
            write_json(root / "batch_progress.json", {"phase": "run_A", "completed": ordinal, "total": 21, "results": results_a})
            print(f"RUN A {ordinal}/21 {case}: {status} clearance={clearance*1000:.3f}mm", flush=True)

        # Restore beta zero after all nonzero cases, including full RGB-D.
        restore_probe, restore_snapshot, restore_sample = generate_one(root, temporary, "A", "R_BASE", None, 0.0, measurement_contract, fixture_path, export_rgbd=True)
        restore_qc = strict_sample_qc(restore_sample, fixture, restore_probe["effective_betas"])
        write_json(root / "runs" / "A" / "qc" / "R_BASE.json", restore_qc)

        # Run B reloads canonical inputs, regenerates native SKEL, reopens a fresh Blender,
        # and exports the same valid RGB-D configurations to a temporary directory.
        determinism_cases = []
        for ordinal, (case, index, value) in enumerate(case_definitions(), start=1):
            expected_fail = case == "B02_NEG"
            probe_b, _snapshot_b, sample_b = generate_one(root, temporary, "B", case, index, value, measurement_contract, fixture_path, export_rgbd=not expected_fail)
            probe_a = read_json(root / "runs" / "A" / "probes" / f"{case}.json")
            comparison = compare_probes(probe_a, probe_b)
            buffers = None
            if not expected_fail:
                sample_a = root / "runs" / "A" / "samples" / case
                buffers = {name: {"run_a": sha256(sample_a / name), "run_b": sha256(sample_b / name), "equal": sha256(sample_a / name) == sha256(sample_b / name)} for name in ("rgb.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png")}
            passed = comparison["passed"] and (expected_fail or all(value["equal"] for key, value in buffers.items() if key != "rgb.png"))
            determinism_cases.append({"case": case, "passed": passed, "geometry": comparison, "buffers": buffers})
            write_json(root / "determinism_progress.json", {"completed": ordinal, "total": 21, "cases": determinism_cases})
            print(f"RUN B {ordinal}/21 {case}: {'PASS' if passed else 'FAIL'}", flush=True)

    hashes_after = source_hashes()
    write_json(root / "source_hashes_after.json", hashes_after)
    if initial_hashes != hashes_after:
        raise RuntimeError("protected input hashes changed during enhanced Shape-only run")
    write_json(root / "run_results.json", {"run_a": results_a, "restore_qc": restore_qc})
    write_json(root / "determinism_report.json", {
        "schema": "enhanced-shape-only-determinism-v1",
        "passed": all(item["passed"] for item in determinism_cases),
        "fresh_blender_processes": True,
        "run_a_and_b_reloaded_canonical_inputs": True,
        "geometry_depth_mask_required_equal": True,
        "rgb_exact_hash_is_reported_but_not_required": True,
        "cases": determinism_cases,
    })
    generate_visuals_and_reports(root)
    print(json.dumps({"generated": True, "root": str(root)}, ensure_ascii=False), flush=True)
    return root


def compare_probes(a: dict, b: dict) -> dict:
    measurement_error = max(abs(float(a["measurements_m"][key]) - float(b["measurements_m"][key])) for key in a["measurements_m"])
    points_a = {item["point_id"]: item for item in a["points"]}
    points_b = {item["point_id"]: item for item in b["points"]}
    xyz_error = max(math.dist(points_a[key]["xyz_world_m"], points_b[key]["xyz_world_m"]) for key in points_a)
    uv_error = max(math.dist(points_a[key]["uv_pixel_opencv"], points_b[key]["uv_pixel_opencv"]) for key in points_a)
    bindings_equal = all(all(points_a[key][field] == points_b[key][field] for field in ("face_index", "vertex_indices", "barycentric")) for key in points_a)
    visibility_equal = all(points_a[key]["visible"] == points_b[key]["visible"] and points_a[key]["visibility_reason"] == points_b[key]["visibility_reason"] for key in points_a)
    mesh_equal = a["model"]["evaluated_local_vertices_float32_sha256"] == b["model"]["evaluated_local_vertices_float32_sha256"]
    return {
        "passed": mesh_equal and bindings_equal and visibility_equal and measurement_error <= 1e-9 and xyz_error <= 1e-8 and uv_error <= 1e-5,
        "mesh_hash_equal": mesh_equal,
        "bindings_equal": bindings_equal,
        "visibility_equal": visibility_equal,
        "max_measurement_error_m": measurement_error,
        "max_xyz_world_error_m": xyz_error,
        "max_uv_error_px": uv_error,
    }


def angle_degrees(a, b) -> float:
    left = np.asarray(a, dtype=float)
    right = np.asarray(b, dtype=float)
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    if denominator == 0:
        return 0.0
    return math.degrees(math.acos(float(np.clip(np.dot(left, right) / denominator, -1.0, 1.0))))


def draw_montage(items: list[tuple[str, Path]], output: Path, columns: int = 4, thumb=(320, 256)) -> None:
    rows = math.ceil(len(items) / columns)
    cell_h = thumb[1] + 28
    canvas = Image.new("RGB", (columns * thumb[0], rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for ordinal, (label, path) in enumerate(items):
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail(thumb, Image.Resampling.LANCZOS)
        x = (ordinal % columns) * thumb[0]
        y = (ordinal // columns) * cell_h
        canvas.paste(image, (x + (thumb[0] - image.width) // 2, y + 24))
        draw.text((x + 6, y + 6), label, fill="black", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def draw_bar_plot(rows: list[tuple[str, float]], title: str, unit: str, output: Path) -> None:
    width, height = 1400, max(520, 48 * len(rows) + 100)
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((20, 18), title, fill="black", font=font)
    max_value = max((abs(value) for _, value in rows), default=1.0) or 1.0
    origin = 520
    scale = 780 / max_value
    for index, (label, value) in enumerate(rows):
        y = 58 + index * 44
        draw.text((20, y + 8), label, fill="black", font=font)
        draw.line((origin, y, origin, y + 30), fill=(120, 120, 120), width=1)
        end = origin + value * scale
        color = (55, 135, 215) if value >= 0 else (225, 95, 75)
        draw.rectangle((min(origin, end), y + 4, max(origin, end), y + 25), fill=color)
        draw.text((max(origin, end) + 8, y + 8), f"{value:.3f} {unit}", fill="black", font=font)
    canvas.save(output)


def generate_visuals_and_reports(root: Path) -> None:
    baseline = read_json(root / "runs" / "A" / "probes" / "A_BASE.json")
    baseline_points = {item["point_id"]: item for item in baseline["points"]}
    case_rows = []
    csv_rows = []
    previews = [(case, root / "runs" / "A" / "samples" / case / "overlay.png") for case, _index, _value in case_definitions()]
    draw_montage(previews, root / "shape_montage.png", columns=4)
    for beta in range(10):
        neg = f"B{beta + 1:02d}_NEG"
        pos = f"B{beta + 1:02d}_POS"
        draw_montage([
            (neg, root / "runs" / "A" / "samples" / neg / "overlay.png"),
            ("A_BASE", root / "runs" / "A" / "samples" / "A_BASE" / "overlay.png"),
            (pos, root / "runs" / "A" / "samples" / pos / "overlay.png"),
        ], root / f"beta_{beta + 1:02d}_triplet.png", columns=3, thumb=(420, 336))

    region_map = {
        "neck_shoulder": {"GV14", "GB21", "SI15"},
        "upper_thoracic": {"BL13", "BL17", "GV9"},
        "mid_lower_thoracic": {"BL20", "GV6"},
        "lumbar": {"BL23", "BL25", "GV4"},
        "sacral": {"BL28"},
    }
    for case, beta_index, value in case_definitions():
        probe = read_json(root / "runs" / "A" / "probes" / f"{case}.json")
        point_details = []
        region_values = {name: [] for name in region_map}
        for point in probe["points"]:
            base = baseline_points[point["point_id"]]
            xyz_world_mm = math.dist(point["xyz_world_m"], base["xyz_world_m"]) * 1000
            xyz_camera_mm = math.dist(point["xyz_camera_opencv_m"], base["xyz_camera_opencv_m"]) * 1000
            uv_px = math.dist(point["uv_pixel_opencv"], base["uv_pixel_opencv"])
            normal_deg = angle_degrees(point["normal_world"], base["normal_world"])
            area_ratio = float(point["triangle_area_m2"]) / float(base["triangle_area_m2"])
            edge_change_mm = [
                (float(current) - float(original)) * 1000
                for current, original in zip(point["triangle_edge_lengths_m"], base["triangle_edge_lengths_m"])
            ]
            record = {
                "point_id": point["point_id"],
                "code": point["code"],
                "xyz_world_delta_mm": xyz_world_mm,
                "xyz_camera_delta_mm": xyz_camera_mm,
                "uv_delta_px": uv_px,
                "normal_angle_delta_deg": normal_deg,
                "triangle_area_ratio": area_ratio,
                "triangle_edge_length_change_mm": edge_change_mm,
                "visible": point["visible"],
                "visibility_reason": point["visibility_reason"],
            }
            point_details.append(record)
            for region, codes in region_map.items():
                if point["code"] in codes:
                    region_values[region].append(xyz_world_mm)
        measurement_delta = {name: (float(value_m) - float(baseline["measurements_m"][name])) * 1000 for name, value_m in probe["measurements_m"].items()}
        region_mean = {name: (sum(values) / len(values) if values else 0.0) for name, values in region_values.items()}
        ranked_measurements = sorted(measurement_delta.items(), key=lambda item: abs(item[1]), reverse=True)
        ranked_regions = sorted(region_mean.items(), key=lambda item: item[1], reverse=True)
        clearance = float(probe["bed"]["minimum_body_clearance_m"])
        status = "EXPECTED_FAIL_BED_INCOMPATIBLE" if case == "B02_NEG" and clearance < 0 else "PASS"
        case_record = {
            "case": case,
            "beta_index_zero_based": beta_index,
            "value": value,
            "status": status,
            "requested_betas": probe["requested_betas"],
            "effective_betas": probe["effective_betas"],
            "beta_control_chain_verified": probe["beta_control_chain_verified"],
            "measurements_m": probe["measurements_m"],
            "measurement_delta_mm": measurement_delta,
            "dominant_measurement_changes": ranked_measurements[:3],
            "region_mean_anchor_delta_mm": region_mean,
            "most_affected_regions": ranked_regions[:3],
            "max_anchor_xyz_delta_mm": max(item["xyz_world_delta_mm"] for item in point_details),
            "mean_anchor_xyz_delta_mm": sum(item["xyz_world_delta_mm"] for item in point_details) / len(point_details),
            "max_uv_delta_px": max(item["uv_delta_px"] for item in point_details),
            "max_normal_delta_deg": max(item["normal_angle_delta_deg"] for item in point_details),
            "bed_clearance_m": clearance,
            "penetration_depth_m": float(probe["bed"]["penetration_depth_m"]),
            "visibility_count": sum(bool(point["visible"]) for point in probe["points"]),
            "points": point_details,
        }
        case_rows.append(case_record)
        for point in point_details:
            csv_rows.append({"case": case, "beta_index": beta_index, "beta_value": value, "point_id": point["point_id"], "xyz_world_delta_mm": point["xyz_world_delta_mm"], "uv_delta_px": point["uv_delta_px"], "normal_delta_deg": point["normal_angle_delta_deg"], "triangle_area_ratio": point["triangle_area_ratio"], "bed_clearance_mm": clearance * 1000, "status": status})

    beta_summaries = []
    by_case = {item["case"]: item for item in case_rows}
    for beta in range(10):
        neg, pos = by_case[f"B{beta + 1:02d}_NEG"], by_case[f"B{beta + 1:02d}_POS"]
        combined = [(direction, name, delta) for direction, row in (("negative", neg), ("positive", pos)) for name, delta in row["measurement_delta_mm"].items()]
        dominant = sorted(combined, key=lambda item: abs(item[2]), reverse=True)[:5]
        affected = sorted({**neg["region_mean_anchor_delta_mm"], **pos["region_mean_anchor_delta_mm"]}, key=lambda region: max(neg["region_mean_anchor_delta_mm"][region], pos["region_mean_anchor_delta_mm"][region]), reverse=True)
        beta_summaries.append({
            "beta_index_zero_based": beta,
            "negative_case": neg["case"],
            "positive_case": pos["case"],
            "interpretation": "mixed principal shape component",
            "largest_measurement_effects": dominant,
            "most_affected_anchor_regions": affected[:3],
            "negative_status": neg["status"],
            "positive_status": pos["status"],
            "max_anchor_delta_mm": max(neg["max_anchor_xyz_delta_mm"], pos["max_anchor_xyz_delta_mm"]),
            "randomization_recommendation": "reject_negative_fixed_bed" if beta == 1 else "candidate_after_combination_validation",
        })

    report = {
        "schema": "enhanced-skel-shape-sensitivity-v1",
        "medical_truth": False,
        "truth_status": "engineering_reference",
        "baseline_case": "A_BASE",
        "beta_control_chain_verified_all": all(item["beta_control_chain_verified"] for item in case_rows),
        "case_count": len(case_rows),
        "cases": case_rows,
        "beta_summaries": beta_summaries,
        "terminology": "surface-anchor geometric sensitivity; never medical drift or acupoint error",
    }
    write_json(root / "shape_sensitivity_report.json", report)
    with (root / "shape_sensitivity.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)

    anchor_rows = [(item["case"], item["max_anchor_xyz_delta_mm"]) for item in case_rows if item["case"] != "A_BASE"]
    draw_bar_plot(anchor_rows, "Maximum 20-anchor geometric sensitivity", "mm", root / "beta_vs_anchor_displacement.png")
    for metric in ("body_longitudinal_length", "shoulder_width", "upper_torso_width", "lower_torso_width", "torso_thickness"):
        rows = [(item["case"], item["measurement_delta_mm"][metric]) for item in case_rows if item["case"] != "A_BASE"]
        draw_bar_plot(rows, f"Shape beta vs {metric}", "mm", root / f"beta_vs_{metric}.png")

    restore = read_json(root / "runs" / "A" / "probes" / "R_BASE.json")
    restore_compare = compare_probes(baseline, restore)
    buffer_compare = {name: {"baseline": sha256(root / "runs" / "A" / "samples" / "A_BASE" / name), "restored": sha256(root / "runs" / "A" / "samples" / "R_BASE" / name)} for name in ("rgb.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png")}
    for value in buffer_compare.values():
        value["equal"] = value["baseline"] == value["restored"]
    write_json(root / "baseline_restore_report.json", {"schema": "enhanced-shape-baseline-restore-v1", "passed": restore_compare["passed"] and all(value["equal"] for key, value in buffer_compare.items() if key != "rgb.png"), "geometry": restore_compare, "buffers": buffer_compare})

    # Candidate single-axis profiles only; combinations are intentionally not run here.
    valid_nonbase = [item for item in case_rows if item["case"] != "A_BASE" and item["status"] == "PASS"]
    chosen = []
    objectives = (
        ("body_longitudinal_length", 1),
        ("body_longitudinal_length", -1),
        ("shoulder_width", 1),
        ("shoulder_width", -1),
        ("torso_thickness", 1),
        ("upper_torso_width", 1),
    )
    for metric, direction in objectives:
        already = {item["case"] for item in chosen}
        ranked = sorted(
            (row for row in valid_nonbase if row["case"] not in already),
            key=lambda row: direction * row["measurement_delta_mm"][metric],
            reverse=True,
        )
        if ranked:
            chosen.append({"case": ranked[0]["case"], "selection_metric": metric, "selection_direction": "positive" if direction > 0 else "negative", "betas": ranked[0]["effective_betas"], "status": "candidate_not_validated_safe"})
    candidates = [{"case": "A_BASE", "selection_metric": "baseline", "betas": [0.0] * 10, "status": "candidate_not_validated_safe"}, *chosen[:6]]
    write_json(root / "candidate_shape_profiles.json", {"schema": "candidate-shape-profiles-v1", "medical_truth": False, "profiles": candidates, "next_required_stage": "CANDIDATE_SHAPE_COMBINATION_VALIDATION", "notice": "Single-axis evidence cannot validate multi-beta combinations."})

    determinism = read_json(root / "determinism_report.json")
    restore_report = read_json(root / "baseline_restore_report.json")
    expected_fail_ok = by_case["B02_NEG"]["status"] == "EXPECTED_FAIL_BED_INCOMPATIBLE"
    valid_case_qc = [read_json(root / "runs" / "A" / "qc" / f"{case}.json")["passed"] for case, _index, _value in case_definitions() if case != "B02_NEG"]
    visual_path = root / "visual_review.json"
    visual_review = read_json(visual_path) if visual_path.is_file() else {"passed": False, "status": "PENDING"}
    verification = {
        "schema": "enhanced-shape-only-verification-v1",
        "passed": report["beta_control_chain_verified_all"] and expected_fail_ok and all(valid_case_qc) and determinism["passed"] and restore_report["passed"] and visual_review.get("passed") is True,
        "configuration_count_processed": 21,
        "valid_rgbd_count": len(valid_case_qc),
        "expected_fail_count": 1,
        "expected_fail": "B02_NEG / beta_2=-0.5 / fixed-bed incompatible",
        "requested_effective_chain_verified": report["beta_control_chain_verified_all"],
        "determinism_passed": determinism["passed"],
        "baseline_restore_passed": restore_report["passed"],
        "valid_rgbd_qc_passed": all(valid_case_qc),
        "visual_self_intersection_review": visual_review,
        "source_inputs_unchanged": read_json(root / "source_hashes_before.json") == read_json(root / "source_hashes_after.json"),
        "limitations": [
            "Current 20 points are engineering references, not medical acupoints.",
            "No exact automated mesh self-intersection predicate is claimed; visual review remains required.",
            "Fixed rigid bed clearance is a scene compatibility result, not physiological plausibility.",
            "RGB and centre-ray Depth/Mask share geometry/camera/frame but are generated by different mechanisms.",
            "Visibility diversity remains future work; this controlled Shape-only stage does not add occluders.",
            "Candidate profiles are not validated safe multi-beta combinations.",
        ],
    }
    write_json(root / "verification.json", verification)
    write_readme(root, verification, report, candidates)
    manifest(root)


def write_readme(root: Path, verification: dict, report: dict, candidates: list[dict]) -> None:
    by_case = {item["case"]: item for item in report["cases"]}
    text = f"""# ENHANCED_SHAPE_ONLY_V1

自动结果：**{'PASS' if verification['passed'] else 'PENDING/FAIL'}**。本次不是首次 Shape smoke，而是在既有逐维 smoke 基础上，换用当前真实插件点击建立的20点 engineering-reference Atlas，完成增强 Shape 几何敏感性分析。

## 范围与状态

- 处理 21 个主配置：beta=0 baseline + 10维各自 ±0.5。
- 有效 RGB-D：{verification['valid_rgbd_count']} 个；`B02_NEG / beta_2=-0.5` 按预期记录为固定床面不兼容，不伪造 PASS。
- requested_betas → 原生 `parameters.json` effective_betas → Blender scene recorded_betas 三段一致：{verification['requested_effective_chain_verified']}。
- baseline 恢复：{verification['baseline_restore_passed']}；两个全新 Blender 运行确定性：{verification['determinism_passed']}。
- `beta_2=-0.5` 穿透：{by_case['B02_NEG']['penetration_depth_m']*1000:.3f} mm。它只证明当前 Shape + 固定刚体位置 + 刚性床面不兼容，不证明人体本身生理异常。

## 重要边界

当前20点不是医学穴位，`medical_truth=false / medical_validated=false`。本报告统一称“工程表面点几何敏感性”，不称医学漂移或穴位误差。尺寸是冻结身体局部坐标及固定顶点集得到的可重复工程代理，不是临床人体测量。

RGB 使用 Eevee 光栅，Depth/Mask 使用像素中心场景射线；它们共享同一场景、Camera、帧、分辨率与几何，但不声称每个轮廓像素属于相同 raster primitive。当前 Shape-only 没有增加遮挡变量，visibility diversity 仍待后续完成。

`candidate_shape_profiles.json` 只给出 {len(candidates)} 个候选单轴 Profile；不能称为 validated safe。下一步必须单独进行 Candidate Shape Combination Validation。本任务未启动 Pose-only、Shape×Pose、网络训练或大规模数据生成。

## 主要文件

- `shape_only_config_v1.json`：21配置和固定场景合同。
- `body_measurement_contract_v1.json`：身体局部坐标与冻结测量顶点集。
- `shape_sensitivity_report.json/.csv`：10维 beta、人体尺寸和20点敏感性。
- `shape_montage.png`、`beta_01_triplet.png` … `beta_10_triplet.png`：固定相机对比。
- `baseline_restore_report.json`、`determinism_report.json`、`verification.json`：恢复与确定性证据。
- `candidate_shape_profiles.json`：只供下一阶段组合验证。

## 不能证明

本实验不能证明医学穴位传播正确、真人泛化、真实 RGB-D 噪声、软组织/床垫接触、机器人坐标或接触安全。精确 Mesh 自穿插没有可靠自动谓词，需结合 triplet/montage 目视复核。
"""
    (root / "README.md").write_text(text, encoding="utf-8")


def manifest(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize", type=Path)
    args = parser.parse_args()
    if args.finalize:
        generate_visuals_and_reports(args.finalize.resolve())
        print(json.dumps({"finalized": True, "root": str(args.finalize.resolve())}, ensure_ascii=False))
    else:
        generate()
