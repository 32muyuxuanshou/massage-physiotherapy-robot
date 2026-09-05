#!/usr/bin/env python3
"""Fresh-process deterministic replay for the B-line pose profiles."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

import run_enhanced_pose_only as b


def compare_points(first: dict, second: dict) -> dict:
    a = {item["point_id"]: item for item in first["points"]}
    c = {item["point_id"]: item for item in second["points"]}
    ids_equal = set(a) == set(c)
    bindings_equal = ids_equal and all(
        all(a[key][field] == c[key][field] for field in ("face_index", "vertex_indices", "barycentric"))
        for key in a
    )
    xyz = max((math.dist(a[key]["xyz_world_m"], c[key]["xyz_world_m"]) for key in a), default=math.inf)
    uv = max((math.dist(a[key]["uv_pixel_opencv"], c[key]["uv_pixel_opencv"]) for key in a), default=math.inf)
    normal = max((math.dist(a[key]["normal_world"], c[key]["normal_world"]) for key in a), default=math.inf)
    triangle = max((abs(float(a[key]["triangle_area_m2"]) - float(c[key]["triangle_area_m2"])) for key in a), default=math.inf)
    visibility = ids_equal and all(
        a[key]["visible"] == c[key]["visible"]
        and a[key]["visibility_reason"] == c[key]["visibility_reason"]
        and a[key]["ray_hit_object"] == c[key]["ray_hit_object"]
        for key in a
    )
    passed = bindings_equal and visibility and xyz <= 1e-8 and uv <= 1e-5 and normal <= 1e-8 and triangle <= 1e-12
    return {
        "passed": passed,
        "point_ids_equal": ids_equal,
        "bindings_equal": bindings_equal,
        "visibility_equal": visibility,
        "max_xyz_world_error_m": xyz,
        "max_uv_error_px": uv,
        "max_normal_vector_error": normal,
        "max_triangle_area_error_m2": triangle,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=b.OUT)
    args = parser.parse_args()
    root = args.output.resolve()
    if root != b.OUT.resolve():
        raise ValueError("B determinism output must remain in the authorized B directory")
    report = b.read(root / "pose_only_report.json")
    if not report["batch_complete"]:
        raise RuntimeError("primary B batch is incomplete")
    if b.read(root / "source_hashes_before.json") != b.source_hashes():
        raise RuntimeError("B source hashes changed before deterministic replay")

    replay_root = root / "determinism_v2"
    light_contract = b.RUN_ROOT / "fixed_light_contract_v1.json"
    if not light_contract.is_file():
        raise FileNotFoundError(light_contract)
    for subdir in ("native", "snapshots", "prepare", "probes", "self_intersections", "lights"):
        (replay_root / subdir).mkdir(parents=True, exist_ok=True)
    cases = []
    for index, definition in enumerate(b.read(b.CONFIG)["profiles"]):
        pose_id = definition["pose_id"]
        profile = root / "profiles" / f"{pose_id}.json"
        native = replay_root / "native" / pose_id
        if not native.exists():
            b.run([str(b.PYTHON), str(b.GENERATE), "--profile", str(profile), "--output", str(native)])
        snapshot = replay_root / "snapshots" / f"{pose_id}.blend"
        prepare = replay_root / "prepare" / f"{pose_id}.json"
        b.run([str(b.BLENDER), "--background", str(b.CANONICAL), "--python", str(b.PREPARE), "--",
               "--snapshot", str(snapshot), "--result", str(prepare), "--native-pose-dir", str(native),
               "--pose-profile", str(profile), "--fixed-scene-contract", str(b.CONTRACT), "--width", "1280", "--height", "1024"],
              "ACU_PREPARE_PRONE_SCENE=PASS")
        light_result = replay_root / "lights" / f"{pose_id}.json"
        b.run([str(b.BLENDER), "--background", str(snapshot), "--python", str(b.LIGHT_SCRIPT), "--",
               "--mode", "apply", "--contract", str(light_contract), "--result", str(light_result)],
              "ACU_FIXED_LIGHT_CONTRACT=PASS")
        probe_path = replay_root / "probes" / f"{pose_id}.json"
        b.run([str(b.BLENDER), "--background", str(snapshot), "--python", str(b.PROBE), "--",
               "--atlas", str(b.ATLAS), "--profile", str(profile), "--native-parameters", str(native / "parameters.json"),
               "--core-parent", str(b.CORE_PARENT), "--output", str(probe_path), "--width", "1280", "--height", "1024"],
              "ACU_ENHANCED_POSE_PROBE=PASS")
        si_path = replay_root / "self_intersections" / f"{pose_id}.json"
        process = subprocess.run(
            [str(b.BLENDER), "--background", str(snapshot), "--python", str(b.SELF_INTERSECTION), "--",
             "--object", "SKEL-skin-female", "--output", str(si_path), "--anchor-atlas", str(b.ATLAS),
             "--anchor-rings", "2", "--max-pairs", "20000"],
            cwd=str(b.TOOL_ROOT), env=b.environment(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=900,
        )
        if process.returncode not in (0, 2) or not si_path.is_file():
            raise RuntimeError((process.stdout + "\n" + process.stderr)[-12000:])
        first, second = b.read(b.RUN_ROOT / "probes" / f"{pose_id}.json"), b.read(probe_path)
        first_si, second_si = b.read(b.RUN_ROOT / "self_intersections" / f"{pose_id}.json"), b.read(si_path)
        geometry = compare_points(first, second)
        checks = {
            "mesh_hash_equal": first["model"]["evaluated_local_vertices_float32_sha256"] == second["model"]["evaluated_local_vertices_float32_sha256"],
            "pose_chain_equal": first["requested_pose_degrees_46"] == second["requested_pose_degrees_46"],
            "point_geometry_equal": geometry["passed"],
            "bed_clearance_equal": abs(float(first["bed"]["minimum_body_clearance_m"]) - float(second["bed"]["minimum_body_clearance_m"])) <= 1e-9,
            "self_intersection_pairs_equal": first_si["nonadjacent_intersection_pairs_truncated"] == second_si["nonadjacent_intersection_pairs_truncated"],
            "fixed_light_contract": b.read(light_result)["passed"] and b.read(light_result)["max_matrix_abs_error"] <= 1e-6 and b.read(light_result)["contract_sha256"] == b.sha256(light_contract),
            "camera_matrix_equal": b.matrix_error(first["camera"]["matrix_world"], second["camera"]["matrix_world"]) <= 1e-6,
            "bed_matrix_and_top_equal": b.matrix_error(first["bed"]["matrix_world"], second["bed"]["matrix_world"]) <= 1e-6 and abs(float(first["bed"]["top_z_m"]) - float(second["bed"]["top_z_m"])) <= 1e-9,
            "body_matrix_equal": b.matrix_error(first["model"]["matrix_world"], second["model"]["matrix_world"]) <= 1e-6,
        }
        eligibility_reproduced = first_si["anchor_scope"]["overlap_pair_count"] == second_si["anchor_scope"]["overlap_pair_count"]
        cases.append({"pose_id": pose_id, "checks": checks, "geometry": geometry,
                      "anchor_overlap_pair_count": second_si["anchor_scope"]["overlap_pair_count"],
                      "eligibility_outcome_reproduced": eligibility_reproduced,
                      "passed": all(checks.values()) and eligibility_reproduced})
        b.write(replay_root / "progress.json", cases)
        print(f"DETERMINISM {index + 1}/12 {pose_id}: {'PASS' if all(checks.values()) else 'FAIL'}", flush=True)

    # Generate an explicit R_BASE only after all diagnostics.  The generation
    # pipeline is intentionally stateless/fresh-process, so this proves that
    # returning to the frozen P0 request reproduces the baseline exactly.
    restore_id = "R_BASE"
    p0_profile = root / "profiles" / "P0_BASE.json"
    restore_native = replay_root / "native" / restore_id
    b.run([str(b.PYTHON), str(b.GENERATE), "--profile", str(p0_profile), "--output", str(restore_native)])
    restore_snapshot = replay_root / "snapshots" / f"{restore_id}.blend"
    restore_prepare = replay_root / "prepare" / f"{restore_id}.json"
    b.run([str(b.BLENDER), "--background", str(b.CANONICAL), "--python", str(b.PREPARE), "--",
           "--snapshot", str(restore_snapshot), "--result", str(restore_prepare), "--native-pose-dir", str(restore_native),
           "--pose-profile", str(p0_profile), "--fixed-scene-contract", str(b.CONTRACT), "--width", "1280", "--height", "1024"],
          "ACU_PREPARE_PRONE_SCENE=PASS")
    restore_light_result = replay_root / "lights" / f"{restore_id}.json"
    b.run([str(b.BLENDER), "--background", str(restore_snapshot), "--python", str(b.LIGHT_SCRIPT), "--",
           "--mode", "apply", "--contract", str(light_contract), "--result", str(restore_light_result)],
          "ACU_FIXED_LIGHT_CONTRACT=PASS")
    restore_probe_path = replay_root / "probes" / f"{restore_id}.json"
    b.run([str(b.BLENDER), "--background", str(restore_snapshot), "--python", str(b.PROBE), "--",
           "--atlas", str(b.ATLAS), "--profile", str(p0_profile), "--native-parameters", str(restore_native / "parameters.json"),
           "--core-parent", str(b.CORE_PARENT), "--output", str(restore_probe_path), "--width", "1280", "--height", "1024"],
          "ACU_ENHANCED_POSE_PROBE=PASS")
    restore_si_path = replay_root / "self_intersections" / f"{restore_id}.json"
    restore_process = subprocess.run(
        [str(b.BLENDER), "--background", str(restore_snapshot), "--python", str(b.SELF_INTERSECTION), "--",
         "--object", "SKEL-skin-female", "--output", str(restore_si_path), "--anchor-atlas", str(b.ATLAS),
         "--anchor-rings", "2", "--max-pairs", "20000"],
        cwd=str(b.TOOL_ROOT), env=b.environment(), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=900,
    )
    if restore_process.returncode not in (0, 2) or not restore_si_path.is_file():
        raise RuntimeError((restore_process.stdout + "\n" + restore_process.stderr)[-12000:])
    primary_p0 = b.read(b.RUN_ROOT / "probes" / "P0_BASE.json")
    restored_p0 = b.read(restore_probe_path)
    primary_si = b.read(b.RUN_ROOT / "self_intersections" / "P0_BASE.json")
    restored_si = b.read(restore_si_path)
    restore_geometry = compare_points(primary_p0, restored_p0)
    restore_checks = {
        "mesh_hash_equal": primary_p0["model"]["evaluated_local_vertices_float32_sha256"] == restored_p0["model"]["evaluated_local_vertices_float32_sha256"],
        "point_geometry_equal": restore_geometry["passed"],
        "bed_clearance_equal": abs(float(primary_p0["bed"]["minimum_body_clearance_m"]) - float(restored_p0["bed"]["minimum_body_clearance_m"])) <= 1e-9,
        "self_intersection_pairs_equal": primary_si["nonadjacent_intersection_pairs_truncated"] == restored_si["nonadjacent_intersection_pairs_truncated"],
        "anchor_overlap_zero": restored_si["anchor_scope"]["overlap_pair_count"] == 0,
        "fixed_light_contract": b.read(restore_light_result)["passed"] and b.read(restore_light_result)["max_matrix_abs_error"] <= 1e-6 and b.read(restore_light_result)["contract_sha256"] == b.sha256(light_contract),
        "camera_matrix_equal": b.matrix_error(primary_p0["camera"]["matrix_world"], restored_p0["camera"]["matrix_world"]) <= 1e-6,
        "bed_matrix_and_top_equal": b.matrix_error(primary_p0["bed"]["matrix_world"], restored_p0["bed"]["matrix_world"]) <= 1e-6 and abs(float(primary_p0["bed"]["top_z_m"]) - float(restored_p0["bed"]["top_z_m"])) <= 1e-9,
        "body_matrix_equal": b.matrix_error(primary_p0["model"]["matrix_world"], restored_p0["model"]["matrix_world"]) <= 1e-6,
    }
    restore = {"method": "explicit R_BASE generated after all diagnostic profiles", "checks": restore_checks,
               "geometry": restore_geometry, "passed": all(restore_checks.values())}
    result = {
        "schema": "enhanced-pose-determinism-v1",
        "fresh_canonical_process_per_profile": True,
        "case_count": len(cases),
        "cases": cases,
        "passed": len(cases) == 12 and all(item["passed"] for item in cases) and restore["passed"],
        "baseline_restore": restore,
        "scope": "beta=0 only",
    }
    b.write(root / "determinism_report.json", result)
    print(json.dumps({"passed": result["passed"], "baseline_restore": restore["passed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
