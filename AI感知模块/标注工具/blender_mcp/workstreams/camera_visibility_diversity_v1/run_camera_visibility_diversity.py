from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


HERE = Path(__file__).resolve().parent
RECON_WS = HERE.parent / "cross_gate_reconciliation_v1"
sys.path.insert(0, str(RECON_WS))
import run_cross_gate_reconciliation as reconcile  # noqa: E402

cross = reconcile.cross
AI_ROOT = cross.AI_ROOT
RECON_ROOT = AI_ROOT / "outputs" / "内部工程证据" / "2026-08-31_17-27-40_CROSS_GATE_RECONCILIATION_V1"
CONFIG = HERE / "camera_scenarios_v1.json"
APPLY = HERE / "apply_camera_scenario.py"
GRID_DIAGNOSTIC = HERE / "diagnose_camera_grid.py"


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


def scenarios() -> list[dict]:
    return read_json(CONFIG)["scenarios"]


def cells() -> list[dict]:
    frozen = read_json(RECON_ROOT / "CROSS_QUALIFIED_SHAPE_POSE_SEARCH_V1.json")
    by_id = reconcile.by_id()
    return [by_id[item["case_id"]] for item in frozen["combinations"]]


def protected_sources() -> dict:
    result = cross.protected_sources()
    for name, path in {
        "reconciliation_qualified_set": RECON_ROOT / "CROSS_QUALIFIED_SHAPE_POSE_SEARCH_V1.json",
        "reconciliation_verification": RECON_ROOT / "restricted_rgbd_verification.json",
        "camera_scenarios": CONFIG,
        "camera_application": APPLY,
        "camera_orchestration": Path(__file__).resolve(),
    }.items():
        result[name] = {"path": str(path), "sha256": sha256(path)}
    return result


def prepare(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if not read_json(RECON_ROOT / "restricted_rgbd_verification.json")["passed"]:
        raise RuntimeError("Restricted fixed-camera RGB-D gate is not passed")
    if (root / "source_hashes_before.json").is_file():
        if read_json(root / "source_hashes_before.json") != protected_sources():
            raise RuntimeError("Camera diversity protected inputs changed")
        return
    shutil.copy2(CONFIG, root / CONFIG.name)
    shutil.copy2(RECON_ROOT / "engineering_fixture_manual20.json", root / "engineering_fixture_manual20.json")
    shutil.copy2(RECON_ROOT / "body_measurement_contract_v2.json", root / "body_measurement_contract_v2.json")
    shutil.copy2(RECON_ROOT / "fixed_prone_light_contract_v1.json", root / "fixed_prone_light_contract_v1.json")
    (root / "profiles").mkdir(parents=True, exist_ok=True)
    for cell in cells():
        shutil.copy2(RECON_ROOT / "profiles" / f"{cell['case_id']}.json", root / "profiles" / f"{cell['case_id']}.json")
    write_json(root / "source_hashes_before.json", protected_sources())
    write_json(root / "camera_visibility_input.json", {
        "schema": "camera-visibility-diversity-input-v1",
        "medical_truth": False,
        "qualified_shape_pose_count": len(cells()),
        "camera_scenario_count": len(scenarios()),
        "expected_full_matrix_count": len(cells()) * len(scenarios()),
    })


def build_snapshot(root: Path, cell: dict, temp_case: Path) -> Path:
    profile_path = root / "profiles" / f"{cell['case_id']}.json"
    native = temp_case / "native"
    snapshot = temp_case / "base.blend"
    native.parent.mkdir(parents=True, exist_ok=True)
    cross.shared.run([sys.executable, str(cross.shared.GENERATE), "--profile", str(profile_path), "--output", str(native)])
    cross.shared.bj(cross.shared.CANONICAL, cross.shared.PREPARE, [
        "--snapshot", snapshot, "--result", temp_case / "prepare.json",
        "--native-pose-dir", native, "--pose-profile", profile_path,
        "--fixed-scene-contract", cross.shared.CONTRACT_SCENE, "--width", 1280, "--height", 1024,
    ], "ACU_PREPARE_PRONE_SCENE=PASS")
    cross.shared.bj(snapshot, cross.LIGHT_SCRIPT, [
        "--apply", root / "fixed_prone_light_contract_v1.json", "--save", snapshot,
    ], "ACU_FIXED_SCENE_LIGHTS=PASS")
    return snapshot


def geometry_replay(reference: dict, current: dict) -> dict:
    left = {item["point_id"]: item for item in reference["points"]}
    right = {item["point_id"]: item for item in current["points"]}
    binding = all(
        all(left[key][field] == right[key][field] for field in ("face_index", "vertex_indices", "barycentric", "side"))
        for key in left
    )
    max_xyz = max(math.dist(left[key]["xyz_world_m"], right[key]["xyz_world_m"]) for key in left)
    hash_key = "evaluated_local_vertices_float32_sha256"
    mesh_hash_equal = reference["model"][hash_key] == current["model"][hash_key]
    return {
        "passed": mesh_hash_equal and binding and max_xyz <= 1e-8,
        "mesh_hash_equal": mesh_hash_equal,
        "bindings_equal": binding,
        "max_xyz_world_error_m": max_xyz,
    }


def reason_counts(labels: dict) -> dict:
    reasons = [point["visibility_reason"] for point in labels["points"]]
    return {reason: reasons.count(reason) for reason in sorted(set(reasons))}


def scenario_qc(sample: Path, scenario: dict) -> dict:
    labels = read_json(sample / "labels.json")
    depth = np.load(sample / "scene_depth_z.npy", allow_pickle=False)
    with Image.open(sample / "skin_mask.png") as image:
        skin = np.asarray(image.convert("L"))
    with Image.open(sample / "depth_valid_mask.png") as image:
        valid = np.asarray(image.convert("L"))
    counts = reason_counts(labels)
    expected = scenario["expect"]
    checks = {
        "minimum_visible": counts.get("VISIBLE", 0) >= int(expected.get("minimum_visible", 0)),
        "minimum_self_occluded": counts.get("SELF_OCCLUDED", 0) >= int(expected.get("minimum_self_occluded", 0)),
        "minimum_back_facing": counts.get("BACK_FACING", 0) >= int(expected.get("minimum_back_facing", 0)),
        "minimum_out_of_frame": counts.get("OUT_OF_FRAME", 0) >= int(expected.get("minimum_out_of_frame", 0)),
        "minimum_external_occluded": counts.get("EXTERNAL_OCCLUDED", 0) >= int(expected.get("minimum_external_occluded", 0)),
    }
    external_details = []
    for point in labels["points"]:
        if point["visibility_reason"] != "EXTERNAL_OCCLUDED":
            continue
        u, v = map(float, point["uv_pixel_opencv"])
        in_frame = 0 <= u < depth.shape[1] and 0 <= v < depth.shape[0]
        observed = float(depth[int(v), int(u)]) if in_frame else 0.0
        point_z = float(point["camera_depth_z_m"])
        pixel_ok = bool(in_frame and valid[int(v), int(u)] == 255 and skin[int(v), int(u)] == 0 and 0 < observed < point_z)
        external_details.append({
            "point_id": point["point_id"], "pixel_ok": pixel_ok, "observed_depth_m": observed,
            "point_depth_m": point_z, "ray_hit_object": point["ray_hit_object"],
        })
    checks["external_depth_and_masks"] = all(item["pixel_ok"] and item["ray_hit_object"] == "__ACU_EXTERNAL_OCCLUDER__" for item in external_details)
    checks["external_details_present_when_required"] = bool(external_details) if expected.get("minimum_external_occluded", 0) else True
    return {"passed": all(checks.values()), "checks": checks, "reason_counts": counts, "external_details": external_details}


def run_sample(root: Path, phase: str, cell: dict, scenario: dict, base_snapshot: Path, temporary: Path, *, temp_sample: bool = False) -> dict:
    sample_id = f"{cell['case_id']}__{scenario['camera_id']}"
    phase_root = root / phase
    probe_path = phase_root / "probes" / f"{sample_id}.json"
    meta_path = phase_root / "meta" / f"{sample_id}.json"
    preview_path = phase_root / "previews" / f"{sample_id}.png"
    sample_path = temporary / sample_id / "sample" if temp_sample else phase_root / "samples" / sample_id
    if meta_path.is_file() and (sample_path / "labels.json").is_file():
        return read_json(meta_path)
    for path in (probe_path, meta_path, preview_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    scenario_snapshot = temporary / sample_id / f"{sample_id}.blend"
    scenario_snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base_snapshot, scenario_snapshot)
    cross.shared.bj(scenario_snapshot, APPLY, [
        "--config", root / CONFIG.name, "--camera-id", scenario["camera_id"],
        "--result", temporary / sample_id / "camera_result.json", "--save", scenario_snapshot,
    ], "ACU_APPLY_CAMERA_SCENARIO=PASS")
    profile_path = root / "profiles" / f"{cell['case_id']}.json"
    native_parameters = temporary / cell["case_id"] / "native" / "parameters.json"
    cross.shared.bj(scenario_snapshot, cross.SHAPE_PROBE, [
        "--atlas", RECON_ROOT / "source_atlas_v5.json", "--contract", root / "body_measurement_contract_v2.json",
        "--profile", profile_path, "--native-parameters", native_parameters,
        "--core-parent", cross.shared.CORE_PARENT, "--output", probe_path, "--width", 1280, "--height", 1024,
    ], "ACU_SHAPE_COMBINATION_PROBE=PASS")
    cross.shared.bj(scenario_snapshot, cross.shared.RENDER, [preview_path], "ACU_NATURAL_PRONE_PREVIEW=PASS")
    cross.shared.bj(scenario_snapshot, cross.shared.EXPORT, [
        "--fixture", root / "engineering_fixture_manual20.json", "--output", sample_path,
        "--result", phase_root / "export" / f"{sample_id}.json", "--width", 1280, "--height", 1024,
    ], "ACU_EXPORT_PRONE_SAMPLE=PASS")
    probe = read_json(probe_path)
    cross.shared.overlay_from_probe(sample_path / "rgb.png", probe, sample_path / "overlay.png")
    profile = read_json(profile_path)
    generic_qc = cross.shared.strict_sample_qc(sample_path, read_json(root / "engineering_fixture_manual20.json"), [float(v) for v in profile["betas"]])
    labels = read_json(sample_path / "labels.json")
    generic_qc["checks"]["pose_recorded"] = labels["scene"]["native_pose_parameters_degrees"] == profile["pose_degrees"]
    generic_qc["passed"] = bool(generic_qc["passed"] and generic_qc["checks"]["pose_recorded"])
    reference = read_json(RECON_ROOT / "restricted_rgbd" / "probes" / f"{cell['case_id']}.json")
    replay = geometry_replay(reference, probe)
    camera_qc = scenario_qc(sample_path, scenario)
    meta = {
        "schema": "camera-visibility-diversity-sample-meta-v1", "medical_truth": False,
        "sample_id": sample_id, "case_id": cell["case_id"], "camera_id": scenario["camera_id"],
        "passed": bool(generic_qc["passed"] and replay["passed"] and camera_qc["passed"]),
        "generic_qc": generic_qc, "geometry_replay": replay, "camera_qc": camera_qc,
        "buffer_hashes": {
            name: sha256(sample_path / name)
            for name in ("rgb.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png")
        },
        "sample": str(sample_path),
    }
    write_json(phase_root / "qc" / f"{sample_id}.json", meta)
    write_json(meta_path, meta)
    return meta


def run_phase(root: Path, phase: str, selected_cells: list[dict], *, temp_samples: bool = False) -> list[dict]:
    prepare(root)
    results = []
    with tempfile.TemporaryDirectory(prefix=f"acu_camera_{phase}_") as temporary_name:
        temporary = Path(temporary_name)
        for cell_index, cell in enumerate(selected_cells, start=1):
            cell_temp = temporary / cell["case_id"]
            base = build_snapshot(root, cell, cell_temp)
            for scenario in scenarios():
                result = run_sample(root, phase, cell, scenario, base, temporary, temp_sample=temp_samples)
                results.append(result)
                print(f"{phase.upper()} {len(results)}/{len(selected_cells) * len(scenarios())} {result['sample_id']}: {'PASS' if result['passed'] else 'FAIL'}", flush=True)
    return results


def smoke(root: Path) -> None:
    chosen = [next(cell for cell in cells() if cell["case_id"] == "C03_LONG_NARROW__D06_THORAX_EXTENSION_P4")]
    results = run_phase(root, "smoke", chosen)
    payload = {"schema": "camera-visibility-diversity-smoke-v1", "passed": len(results) == len(scenarios()) and all(item["passed"] for item in results), "samples": results}
    write_json(root / "smoke_verification.json", payload)
    if not payload["passed"]:
        raise SystemExit(2)


def diagnose(root: Path) -> None:
    prepare(root)
    chosen = next(cell for cell in cells() if cell["case_id"] == "C03_LONG_NARROW__D06_THORAX_EXTENSION_P4")
    with tempfile.TemporaryDirectory(prefix="acu_camera_grid_") as temporary_name:
        temporary = Path(temporary_name)
        snapshot = build_snapshot(root, chosen, temporary / chosen["case_id"])
        cross.shared.bj(snapshot, GRID_DIAGNOSTIC, [
            "--fixture", root / "engineering_fixture_manual20.json",
            "--core-parent", cross.shared.CORE_PARENT,
            "--output", root / "diagnostics" / "camera_grid_report.json",
        ], "ACU_CAMERA_GRID_DIAGNOSTIC=PASS")


def full(root: Path) -> None:
    if not read_json(root / "smoke_verification.json")["passed"]:
        raise RuntimeError("Camera smoke must pass before the full matrix")
    results = run_phase(root, "matrix", cells())
    reasons = {scenario["camera_id"]: {} for scenario in scenarios()}
    for item in results:
        bucket = reasons[item["camera_id"]]
        for reason, count in item["camera_qc"]["reason_counts"].items():
            bucket[reason] = bucket.get(reason, 0) + int(count)
    scenario_rows = []
    for scenario in scenarios():
        subset = [item for item in results if item["camera_id"] == scenario["camera_id"]]
        qualified = [item for item in subset if item["passed"]]
        policy = scenario["qualification_policy"]
        policy_passed = len(qualified) == 17 if policy == "REQUIRE_ALL_17" else len(qualified) >= 3
        scenario_rows.append({
            "camera_id": scenario["camera_id"], "qualification_policy": policy,
            "processed_count": len(subset), "qualified_count": len(qualified),
            "incompatible_count": len(subset) - len(qualified), "policy_passed": policy_passed,
            "qualified_sample_ids": [item["sample_id"] for item in qualified],
            "incompatible_sample_ids": [item["sample_id"] for item in subset if not item["passed"]],
        })
    payload = {
        "schema": "camera-visibility-diversity-matrix-v1", "medical_truth": False,
        "passed": len(results) == len(cells()) * len(scenarios()) and all(item["policy_passed"] for item in scenario_rows),
        "sample_count": len(results), "qualified_sample_count": sum(item["passed"] for item in results),
        "reason_totals_by_camera": reasons, "scenario_qualification": scenario_rows, "samples": results,
    }
    write_json(root / "camera_visibility_matrix_report.json", payload)
    if not payload["passed"]:
        raise SystemExit(3)


def determinism(root: Path) -> None:
    matrix = read_json(root / "camera_visibility_matrix_report.json")
    if not matrix["passed"]:
        raise RuntimeError("Camera matrix must pass before determinism")
    results = run_phase(root, "determinism", cells(), temp_samples=True)
    by_sample = {item["sample_id"]: item for item in results}
    rows = []
    for primary in matrix["samples"]:
        replay = by_sample[primary["sample_id"]]
        buffers = {
            name: {
                "equal": primary["buffer_hashes"][name] == replay["buffer_hashes"][name],
                "required": name != "rgb.png",
            }
            for name in primary["buffer_hashes"]
        }
        buffers_passed = all(item["equal"] for item in buffers.values() if item["required"])
        rows.append({
            "sample_id": primary["sample_id"],
            "passed": bool(primary["passed"] == replay["passed"] and primary["generic_qc"] == replay["generic_qc"] and primary["camera_qc"] == replay["camera_qc"] and primary["geometry_replay"] == replay["geometry_replay"] and buffers_passed),
            "qualification_equal": primary["passed"] == replay["passed"],
            "generic_qc_equal": primary["generic_qc"] == replay["generic_qc"],
            "camera_qc_equal": primary["camera_qc"] == replay["camera_qc"],
            "geometry_replay_equal": primary["geometry_replay"] == replay["geometry_replay"],
            "buffers": {"passed": buffers_passed, "files": buffers},
        })
    payload = {"schema": "camera-visibility-diversity-determinism-v1", "passed": len(rows) == len(cells()) * len(scenarios()) and all(item["passed"] for item in rows), "fresh_native_and_blender_process_per_shape_pose": True, "samples": rows}
    write_json(root / "determinism_report.json", payload)
    if not payload["passed"]:
        raise SystemExit(4)


def build_manifest(root: Path) -> dict:
    manifest = root / "SHA256SUMS.txt"
    rows = [f"{sha256(path)}  {path.relative_to(root).as_posix()}" for path in sorted(root.rglob("*")) if path.is_file() and path != manifest]
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"entries": len(rows), "manifest_sha256": sha256(manifest)}


def finalize(root: Path) -> None:
    smoke_report = read_json(root / "smoke_verification.json")
    matrix = read_json(root / "camera_visibility_matrix_report.json")
    determinism_report = read_json(root / "determinism_report.json")
    source_unchanged = read_json(root / "source_hashes_before.json") == protected_sources()
    qualified = [item for item in matrix["samples"] if item["passed"]]
    stress = next(item for item in matrix["scenario_qualification"] if item["camera_id"] == "C4_SELF_OCCLUSION_STRESS")
    write_json(root / "QUALIFIED_CAMERA_SHAPE_POSE_COMPATIBILITY_V1.json", {
        "schema": "qualified-camera-shape-pose-compatibility-v1", "medical_truth": False,
        "general_camera_ids": ["C1_MILD_OBLIQUE", "C2_EDGE_CROP", "C3_EXTERNAL_OCCLUDER"],
        "general_camera_shape_pose_count_each": 17,
        "self_occlusion_stress_qualified_sample_ids": stress["qualified_sample_ids"],
        "self_occlusion_stress_incompatible_sample_ids": stress["incompatible_sample_ids"],
        "qualified_sample_count": len(qualified),
        "not_claimed": ["continuous camera-space safety", "real RGB-D calibration", "medical validity"],
    })
    verification = {
        "schema": "camera-visibility-diversity-verification-v1",
        "passed": bool(smoke_report["passed"] and matrix["passed"] and determinism_report["passed"] and source_unchanged),
        "shape_pose_count": 17, "camera_scenario_count": len(scenarios()), "sample_count": matrix["sample_count"],
        "qualified_sample_count": len(qualified),
        "general_camera_count": 3,
        "self_occlusion_stress_qualified_count": stress["qualified_count"],
        "self_occlusion_stress_incompatible_count": stress["incompatible_count"],
        "reason_totals_by_camera": matrix["reason_totals_by_camera"],
        "determinism_passed": determinism_report["passed"], "protected_sources_unchanged": source_unchanged,
        "truth_status": {"kind": "ENGINEERING_QA", "medical_truth": False, "medical_validated": False},
        "next_gate": "Only after review may the 3 general cameras and the explicitly compatible self-occlusion cells seed a 300-500 sample engineering Pilot.",
    }
    write_json(root / "verification.json", verification)
    result = build_manifest(root)
    print(json.dumps({"CAMERA_VISIBILITY_FINAL": "PASS" if verification["passed"] else "FAIL", **result}, ensure_ascii=False), flush=True)
    if not verification["passed"]:
        raise SystemExit(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "diagnose", "smoke", "full", "determinism", "finalize"))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.root)
    elif args.mode == "diagnose":
        diagnose(args.root)
    elif args.mode == "smoke":
        smoke(args.root)
    elif args.mode == "full":
        full(args.root)
    elif args.mode == "determinism":
        determinism(args.root)
    else:
        finalize(args.root)


if __name__ == "__main__":
    main()
