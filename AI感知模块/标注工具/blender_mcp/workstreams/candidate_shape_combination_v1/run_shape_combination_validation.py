#!/usr/bin/env python3
"""Run CANDIDATE_SHAPE_COMBINATION_VALIDATION_V1 in isolated output roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


AI_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
TOOL_ROOT = AI_ROOT / "标注工具" / "blender_mcp"
WS = Path(__file__).resolve().parent
ENHANCED_WS = TOOL_ROOT / "workstreams" / "enhanced_shape_only_v1"
sys.path.insert(0, str(ENHANCED_WS))
import run_enhanced_shape_only as shared  # noqa: E402

OUTPUT_ROOT = AI_ROOT / "outputs" / "交付文件" / "2026-08-31_13-36-44" / "A_shape_combination"
SENSITIVITY_ROOT = AI_ROOT / "outputs" / "交付文件" / "2026-08-30_19-24-33"
SENSITIVITY_REPORT = SENSITIVITY_ROOT / "shape_sensitivity_report.json"
ATLAS = AI_ROOT / "outputs" / "交付文件" / "2026-08-29_16-21-55" / "source_atlas_v5.json"
F_ROOT = AI_ROOT / "outputs" / "交付文件" / "2026-08-31_13-36-44" / "F_qa"
MEASUREMENT_CONTRACT = F_ROOT / "body_measurement_contract_v2.json"
SELF_PROBE = TOOL_ROOT / "workstreams" / "qa_infrastructure_v1" / "self_intersection_probe.py"
DESIGN = WS / "design_combinations.py"
PROBE = WS / "probe_shape_combination_case.py"
LIGHT_FREEZE = WS / "freeze_scene_lights.py"
PARALLEL_ROOT = TOOL_ROOT / "workstreams" / "parallel_abc_f_v1"
BASELINE_MANIFEST = PARALLEL_ROOT / "baseline_manifest.json"
EXPECTED_TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"
BASELINE_GLOBAL_OVERLAPS = 293
MIN_CLEARANCE_M = 0.003


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sha_manifest(root: Path, expected_hash: str, expected_entries: int) -> dict:
    manifest = root / "SHA256SUMS.txt"
    lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if len(line) >= 66]
    missing, mismatch = [], []
    for line in lines:
        expected, relative = line.split("  ", 1)
        target = root / Path(relative)
        if not target.is_file():
            missing.append(relative)
        elif sha256(target) != expected.lower():
            mismatch.append(relative)
    result = {
        "root": str(root), "manifest_sha256": sha256(manifest),
        "expected_manifest_sha256": expected_hash, "entry_count": len(lines),
        "expected_entry_count": expected_entries, "missing": missing, "mismatch": mismatch,
    }
    result["passed"] = result["manifest_sha256"] == expected_hash and len(lines) == expected_entries and not missing and not mismatch
    return result


def verify_frozen_baselines() -> dict:
    manifest = read_json(BASELINE_MANIFEST)
    results = [verify_sha_manifest(Path(item["path"]), item["sha256sums_sha256"], int(item["sha256_entries"])) for item in manifest["sources"]]
    return {"schema": "a-line-frozen-baseline-verification-v1", "passed": all(item["passed"] for item in results), "sources": results}


def protected_hashes() -> dict:
    files = {
        "canonical_skel": shared.CANONICAL, "engineering_atlas": ATLAS,
        "sensitivity_report": SENSITIVITY_REPORT, "measurement_contract_v2": MEASUREMENT_CONTRACT,
        "self_intersection_probe": SELF_PROBE, "fixed_scene_contract": shared.CONTRACT_SCENE,
        "natural_prone_pose_profile": shared.PROFILE_BASE,
        "training_surface_binding": shared.CORE_PARENT / "training_export_core" / "surface_binding.py",
        "training_camera_geometry": shared.CORE_PARENT / "training_export_core" / "camera_geometry.py",
        "training_visibility": shared.CORE_PARENT / "training_export_core" / "visibility.py",
        "training_depth_raycast": shared.CORE_PARENT / "training_export_core" / "depth_raycast.py",
    }
    return {name: {"path": str(path), "sha256": sha256(path)} for name, path in files.items()}


def make_profile(base: dict, profile_id: str, betas: list[float]) -> dict:
    profile = json.loads(json.dumps(base))
    profile.update({
        "schema": "candidate-skel-shape-combination-profile-v1", "profile_id": profile_id,
        "medical_truth": False, "medical_validated": False,
        "betas": [float(value) for value in betas],
        "shape_test": {"kind": "multi_beta_combination", "nonzero_indices_zero_based": [index for index, value in enumerate(betas) if value != 0]},
    })
    return profile


def run_self_probe(snapshot: Path, output: Path) -> dict:
    command = [
        str(shared.BLENDER), "--background", str(snapshot), "--python", str(SELF_PROBE), "--",
        "--object", "SKEL-skin-female", "--output", str(output), "--epsilon", "1e-7",
        "--anchor-atlas", str(ATLAS), "--anchor-rings", "2", "--max-pairs", "20000",
    ]
    result = subprocess.run(command, cwd=str(TOOL_ROOT), env=shared.blender_env(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if result.returncode not in (0, 2) or not output.is_file():
        raise RuntimeError(f"self-intersection probe failed ({result.returncode})\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}")
    return read_json(output)


def generate_case(root: Path, temporary: Path, run_id: str, profile_id: str, betas: list[float], fixture_path: Path, *, run_group: str = "runs", light_contract: Path | None = None) -> dict:
    run_root = root / run_group / run_id
    for name in ("profiles", "snapshots", "probes", "samples", "prepare", "export", "qc", "self_intersection"):
        (run_root / name).mkdir(parents=True, exist_ok=True)
    profile = make_profile(read_json(shared.PROFILE_BASE), profile_id, betas)
    profile_path = run_root / "profiles" / f"{profile_id}.json"
    write_json(profile_path, profile)
    native = temporary / run_id / profile_id / "native"
    native.parent.mkdir(parents=True, exist_ok=True)
    shared.run([sys.executable, str(shared.GENERATE), "--profile", str(profile_path), "--output", str(native)])
    snapshot = run_root / "snapshots" / f"{profile_id}.blend"
    shared.bj(shared.CANONICAL, shared.PREPARE, [
        "--snapshot", snapshot, "--result", run_root / "prepare" / f"{profile_id}.json",
        "--native-pose-dir", native, "--pose-profile", profile_path,
        "--fixed-scene-contract", shared.CONTRACT_SCENE, "--width", 1280, "--height", 1024,
    ], "ACU_PREPARE_PRONE_SCENE=PASS")
    if light_contract is not None:
        shared.bj(snapshot, LIGHT_FREEZE, ["--apply", light_contract, "--save", snapshot], "ACU_FIXED_SCENE_LIGHTS=PASS")
    probe_path = run_root / "probes" / f"{profile_id}.json"
    shared.bj(snapshot, PROBE, [
        "--atlas", ATLAS, "--contract", MEASUREMENT_CONTRACT,
        "--profile", profile_path, "--native-parameters", native / "parameters.json",
        "--core-parent", shared.CORE_PARENT, "--output", probe_path, "--width", 1280, "--height", 1024,
    ], "ACU_SHAPE_COMBINATION_PROBE=PASS")
    probe = read_json(probe_path)
    self_report_path = run_root / "self_intersection" / f"{profile_id}.json"
    self_report = run_self_probe(snapshot, self_report_path)
    sample = run_root / "samples" / profile_id
    shared.bj(snapshot, shared.EXPORT, [
        "--fixture", fixture_path, "--output", sample,
        "--result", run_root / "export" / f"{profile_id}.json", "--width", 1280, "--height", 1024,
    ], "ACU_EXPORT_PRONE_SAMPLE=PASS")
    shared.overlay_from_probe(sample / "rgb.png", probe, sample / "overlay.png")
    qc = shared.strict_sample_qc(sample, read_json(fixture_path), [float(value) for value in betas])
    write_json(run_root / "qc" / f"{profile_id}.json", qc)
    return {"profile_id": profile_id, "betas": betas, "probe": probe, "probe_path": probe_path, "snapshot": snapshot, "sample": sample, "qc": qc, "self_intersection": self_report, "self_intersection_path": self_report_path}


def matrix_max_abs_error(left, right) -> float:
    return float(np.max(np.abs(np.asarray(left, dtype=float) - np.asarray(right, dtype=float))))


def scene_invariant_comparison(base: dict, current: dict, tolerance: float = 1e-6) -> dict:
    """Compare controls, excluding expected shape-dependent geometry fields."""
    base_lights = {item["name"]: item for item in base["scene_invariants"]["lights"]}
    current_lights = {item["name"]: item for item in current["scene_invariants"]["lights"]}
    light_names_equal = set(base_lights) == set(current_lights)
    light_details = {}
    if light_names_equal:
        for name in sorted(base_lights):
            left, right = base_lights[name], current_lights[name]
            error = matrix_max_abs_error(left["matrix_world"], right["matrix_world"])
            exact_fields = all(left[key] == right[key] for key in ("name", "type", "energy", "color"))
            light_details[name] = {"exact_object_and_data_fields": exact_fields, "matrix_max_abs_error": error, "passed": exact_fields and error <= tolerance}
    camera_error = matrix_max_abs_error(base["camera"]["matrix_world"], current["camera"]["matrix_world"])
    bed_error = matrix_max_abs_error(base["bed"]["matrix_world"], current["bed"]["matrix_world"])
    target_error = matrix_max_abs_error(base["model"]["matrix_world"], current["model"]["matrix_world"])
    exact_checks = {
        "pose_degrees": base["pose_degrees"] == current["pose_degrees"],
        "frame": base["scene_invariants"]["frame"] == current["scene_invariants"]["frame"],
        "unit_scale_length": base["scene_invariants"]["unit_scale_length"] == current["scene_invariants"]["unit_scale_length"],
        "render_engine": base["scene_invariants"]["render_engine"] == current["scene_invariants"]["render_engine"],
        "camera_identity_and_resolution": base["camera"]["name"] == current["camera"]["name"] and base["camera"]["resolution"] == current["camera"]["resolution"],
        "bed_identity_and_top_z": base["bed"]["name"] == current["bed"]["name"] and base["bed"]["top_z_m"] == current["bed"]["top_z_m"],
        "target_identity": base["model"]["object_name"] == current["model"]["object_name"],
        "light_names": light_names_equal,
    }
    matrix_checks = {"camera": camera_error <= tolerance, "bed": bed_error <= tolerance, "target_rigid_transform": target_error <= tolerance, "lights": light_names_equal and all(item["passed"] for item in light_details.values())}
    return {
        "passed": all(exact_checks.values()) and all(matrix_checks.values()),
        "matrix_absolute_tolerance": tolerance,
        "exact_checks": exact_checks, "matrix_checks": matrix_checks,
        "matrix_max_abs_error": {"camera": camera_error, "bed": bed_error, "target_rigid_transform": target_error, "lights": max((item["matrix_max_abs_error"] for item in light_details.values()), default=0.0)},
        "lights": light_details,
        "excluded_as_shape_dependent": ["bed.minimum_body_clearance_m", "bed.penetration_depth_m", "model.bounds_*", "model.evaluated_local_vertices_float32_sha256"],
    }


def scene_invariants_equal(base: dict, current: dict) -> bool:
    return scene_invariant_comparison(base, current)["passed"]


def overlap_delta(base: dict, current: dict) -> dict:
    base_pairs = {tuple(pair) for pair in base["nonadjacent_intersection_pairs_truncated"]}
    current_pairs = {tuple(pair) for pair in current["nonadjacent_intersection_pairs_truncated"]}
    complete = not base["pair_list_truncated"] and not current["pair_list_truncated"]
    return {
        "complete_pair_lists": complete,
        "baseline_global_count": base["nonadjacent_intersection_pair_count"],
        "current_global_count": current["nonadjacent_intersection_pair_count"],
        "count_delta": current["nonadjacent_intersection_pair_count"] - base["nonadjacent_intersection_pair_count"],
        "new_global_pairs": [list(pair) for pair in sorted(current_pairs - base_pairs)] if complete else None,
        "removed_global_pairs": [list(pair) for pair in sorted(base_pairs - current_pairs)] if complete else None,
    }


def case_gate(base_probe: dict, base_self: dict, case: dict) -> dict:
    probe, self_report, qc = case["probe"], case["self_intersection"], case["qc"]
    expected_bindings = {(point["point_id"], point["face_index"], tuple(point["vertex_indices"]), tuple(point["barycentric"])) for point in base_probe["points"]}
    actual_bindings = {(point["point_id"], point["face_index"], tuple(point["vertex_indices"]), tuple(point["barycentric"])) for point in probe["points"]}
    scene_comparison = scene_invariant_comparison(base_probe, probe)
    checks = {
        "requested_effective_scene_betas_equal": probe["beta_control_chain_verified"] and probe["requested_betas"] == case["betas"],
        "topology_frozen": probe["model"]["topology_signature_sha256"] == EXPECTED_TOPOLOGY and probe["model"]["vertex_count"] == 6890 and probe["model"]["face_count"] == 13776,
        "surface_bindings_frozen": actual_bindings == expected_bindings,
        "pose_camera_bed_light_frozen": scene_comparison["passed"],
        "minimum_fixed_bed_clearance_3mm": float(probe["bed"]["minimum_body_clearance_m"]) >= MIN_CLEARANCE_M,
        "rgbd_depth_backprojection_visibility_qc": bool(qc["passed"]) and int(qc["visible_count"]) == 20,
        "anchor_two_ring_overlap_clear": bool(self_report["passed"]) and int(self_report["anchor_scope"]["overlap_pair_count"]) == 0,
        "global_overlap_pair_list_complete": not bool(self_report["pair_list_truncated"]),
        "baseline_calibration_matches_293": int(base_self["nonadjacent_intersection_pair_count"]) == BASELINE_GLOBAL_OVERLAPS,
    }
    return {"passed": all(checks.values()), "checks": checks, "scene_invariant_comparison": scene_comparison, "global_overlap_comparison": overlap_delta(base_self, self_report)}


def buffer_comparison(left: Path, right: Path) -> dict:
    result = {}
    for name in ("rgb.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png"):
        a, b = sha256(left / name), sha256(right / name)
        result[name] = {"run_a": a, "run_b": b, "equal": a == b, "required_equal": name != "rgb.png"}
    return result


def choose_qualified(validated: list[dict], baseline: dict, limit: int = 6) -> list[dict]:
    metrics = list(baseline["probe"]["measurements_m"])
    base = np.asarray([baseline["probe"]["measurements_m"][metric] for metric in metrics], dtype=float)
    vectors = {}
    for item in validated:
        vectors[item["profile_id"]] = (np.asarray([item["probe"]["measurements_m"][metric] for metric in metrics], dtype=float) - base) * 1000.0
    scales = np.maximum(np.max(np.abs(np.stack(list(vectors.values()))), axis=0), 1e-9)
    chosen: list[dict] = []
    remaining = list(validated)
    while remaining and len(chosen) < limit:
        if not chosen:
            selected = max(remaining, key=lambda item: float(np.linalg.norm(vectors[item["profile_id"]] / scales)))
        else:
            selected = max(remaining, key=lambda item: min(float(np.linalg.norm((vectors[item["profile_id"]] - vectors[other["profile_id"]]) / scales)) for other in chosen))
        chosen.append(selected)
        remaining.remove(selected)
    return chosen


def draw_montage(items: list[tuple[str, Path]], output: Path) -> None:
    columns, thumb = 3, (420, 336)
    rows = math.ceil(len(items) / columns)
    canvas = Image.new("RGB", (columns * thumb[0], rows * (thumb[1] + 30)), "white")
    draw, font = ImageDraw.Draw(canvas), ImageFont.load_default()
    for ordinal, (label, path) in enumerate(items):
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail(thumb, Image.Resampling.LANCZOS)
        x, y = ordinal % columns * thumb[0], ordinal // columns * (thumb[1] + 30)
        canvas.paste(image, (x + (thumb[0] - image.width) // 2, y + 28))
        draw.text((x + 6, y + 7), label, fill="black", font=font)
    canvas.save(output)


def manifest(root: Path) -> None:
    top_level_manifest = root / "SHA256SUMS.txt"
    rows = [f"{sha256(path)}  {path.relative_to(root).as_posix()}" for path in sorted(item for item in root.rglob("*") if item.is_file() and item != top_level_manifest)]
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def finalize(root: Path) -> None:
    run_results = read_json(root / "run_results.json")
    restore = read_json(root / "baseline_restore_report.json")
    determinism = read_json(root / "determinism_report.json")
    visual = read_json(root / "visual_review.json") if (root / "visual_review.json").is_file() else {"passed": False, "status": "PENDING"}
    valid = [item for item in run_results["candidates"] if item["gate"]["passed"] and determinism["by_profile"][item["profile_id"]]["passed"]]
    qualified = choose_qualified(valid, run_results["baseline"], limit=6) if valid else []
    profiles = [{"profile_id": "S0_BASE", "betas": [0.0] * 10, "qualification": "FIXED_PRONE_ONLY"}] + [
        {"profile_id": item["profile_id"], "betas": item["betas"], "qualification": "FIXED_PRONE_ONLY", "bed_clearance_m": item["probe"]["bed"]["minimum_body_clearance_m"], "global_overlap_count": item["self_intersection"]["nonadjacent_intersection_pair_count"], "anchor_two_ring_overlap_count": item["self_intersection"]["anchor_scope"]["overlap_pair_count"]}
        for item in qualified
    ]
    qualification = {
        "schema": "QUALIFIED_SHAPE_PROFILES_FIXED_PRONE_V1", "medical_truth": False,
        "scope": "fixed natural-prone pose/camera/rigid-bed/light/engineering-Atlas only",
        "profiles": profiles,
        "global_mesh_notice": "Baseline and candidates contain known global nonadjacent triangle overlaps outside the 20-anchor 2-ring neighborhood; no global self-intersection-free claim is made.",
        "next_required_gate": "ENHANCED_POSE_ONLY_V1 then a separately authorized Shape x Pose cross-product validation",
    }
    write_json(root / "QUALIFIED_SHAPE_PROFILES_FIXED_PRONE_V1.json", qualification)
    passed = len(profiles) in range(5, 8) and restore["passed"] and determinism["passed"] and visual.get("passed") is True and run_results["source_inputs_unchanged"] and run_results["baseline_verification"]["passed"]
    verification = {
        "schema": "candidate-shape-combination-verification-v1", "passed": passed,
        "designed_combination_count": len(run_results["candidates"]),
        "candidate_gate_pass_count": len(valid), "qualified_profile_count_including_baseline": len(profiles),
        "baseline_restore_passed": restore["passed"], "two_fresh_process_determinism_passed": determinism["passed"],
        "visual_review": visual, "source_inputs_unchanged": run_results["source_inputs_unchanged"],
        "baseline_manifests_verified": run_results["baseline_verification"]["passed"],
        "truth_status": {"medical_truth": False, "medical_validated": False, "kind": "engineering_reference"},
        "limitations": [
            "Qualification is limited to the frozen prone pose/camera/rigid-bed/light contract.",
            "The baseline has 293 known global nonadjacent triangle overlaps; only the 20-anchor 2-ring neighborhood is a zero-overlap hard gate.",
            "No medical propagation, physiological plausibility, real RGB-D, soft-bed contact, generalization, or robot safety claim is made.",
            "RGB exact hashes are reported but not required because current Eevee RGB is stochastic; geometry, Depth and masks are required deterministic.",
        ],
    }
    write_json(root / "verification.json", verification)
    lines = [
        "# CANDIDATE_SHAPE_COMBINATION_VALIDATION_V1", "",
        f"结果：**{'PASS' if passed else 'PENDING/FAIL'}**。设计8个真正多 beta 组合，组合硬门通过 {len(valid)}/8，最终冻结 {len(profiles)} 个仅限固定俯卧场景的 Shape profiles（含 baseline）。", "",
        "## 结论边界", "",
        "- 只有 `QUALIFIED_SHAPE_PROFILES_FIXED_PRONE_V1`；不是全局安全体型。",
        "- 20点是 engineering reference，不是医学穴位。",
        "- 基线全身有293对既有非邻接三角形重叠；硬门只要求20点二环邻域为0，不声称全身无自交。",
        "- 本线没有进入 Pose、Shape×Pose、训练或大数据。", "",
        "## 主要文件", "",
        "- `combination_design_v1.json`：局部线性敏感性矩阵、受限枚举和8个候选。",
        "- `combination_validation_report.json`：非线性 Blender 实测与每项硬门。",
        "- `QUALIFIED_SHAPE_PROFILES_FIXED_PRONE_V1.json`：下一阶段唯一 Shape 集合。",
        "- `baseline_restore_report.json` / `determinism_report.json` / `verification.json`：恢复、两新进程与总验收。",
    ]
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest(root)


def execute(root: Path) -> None:
    required = [shared.BLENDER, shared.CANONICAL, ATLAS, SENSITIVITY_REPORT, MEASUREMENT_CONTRACT, SELF_PROBE, DESIGN, PROBE, shared.GENERATE, shared.PREPARE, shared.EXPORT]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise RuntimeError(f"A output directory must be empty: {root}")
    baseline_verification = verify_frozen_baselines()
    if not baseline_verification["passed"]:
        raise RuntimeError("frozen baseline manifest verification failed")
    write_json(root / "baseline_verification.json", baseline_verification)
    hashes_before = protected_hashes()
    write_json(root / "source_hashes_before.json", hashes_before)
    shutil.copy2(ATLAS, root / "source_atlas_v5.json")
    shutil.copy2(MEASUREMENT_CONTRACT, root / "body_measurement_contract_v2.json")
    fixture_path = root / "engineering_fixture_manual20.json"
    write_json(fixture_path, shared.make_fixture(read_json(ATLAS)))
    design_path = root / "combination_design_v1.json"
    shared.run([sys.executable, str(DESIGN), "--report", str(SENSITIVITY_REPORT), "--output", str(design_path)])
    design = read_json(design_path)
    profiles = [("A_BASE", [0.0] * 10)] + [(item["profile_id"], item["betas"]) for item in design["candidates"]]

    with tempfile.TemporaryDirectory(prefix="acu_shape_combo_") as temporary_name:
        temporary = Path(temporary_name)
        run_a = []
        for ordinal, (profile_id, betas) in enumerate(profiles, start=1):
            case = generate_case(root, temporary, "A", profile_id, betas, fixture_path)
            run_a.append(case)
            write_json(root / "progress.json", {"phase": "run_A", "completed": ordinal, "total": len(profiles)})
            print(f"A {ordinal}/{len(profiles)} {profile_id}", flush=True)
        baseline = run_a[0]
        if baseline["self_intersection"]["nonadjacent_intersection_pair_count"] != BASELINE_GLOBAL_OVERLAPS:
            raise RuntimeError("F baseline global-overlap calibration no longer matches 293")
        candidates = []
        for case in run_a[1:]:
            gate = case_gate(baseline["probe"], baseline["self_intersection"], case)
            case["gate"] = gate
            candidates.append(case)

        restore = generate_case(root, temporary, "A", "R_BASE", [0.0] * 10, fixture_path)
        restore_geometry = shared.compare_probes(baseline["probe"], restore["probe"])
        restore_buffers = buffer_comparison(baseline["sample"], restore["sample"])
        restore_self_equal = overlap_delta(baseline["self_intersection"], restore["self_intersection"])
        restore_passed = restore_geometry["passed"] and restore["qc"]["passed"] and all(item["equal"] for item in restore_buffers.values() if item["required_equal"]) and restore_self_equal["count_delta"] == 0 and not restore_self_equal["new_global_pairs"] and not restore_self_equal["removed_global_pairs"]
        write_json(root / "baseline_restore_report.json", {"schema": "shape-combination-baseline-restore-v1", "passed": restore_passed, "geometry": restore_geometry, "buffers": restore_buffers, "self_intersection": restore_self_equal})

        run_b = []
        determinism_by_profile = {}
        for ordinal, (profile_id, betas) in enumerate(profiles, start=1):
            case_b = generate_case(root, temporary, "B", profile_id, betas, fixture_path)
            case_a = next(item for item in run_a if item["profile_id"] == profile_id)
            geometry = shared.compare_probes(case_a["probe"], case_b["probe"])
            buffers = buffer_comparison(case_a["sample"], case_b["sample"])
            self_delta = overlap_delta(case_a["self_intersection"], case_b["self_intersection"])
            passed = geometry["passed"] and case_b["qc"]["passed"] and all(item["equal"] for item in buffers.values() if item["required_equal"]) and self_delta["count_delta"] == 0 and not self_delta["new_global_pairs"] and not self_delta["removed_global_pairs"]
            determinism_by_profile[profile_id] = {"passed": passed, "geometry": geometry, "buffers": buffers, "self_intersection": self_delta}
            run_b.append(case_b)
            write_json(root / "progress.json", {"phase": "run_B", "completed": ordinal, "total": len(profiles)})
            print(f"B {ordinal}/{len(profiles)} {profile_id}: {'PASS' if passed else 'FAIL'}", flush=True)

    hashes_after = protected_hashes()
    write_json(root / "source_hashes_after.json", hashes_after)
    source_unchanged = hashes_before == hashes_after
    write_json(root / "determinism_report.json", {"schema": "shape-combination-determinism-v1", "passed": all(item["passed"] for item in determinism_by_profile.values()), "fresh_native_generation_and_blender_processes": True, "rgb_exact_hash_reported_not_required": True, "by_profile": determinism_by_profile})

    def compact(case: dict) -> dict:
        return {
            "profile_id": case["profile_id"], "betas": case["betas"], "probe": case["probe"],
            "qc": case["qc"], "self_intersection": case["self_intersection"],
            "gate": case.get("gate"), "sample": str(case["sample"].relative_to(root)),
            "snapshot": str(case["snapshot"].relative_to(root)),
        }

    payload = {
        "schema": "candidate-shape-combination-run-results-v1", "medical_truth": False,
        "baseline_verification": baseline_verification, "source_inputs_unchanged": source_unchanged,
        "baseline": compact(baseline), "candidates": [compact(item) for item in candidates],
        "restore": compact(restore),
    }
    write_json(root / "run_results.json", payload)
    write_json(root / "combination_validation_report.json", {
        "schema": "candidate-shape-combination-validation-report-v1", "medical_truth": False,
        "baseline_global_overlap_count": BASELINE_GLOBAL_OVERLAPS,
        "hard_gate": "20 engineering-anchor 2-ring overlap count must be zero",
        "global_mesh_claim": "known global overlaps recorded; no globally self-intersection-free claim",
        "candidates": [{"profile_id": item["profile_id"], "betas": item["betas"], "gate": item["gate"], "bed_clearance_m": item["probe"]["bed"]["minimum_body_clearance_m"], "measurements_m": item["probe"]["measurements_m"], "visible_count": item["qc"]["visible_count"], "max_depth_error_m": item["qc"]["max_depth_error_m"], "max_backprojection_error_m": item["qc"]["max_backprojection_error_m"], "self_intersection_status": item["self_intersection"]["status"]} for item in candidates],
    })
    draw_montage([(item["profile_id"], item["sample"] / "overlay.png") for item in run_a], root / "shape_combination_montage.png")
    write_json(root / "visual_review.json", {"passed": False, "status": "PENDING_MANUAL_REVIEW", "notice": "Inspect fixed-camera montage before finalization."})
    finalize(root)


def execute_fixed_lights(root: Path) -> None:
    """Preserve the first diagnostic attempt and rerun with frozen baseline lights."""
    if not (root / "run_results.json").is_file():
        raise RuntimeError("the diagnostic first attempt is required before fixed-light rerun")
    fixed_runs = root / "runs_fixed_lights"
    if fixed_runs.exists():
        raise RuntimeError(f"fixed-light run already exists: {fixed_runs}")
    diagnostics = root / "diagnostics" / "attempt_1_body_dependent_fill_light"
    diagnostics.mkdir(parents=True, exist_ok=False)
    for name in (
        "run_results.json", "combination_validation_report.json", "baseline_restore_report.json",
        "determinism_report.json", "verification.json", "QUALIFIED_SHAPE_PROFILES_FIXED_PRONE_V1.json",
        "README.md", "visual_review.json", "shape_combination_montage.png", "SHA256SUMS.txt",
    ):
        source = root / name
        if source.is_file():
            shutil.copy2(source, diagnostics / name)
    write_json(diagnostics / "DIAGNOSTIC_DO_NOT_USE_AS_FINAL.json", {
        "status": "DIAGNOSTIC_REJECTED_CONTROL_VARIABLE_VIOLATION",
        "reason": "prepare_prone_scene positioned ACU_PRONE_FILL from per-shape body_max.y, so Light was not fixed",
        "retained_for_audit": True,
    })

    baseline_verification = verify_frozen_baselines()
    if not baseline_verification["passed"]:
        raise RuntimeError("frozen baseline manifest verification failed before fixed-light rerun")
    hashes_before = protected_hashes()
    design = read_json(root / "combination_design_v1.json")
    fixture_path = root / "engineering_fixture_manual20.json"
    profiles = [("A_BASE", [0.0] * 10)] + [(item["profile_id"], item["betas"]) for item in design["candidates"]]
    light_contract = root / "fixed_prone_light_contract_v1.json"

    with tempfile.TemporaryDirectory(prefix="acu_shape_combo_fixed_light_") as temporary_name:
        temporary = Path(temporary_name)
        baseline = generate_case(root, temporary, "A", "A_BASE", [0.0] * 10, fixture_path, run_group="runs_fixed_lights")
        shared.bj(baseline["snapshot"], LIGHT_FREEZE, ["--capture", light_contract], "ACU_FIXED_SCENE_LIGHTS=PASS")
        run_a = [baseline]
        for ordinal, (profile_id, betas) in enumerate(profiles[1:], start=2):
            case = generate_case(root, temporary, "A", profile_id, betas, fixture_path, run_group="runs_fixed_lights", light_contract=light_contract)
            run_a.append(case)
            write_json(root / "progress_fixed_lights.json", {"phase": "run_A", "completed": ordinal, "total": len(profiles)})
            print(f"FIXED A {ordinal}/{len(profiles)} {profile_id}", flush=True)
        if baseline["self_intersection"]["nonadjacent_intersection_pair_count"] != BASELINE_GLOBAL_OVERLAPS:
            raise RuntimeError("F baseline global-overlap calibration no longer matches 293")
        candidates = []
        for case in run_a[1:]:
            case["gate"] = case_gate(baseline["probe"], baseline["self_intersection"], case)
            candidates.append(case)

        restore = generate_case(root, temporary, "A", "R_BASE", [0.0] * 10, fixture_path, run_group="runs_fixed_lights", light_contract=light_contract)
        restore_geometry = shared.compare_probes(baseline["probe"], restore["probe"])
        restore_buffers = buffer_comparison(baseline["sample"], restore["sample"])
        restore_self = overlap_delta(baseline["self_intersection"], restore["self_intersection"])
        restore_passed = restore_geometry["passed"] and restore["qc"]["passed"] and all(item["equal"] for item in restore_buffers.values() if item["required_equal"]) and restore_self["count_delta"] == 0 and not restore_self["new_global_pairs"] and not restore_self["removed_global_pairs"] and scene_invariants_equal(baseline["probe"], restore["probe"])
        write_json(root / "baseline_restore_report.json", {"schema": "shape-combination-baseline-restore-v1", "passed": restore_passed, "geometry": restore_geometry, "buffers": restore_buffers, "self_intersection": restore_self, "scene_invariants_equal": scene_invariants_equal(baseline["probe"], restore["probe"])})

        determinism_by_profile = {}
        for ordinal, (profile_id, betas) in enumerate(profiles, start=1):
            case_b = generate_case(root, temporary, "B", profile_id, betas, fixture_path, run_group="runs_fixed_lights", light_contract=light_contract)
            case_a = next(item for item in run_a if item["profile_id"] == profile_id)
            geometry = shared.compare_probes(case_a["probe"], case_b["probe"])
            buffers = buffer_comparison(case_a["sample"], case_b["sample"])
            self_delta = overlap_delta(case_a["self_intersection"], case_b["self_intersection"])
            scene_equal = scene_invariants_equal(case_a["probe"], case_b["probe"])
            passed = geometry["passed"] and case_b["qc"]["passed"] and scene_equal and all(item["equal"] for item in buffers.values() if item["required_equal"]) and self_delta["count_delta"] == 0 and not self_delta["new_global_pairs"] and not self_delta["removed_global_pairs"]
            determinism_by_profile[profile_id] = {"passed": passed, "geometry": geometry, "buffers": buffers, "self_intersection": self_delta, "scene_invariants_equal": scene_equal}
            write_json(root / "progress_fixed_lights.json", {"phase": "run_B", "completed": ordinal, "total": len(profiles)})
            print(f"FIXED B {ordinal}/{len(profiles)} {profile_id}: {'PASS' if passed else 'FAIL'}", flush=True)

    hashes_after = protected_hashes()
    source_unchanged = hashes_before == hashes_after
    write_json(root / "source_hashes_fixed_lights_before.json", hashes_before)
    write_json(root / "source_hashes_fixed_lights_after.json", hashes_after)
    write_json(root / "determinism_report.json", {"schema": "shape-combination-determinism-v1", "passed": all(item["passed"] for item in determinism_by_profile.values()), "fresh_native_generation_and_blender_processes": True, "rgb_exact_hash_reported_not_required": True, "fixed_light_contract_sha256": sha256(light_contract), "by_profile": determinism_by_profile})

    def compact(case: dict) -> dict:
        return {"profile_id": case["profile_id"], "betas": case["betas"], "probe": case["probe"], "qc": case["qc"], "self_intersection": case["self_intersection"], "gate": case.get("gate"), "sample": str(case["sample"].relative_to(root)), "snapshot": str(case["snapshot"].relative_to(root))}

    payload = {"schema": "candidate-shape-combination-run-results-v1", "medical_truth": False, "attempt": "fixed_baseline_light_contract", "baseline_verification": baseline_verification, "source_inputs_unchanged": source_unchanged, "baseline": compact(baseline), "candidates": [compact(item) for item in candidates], "restore": compact(restore)}
    write_json(root / "run_results.json", payload)
    write_json(root / "combination_validation_report.json", {
        "schema": "candidate-shape-combination-validation-report-v1", "medical_truth": False,
        "baseline_global_overlap_count": BASELINE_GLOBAL_OVERLAPS,
        "hard_gate": "20 engineering-anchor 2-ring overlap count must be zero",
        "global_mesh_claim": "known global overlaps recorded; no globally self-intersection-free claim",
        "fixed_light_contract_sha256": sha256(light_contract),
        "candidates": [{"profile_id": item["profile_id"], "betas": item["betas"], "gate": item["gate"], "bed_clearance_m": item["probe"]["bed"]["minimum_body_clearance_m"], "measurements_m": item["probe"]["measurements_m"], "visible_count": item["qc"]["visible_count"], "max_depth_error_m": item["qc"]["max_depth_error_m"], "max_backprojection_error_m": item["qc"]["max_backprojection_error_m"], "self_intersection_status": item["self_intersection"]["status"]} for item in candidates],
    })
    draw_montage([(item["profile_id"], item["sample"] / "overlay.png") for item in run_a], root / "shape_combination_montage.png")
    write_json(root / "visual_review.json", {"passed": False, "status": "PENDING_MANUAL_REVIEW", "notice": "Inspect fixed-light montage before finalization."})
    finalize(root)


def rejudge_fixed_light_runs(root: Path) -> None:
    """Repair the exact-float comparator mistake without regenerating scenes."""
    diagnostic = root / "diagnostics" / "attempt_2_exact_float_scene_comparator"
    diagnostic.mkdir(parents=True, exist_ok=False)
    for name in ("run_results.json", "combination_validation_report.json", "baseline_restore_report.json", "determinism_report.json", "verification.json", "QUALIFIED_SHAPE_PROFILES_FIXED_PRONE_V1.json", "README.md", "visual_review.json", "SHA256SUMS.txt"):
        source = root / name
        if source.is_file():
            shutil.copy2(source, diagnostic / name)
    write_json(diagnostic / "DIAGNOSTIC_DO_NOT_USE_AS_FINAL.json", {
        "status": "DIAGNOSTIC_REJECTED_COMPARATOR_BUG",
        "reason": "The first fixed-light adjudication used exact dict equality and incorrectly rejected harmless <=1e-7 Blender matrix reconstruction noise; it also compared shape-dependent fields indirectly.",
        "scenes_and_buffers_regenerated": False,
    })

    results = read_json(root / "run_results.json")
    baseline, candidates, restore = results["baseline"], results["candidates"], results["restore"]
    for case in candidates:
        case["gate"] = case_gate(baseline["probe"], baseline["self_intersection"], case)
    results["candidates"] = candidates
    results["adjudication"] = "matrix controls compared with explicit absolute tolerance <=1e-6; shape-dependent geometry excluded"
    write_json(root / "run_results.json", results)

    group = root / "runs_fixed_lights"
    profile_ids = ["A_BASE"] + [item["profile_id"] for item in candidates]
    determinism_by_profile = {}
    for profile_id in profile_ids:
        probe_a = read_json(group / "A" / "probes" / f"{profile_id}.json")
        probe_b = read_json(group / "B" / "probes" / f"{profile_id}.json")
        sample_a, sample_b = group / "A" / "samples" / profile_id, group / "B" / "samples" / profile_id
        geometry = shared.compare_probes(probe_a, probe_b)
        buffers = buffer_comparison(sample_a, sample_b)
        self_a = read_json(group / "A" / "self_intersection" / f"{profile_id}.json")
        self_b = read_json(group / "B" / "self_intersection" / f"{profile_id}.json")
        self_delta = overlap_delta(self_a, self_b)
        scene_comparison = scene_invariant_comparison(probe_a, probe_b)
        qc_b = read_json(group / "B" / "qc" / f"{profile_id}.json")
        passed = geometry["passed"] and qc_b["passed"] and scene_comparison["passed"] and all(item["equal"] for item in buffers.values() if item["required_equal"]) and self_delta["count_delta"] == 0 and not self_delta["new_global_pairs"] and not self_delta["removed_global_pairs"]
        determinism_by_profile[profile_id] = {"passed": passed, "geometry": geometry, "buffers": buffers, "self_intersection": self_delta, "scene_invariant_comparison": scene_comparison}
    write_json(root / "determinism_report.json", {"schema": "shape-combination-determinism-v1", "passed": all(item["passed"] for item in determinism_by_profile.values()), "fresh_native_generation_and_blender_processes": True, "rgb_exact_hash_reported_not_required": True, "matrix_absolute_tolerance": 1e-6, "by_profile": determinism_by_profile})

    base_probe, restore_probe = baseline["probe"], restore["probe"]
    restore_geometry = shared.compare_probes(base_probe, restore_probe)
    restore_buffers = buffer_comparison(root / baseline["sample"], root / restore["sample"])
    restore_self = overlap_delta(baseline["self_intersection"], restore["self_intersection"])
    restore_scene = scene_invariant_comparison(base_probe, restore_probe)
    restore_passed = restore_geometry["passed"] and restore["qc"]["passed"] and restore_scene["passed"] and all(item["equal"] for item in restore_buffers.values() if item["required_equal"]) and restore_self["count_delta"] == 0 and not restore_self["new_global_pairs"] and not restore_self["removed_global_pairs"]
    write_json(root / "baseline_restore_report.json", {"schema": "shape-combination-baseline-restore-v1", "passed": restore_passed, "geometry": restore_geometry, "buffers": restore_buffers, "self_intersection": restore_self, "scene_invariant_comparison": restore_scene})

    write_json(root / "combination_validation_report.json", {
        "schema": "candidate-shape-combination-validation-report-v1", "medical_truth": False,
        "baseline_global_overlap_count": BASELINE_GLOBAL_OVERLAPS,
        "hard_gate": "20 engineering-anchor 2-ring overlap count must be zero",
        "global_mesh_claim": "known global overlaps recorded; no globally self-intersection-free claim",
        "fixed_light_contract_sha256": sha256(root / "fixed_prone_light_contract_v1.json"),
        "scene_matrix_absolute_tolerance": 1e-6,
        "candidates": [{"profile_id": item["profile_id"], "betas": item["betas"], "gate": item["gate"], "bed_clearance_m": item["probe"]["bed"]["minimum_body_clearance_m"], "measurements_m": item["probe"]["measurements_m"], "visible_count": item["qc"]["visible_count"], "max_depth_error_m": item["qc"]["max_depth_error_m"], "max_backprojection_error_m": item["qc"]["max_backprojection_error_m"], "self_intersection_status": item["self_intersection"]["status"]} for item in candidates],
    })
    write_json(root / "visual_review.json", {"passed": False, "status": "PENDING_MANUAL_REVIEW", "notice": "Inspect fixed-light montage before finalization."})
    finalize(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--rerun-fixed-lights", action="store_true")
    parser.add_argument("--rejudge-fixed-lights", action="store_true")
    args = parser.parse_args()
    if args.finalize:
        finalize(OUTPUT_ROOT)
    elif args.rerun_fixed_lights:
        execute_fixed_lights(OUTPUT_ROOT)
    elif args.rejudge_fixed_lights:
        rejudge_fixed_light_runs(OUTPUT_ROOT)
    else:
        execute(OUTPUT_ROOT)
    print(json.dumps({"root": str(OUTPUT_ROOT), "finalized": args.finalize}, ensure_ascii=False))


if __name__ == "__main__":
    main()
