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
CAMERA_WS = HERE.parent / "camera_visibility_diversity_v1"
sys.path.insert(0, str(CAMERA_WS))
import run_camera_visibility_diversity as camera_gate  # noqa: E402

cross = camera_gate.cross
AI_ROOT = cross.AI_ROOT
RECON_ROOT = camera_gate.RECON_ROOT
CONFIG = HERE / "truncation_profiles_v2.json"
APPLY = CAMERA_WS / "apply_camera_scenario.py"
SEVERITY = HERE / "measure_truncation_severity.py"


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


def profiles() -> list[dict]:
    config = read_json(CONFIG)
    return [
        {
            **profile,
            "purpose": f"Controlled {profile['subject_side_clipped']} {profile['severity']} truncation",
            "qualification_policy": "FREEZE_COMPATIBLE_CELLS_ONLY",
        }
        for profile in config["scenarios"]
    ]


def cells() -> list[dict]:
    return camera_gate.cells()


def mirror_contract() -> dict:
    config = read_json(CONFIG)
    baseline_x = float(config["baseline_camera_matrix_world"][0][3])
    by_key = {(item["severity"], item["subject_side_clipped"]): item for item in config["scenarios"]}
    checks = {}
    for severity in ("MILD", "MODERATE"):
        left = by_key[(severity, "LEFT")]
        right = by_key[(severity, "RIGHT")]
        left_matrix = left["matrix_world"]
        right_matrix = right["matrix_world"]
        checks[f"{severity}_x_mirror"] = abs((float(left_matrix[0][3]) + float(right_matrix[0][3])) * 0.5 - baseline_x) < 1e-12
        checks[f"{severity}_absolute_offsets_equal"] = abs(abs(float(left["camera_offset_x_m"])) - abs(float(right["camera_offset_x_m"]))) < 1e-12
        checks[f"{severity}_non_x_matrix_equal"] = all(
            float(left_matrix[row][col]) == float(right_matrix[row][col])
            for row in range(4) for col in range(4) if (row, col) != (0, 3)
        )
        checks[f"{severity}_lens_equal"] = float(left["lens_mm"]) == float(right["lens_mm"])
    return {"passed": all(checks.values()), "baseline_camera_x_m": baseline_x, "checks": checks}


def protected_sources() -> dict:
    result = camera_gate.protected_sources()
    for name, path in {
        "truncation_profiles": CONFIG,
        "severity_probe": SEVERITY,
        "orchestration": Path(__file__).resolve(),
    }.items():
        result[name] = {"path": str(path), "sha256": sha256(path)}
    return result


def prepare(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if not read_json(RECON_ROOT / "restricted_rgbd_verification.json")["passed"]:
        raise RuntimeError("Restricted fixed-camera RGB-D gate is not passed")
    mirror = mirror_contract()
    if not mirror["passed"]:
        raise RuntimeError("Truncation profiles are not strict mirrors")
    if (root / "source_hashes_before.json").is_file():
        if read_json(root / "source_hashes_before.json") != protected_sources():
            raise RuntimeError("Protected inputs changed")
        return
    shutil.copy2(CONFIG, root / CONFIG.name)
    shutil.copy2(RECON_ROOT / "engineering_fixture_manual20.json", root / "engineering_fixture_manual20.json")
    shutil.copy2(RECON_ROOT / "body_measurement_contract_v2.json", root / "body_measurement_contract_v2.json")
    shutil.copy2(RECON_ROOT / "fixed_prone_light_contract_v1.json", root / "fixed_prone_light_contract_v1.json")
    (root / "profiles").mkdir(parents=True, exist_ok=True)
    for cell in cells():
        shutil.copy2(RECON_ROOT / "profiles" / f"{cell['case_id']}.json", root / "profiles" / f"{cell['case_id']}.json")
    write_json(root / "source_hashes_before.json", protected_sources())
    write_json(root / "profile_mirror_contract.json", mirror)
    write_json(root / "truncation_gate_input.json", {
        "schema": "truncation-gate-input-v2",
        "medical_truth": False,
        "qualified_shape_pose_count": len(cells()),
        "profile_count": len(profiles()),
        "matrix_count": len(cells()) * len(profiles()),
        "training_authorized": False,
    })


def baseline_skin_pixels(case_id: str) -> int:
    path = RECON_ROOT / "restricted_rgbd" / "samples" / case_id / "skin_mask.png"
    with Image.open(path) as image:
        return int((np.asarray(image.convert("L"), dtype=np.uint8) == 255).sum())


def reason_counts(labels: dict) -> dict:
    reasons = [point["visibility_reason"] for point in labels["points"]]
    return {reason: reasons.count(reason) for reason in sorted(set(reasons))}


def truncation_qc(sample: Path, case_id: str, profile: dict, severity: dict) -> dict:
    labels = read_json(sample / "labels.json")
    counts = reason_counts(labels)
    out_points = [point for point in labels["points"] if point["visibility_reason"] == "OUT_OF_FRAME"]
    expected = profile["expect"]
    with Image.open(sample / "skin_mask.png") as image:
        current_skin_pixels = int((np.asarray(image.convert("L"), dtype=np.uint8) == 255).sum())
    baseline_pixels = baseline_skin_pixels(case_id)
    skin_ratio = current_skin_pixels / baseline_pixels
    edge = profile["image_edge_clipped"]
    opposite = "RIGHT" if edge == "LEFT" else "LEFT"
    checks = {
        "minimum_visible": counts.get("VISIBLE", 0) >= int(expected["minimum_visible"]),
        "out_of_frame_within_frozen_stratum": int(expected["minimum_out_of_frame"]) <= counts.get("OUT_OF_FRAME", 0) <= int(expected["maximum_out_of_frame"]),
        "out_of_frame_only_expected_subject_side": bool(out_points) and all(point["side"] == profile["subject_side_clipped"] for point in out_points),
        "projected_bbox_clips_expected_edge": bool(severity["clipped_edges"][edge]),
        "projected_bbox_does_not_clip_opposite_edge": not bool(severity["clipped_edges"][opposite]),
        "projected_bbox_does_not_clip_vertical_edges": not severity["clipped_edges"]["TOP"] and not severity["clipped_edges"]["BOTTOM"],
        "positive_bbox_truncation": float(severity["bbox_area_truncation_fraction"]) > 0.0,
        "skin_mask_area_reduced_but_nonempty": 0.0 < skin_ratio < 1.0,
    }
    per_point = [
        {"point_id": point["point_id"], "side": point["side"], "visibility_reason": point["visibility_reason"], "uv": point["uv_pixel_opencv"]}
        for point in labels["points"]
    ]
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "reason_counts": counts,
        "out_of_frame_point_ids": [point["point_id"] for point in out_points],
        "skin_mask_pixel_count": current_skin_pixels,
        "baseline_skin_mask_pixel_count": baseline_pixels,
        "skin_mask_area_ratio_to_baseline": skin_ratio,
        "severity": severity,
        "per_point_visibility": per_point,
    }


def run_sample(root: Path, phase: str, cell: dict, profile: dict, base_snapshot: Path, temporary: Path, *, temp_sample: bool) -> dict:
    sample_id = f"{cell['case_id']}__{profile['camera_id']}"
    phase_root = root / phase
    meta_path = phase_root / "meta" / f"{sample_id}.json"
    sample_path = temporary / sample_id / "sample" if temp_sample else phase_root / "samples" / sample_id
    if meta_path.is_file() and (sample_path / "labels.json").is_file():
        return read_json(meta_path)
    scenario_snapshot = temporary / sample_id / f"{sample_id}.blend"
    scenario_snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base_snapshot, scenario_snapshot)
    cross.shared.bj(scenario_snapshot, APPLY, [
        "--config", root / CONFIG.name, "--camera-id", profile["camera_id"],
        "--result", temporary / sample_id / "camera_result.json", "--save", scenario_snapshot,
    ], "ACU_APPLY_CAMERA_SCENARIO=PASS")
    severity_path = phase_root / "severity" / f"{sample_id}.json"
    cross.shared.bj(scenario_snapshot, SEVERITY, [
        "--mesh-name", "SKEL-skin-female", "--width", 1280, "--height", 1024, "--output", severity_path,
    ], "ACU_TRUNCATION_SEVERITY=PASS")
    profile_path = root / "profiles" / f"{cell['case_id']}.json"
    native_parameters = temporary / cell["case_id"] / "native" / "parameters.json"
    probe_path = phase_root / "probes" / f"{sample_id}.json"
    cross.shared.bj(scenario_snapshot, cross.SHAPE_PROBE, [
        "--atlas", RECON_ROOT / "source_atlas_v5.json", "--contract", root / "body_measurement_contract_v2.json",
        "--profile", profile_path, "--native-parameters", native_parameters,
        "--core-parent", cross.shared.CORE_PARENT, "--output", probe_path, "--width", 1280, "--height", 1024,
    ], "ACU_SHAPE_COMBINATION_PROBE=PASS")
    cross.shared.bj(scenario_snapshot, cross.shared.EXPORT, [
        "--fixture", root / "engineering_fixture_manual20.json", "--output", sample_path,
        "--result", phase_root / "export" / f"{sample_id}.json", "--width", 1280, "--height", 1024,
    ], "ACU_EXPORT_PRONE_SAMPLE=PASS")
    probe = read_json(probe_path)
    cross.shared.overlay_from_probe(sample_path / "rgb.png", probe, sample_path / "overlay.png")
    shape_pose_profile = read_json(profile_path)
    generic_qc = cross.shared.strict_sample_qc(sample_path, read_json(root / "engineering_fixture_manual20.json"), [float(value) for value in shape_pose_profile["betas"]])
    labels = read_json(sample_path / "labels.json")
    generic_qc["checks"]["pose_recorded"] = labels["scene"]["native_pose_parameters_degrees"] == shape_pose_profile["pose_degrees"]
    generic_qc["passed"] = bool(generic_qc["passed"] and generic_qc["checks"]["pose_recorded"])
    replay = camera_gate.geometry_replay(read_json(RECON_ROOT / "restricted_rgbd" / "probes" / f"{cell['case_id']}.json"), probe)
    truncation = truncation_qc(sample_path, cell["case_id"], profile, read_json(severity_path))
    meta = {
        "schema": "truncation-gate-sample-meta-v2",
        "medical_truth": False,
        "sample_id": sample_id,
        "case_id": cell["case_id"],
        "camera_id": profile["camera_id"],
        "subject_side_clipped": profile["subject_side_clipped"],
        "severity_class": profile["severity"],
        "passed": bool(generic_qc["passed"] and replay["passed"] and truncation["passed"]),
        "generic_qc": generic_qc,
        "geometry_replay": replay,
        "truncation_qc": truncation,
        "buffer_hashes": {name: sha256(sample_path / name) for name in ("rgb.png", "scene_depth_z.npy", "depth_valid_mask.png", "skin_mask.png")},
        "sample": str(sample_path),
    }
    write_json(phase_root / "qc" / f"{sample_id}.json", meta)
    write_json(meta_path, meta)
    return meta


def run_phase(root: Path, phase: str, selected_cells: list[dict], *, temp_samples: bool = False) -> list[dict]:
    prepare(root)
    results = []
    with tempfile.TemporaryDirectory(prefix=f"acu_trunc_{phase}_") as temporary_name:
        temporary = Path(temporary_name)
        for cell in selected_cells:
            base = camera_gate.build_snapshot(root, cell, temporary / cell["case_id"])
            for profile in profiles():
                result = run_sample(root, phase, cell, profile, base, temporary, temp_sample=temp_samples)
                results.append(result)
                print(f"{phase.upper()} {len(results)}/{len(selected_cells) * len(profiles())} {result['sample_id']}: {'PASS' if result['passed'] else 'INCOMPATIBLE'}", flush=True)
    return results


def smoke(root: Path) -> None:
    chosen = [next(cell for cell in cells() if cell["case_id"] == "C03_LONG_NARROW__D06_THORAX_EXTENSION_P4")]
    results = run_phase(root, "smoke", chosen)
    payload = {"schema": "truncation-gate-smoke-v2", "passed": len(results) == 4 and all(item["passed"] for item in results), "samples": results}
    write_json(root / "smoke_verification.json", payload)
    if not payload["passed"]:
        raise SystemExit(2)


def full(root: Path) -> None:
    if not read_json(root / "smoke_verification.json")["passed"]:
        raise RuntimeError("Smoke must pass before matrix")
    results = run_phase(root, "matrix", cells())
    profile_rows = []
    for profile in profiles():
        subset = [item for item in results if item["camera_id"] == profile["camera_id"]]
        qualified = [item for item in subset if item["passed"]]
        profile_rows.append({
            "camera_id": profile["camera_id"],
            "subject_side_clipped": profile["subject_side_clipped"],
            "severity": profile["severity"],
            "processed_count": len(subset),
            "qualified_count": len(qualified),
            "incompatible_count": len(subset) - len(qualified),
            "qualified_sample_ids": [item["sample_id"] for item in qualified],
            "incompatible_sample_ids": [item["sample_id"] for item in subset if not item["passed"]],
        })
    payload = {
        "schema": "truncation-gate-matrix-v2",
        "medical_truth": False,
        "passed": len(results) == 68,
        "all_cells_processed": len(results) == 68,
        "qualified_count": sum(item["passed"] for item in results),
        "incompatible_count": sum(not item["passed"] for item in results),
        "profiles": profile_rows,
        "samples": results,
    }
    write_json(root / "truncation_matrix_report.json", payload)
    if not payload["passed"]:
        raise SystemExit(3)


def determinism(root: Path) -> None:
    matrix = read_json(root / "truncation_matrix_report.json")
    if not matrix["passed"]:
        raise RuntimeError("Matrix must complete before determinism")
    replay_results = run_phase(root, "determinism", cells(), temp_samples=True)
    replay_by_id = {item["sample_id"]: item for item in replay_results}
    rows = []
    for primary in matrix["samples"]:
        replay = replay_by_id[primary["sample_id"]]
        buffers = {
            name: {"equal": primary["buffer_hashes"][name] == replay["buffer_hashes"][name], "required": name != "rgb.png"}
            for name in primary["buffer_hashes"]
        }
        required_buffers_equal = all(item["equal"] for item in buffers.values() if item["required"])
        passed = bool(
            primary["passed"] == replay["passed"]
            and primary["generic_qc"] == replay["generic_qc"]
            and primary["geometry_replay"] == replay["geometry_replay"]
            and primary["truncation_qc"] == replay["truncation_qc"]
            and required_buffers_equal
        )
        rows.append({"sample_id": primary["sample_id"], "passed": passed, "qualification_equal": primary["passed"] == replay["passed"], "required_buffers_equal": required_buffers_equal, "buffers": buffers})
    payload = {"schema": "truncation-gate-determinism-v2", "passed": len(rows) == 68 and all(item["passed"] for item in rows), "fresh_native_and_blender_process_per_shape_pose": True, "samples": rows}
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
    matrix = read_json(root / "truncation_matrix_report.json")
    determinism_report = read_json(root / "determinism_report.json")
    mirror = read_json(root / "profile_mirror_contract.json")
    source_unchanged = read_json(root / "source_hashes_before.json") == protected_sources()
    qualified = [item for item in matrix["samples"] if item["passed"]]
    write_json(root / "QUALIFIED_TRUNCATION_COMPATIBILITY_V2.json", {
        "schema": "qualified-truncation-compatibility-v2",
        "medical_truth": False,
        "training_authorized": False,
        "profile_mirror_contract_passed": mirror["passed"],
        "qualified_sample_ids": [item["sample_id"] for item in qualified],
        "incompatible_sample_ids": [item["sample_id"] for item in matrix["samples"] if not item["passed"]],
        "qualified_count": len(qualified),
        "incompatible_count": len(matrix["samples"]) - len(qualified),
        "not_claimed": ["continuous camera coverage", "network improvement", "real RGB-D validity", "medical validity", "robot safety"],
    })
    verification = {
        "schema": "truncation-gate-verification-v2",
        "passed": bool(smoke_report["passed"] and matrix["passed"] and determinism_report["passed"] and mirror["passed"] and source_unchanged),
        "shape_pose_count": 17,
        "profile_count": 4,
        "processed_count": 68,
        "qualified_count": len(qualified),
        "incompatible_count": 68 - len(qualified),
        "determinism_passed": determinism_report["passed"],
        "protected_sources_unchanged": source_unchanged,
        "training_started": False,
        "truth_status": {"kind": "ENGINEERING_QA", "medical_truth": False, "medical_validated": False},
        "next_gate": "Review compatibility before any FAILURE_DRIVEN_PILOT_V2 dataset or training work.",
    }
    write_json(root / "verification.json", verification)
    result = build_manifest(root)
    print(json.dumps({"TRUNCATION_GATE_FINAL": "PASS" if verification["passed"] else "FAIL", **result}, ensure_ascii=False), flush=True)
    if not verification["passed"]:
        raise SystemExit(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "smoke", "full", "determinism", "finalize"))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.root)
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
