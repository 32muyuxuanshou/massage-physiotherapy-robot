#!/usr/bin/env python3
"""Verify A (zero), P (native pose), R (independent zero restoration) regression."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


EXPECTED_TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"
DORSAL = {"ENG_BACK_C7", "ENG_BACK_SCAPULA_L", "ENG_BACK_SCAPULA_R", "ENG_BACK_THORACIC_L", "ENG_BACK_THORACIC_R", "ENG_BACK_LUMBAR"}
VENTRAL = {"ENG_FRONT_CHEST", "ENG_FRONT_ABDOMEN"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _max_vector_delta(left, right) -> float:
    return max((math.dist(a, b) for a, b in zip(left, right)), default=0.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", required=True, type=Path)
    parser.add_argument("--p", required=True, type=Path)
    parser.add_argument("--r", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--independent-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    probes = {key: _load(path) for key, path in (("A", args.a), ("P", args.p), ("R", args.r))}
    fixture = _load(args.fixture)
    labels = _load(args.sample / "labels.json")
    independent = _load(args.independent_report)
    checks = []

    def add(check_id: str, passed: bool, message: str, metrics=None) -> None:
        item = {"id": check_id, "passed": bool(passed), "message": message}
        if metrics is not None:
            item["metrics"] = metrics
        checks.append(item)

    topology_ok = all(
        probe["model"]["vertex_count"] == 6890
        and probe["model"]["polygon_count"] == 13776
        and probe["model"]["topology_signature_sha256"] == EXPECTED_TOPOLOGY
        for probe in probes.values()
    )
    add("topology_stable", topology_ok, "A/P/R must retain the frozen 6890/13776 topology and signature.")

    fixture_map = {item["point_id"]: item for item in fixture["anchors"]}
    binding_ok = True
    for probe in probes.values():
        for point in probe["points"]:
            frozen = fixture_map.get(point["point_id"])
            binding_ok = binding_ok and frozen is not None and int(point["face_index"]) == int(frozen["face_index"]) and point["vertex_indices"] == frozen["vertex_indices"] and max(abs(float(a) - float(b)) for a, b in zip(point["barycentric"], frozen["barycentric"])) <= 1e-12
    add("frozen_bindings_not_reselected", binding_ok, "A/P/R must use the original fixed triangle and barycentric coordinates.")

    a_vertices, p_vertices, r_vertices = (probes[key]["world_vertices_m"] for key in ("A", "P", "R"))
    max_p_mesh_change = _max_vector_delta(a_vertices, p_vertices)
    max_r_mesh_error = _max_vector_delta(a_vertices, r_vertices)
    add("native_pose_changes_mesh", max_p_mesh_change >= 0.10, "Native pose must materially deform the skin mesh.", {"max_A_to_P_vertex_delta_m": max_p_mesh_change})
    add("zero_pose_restores_mesh", max_r_mesh_error <= 1e-7, "An independent zero-pose generation must restore the full A mesh.", {"max_A_to_R_vertex_error_m": max_r_mesh_error})

    point_maps = {key: {item["point_id"]: item for item in probe["points"]} for key, probe in probes.items()}
    dorsal_deltas = {point_id: math.dist(point_maps["A"][point_id]["xyz_world_m"], point_maps["P"][point_id]["xyz_world_m"]) for point_id in sorted(DORSAL)}
    shoulder_delta = max(dorsal_deltas["ENG_BACK_SCAPULA_L"], dorsal_deltas["ENG_BACK_SCAPULA_R"])
    add("shoulder_region_follows_pose", shoulder_delta >= 0.002, "At least one scapular-region anchor must move with the native shoulder pose.", {"dorsal_anchor_delta_m": dorsal_deltas})

    max_r_xyz = max(math.dist(point_maps["A"][point_id]["xyz_world_m"], point_maps["R"][point_id]["xyz_world_m"]) for point_id in point_maps["A"])
    max_r_uv = max(math.dist(point_maps["A"][point_id]["uv_pixel_opencv"], point_maps["R"][point_id]["uv_pixel_opencv"]) for point_id in point_maps["A"])
    add("zero_pose_restores_anchor_xyz_uv", max_r_xyz <= 1e-7 and max_r_uv <= 1e-4, "A/R anchor world coordinates and pixels must recover.", {"max_xyz_error_m": max_r_xyz, "max_uv_error_px": max_r_uv})

    p_dorsal_visible = all(point_maps["P"][point_id]["visible"] for point_id in DORSAL)
    p_ventral_hidden = all(not point_maps["P"][point_id]["visible"] for point_id in VENTRAL)
    add("pose_visibility_contract", p_dorsal_visible and p_ventral_hidden, "P must keep all dorsal anchors visible and both ventral controls invisible.", {"dorsal_visible": p_dorsal_visible, "ventral_hidden": p_ventral_hidden})

    camera_equal = probes["A"]["camera"] == probes["P"]["camera"] == probes["R"]["camera"]
    add("same_camera_contract", camera_equal, "A/P/R must share the exact frozen camera intrinsics/extrinsics.")
    rigid_transform_equal = probes["A"]["model"]["target_matrix_world"] == probes["P"]["model"]["target_matrix_world"] == probes["R"]["model"]["target_matrix_world"]
    add("same_rigid_prone_transform", rigid_transform_equal, "A/P/R must share the exact same rigid prone transform; pose-dependent auto-leveling is forbidden.")
    a_width = probes["A"]["bounds_world_m"]["max"][0] - probes["A"]["bounds_world_m"]["min"][0]
    p_width = probes["P"]["bounds_world_m"]["max"][0] - probes["P"]["bounds_world_m"]["min"][0]
    add("arms_lowered_from_t_pose", p_width <= a_width * 0.65, "The overhead body width must shrink materially when arms move from T-pose to alongside the torso.", {"A_width_m": a_width, "P_width_m": p_width, "ratio": p_width / a_width})

    p_min_z = probes["P"]["bounds_world_m"]["min"][2]
    bed_top = probes["P"]["bed"]["top_z_m"]
    add("body_above_bed", p_min_z >= bed_top - 1e-5 and p_min_z <= bed_top + 0.02, "P body must remain just above the bed plane, without sinking below it.", {"body_min_z_m": p_min_z, "bed_top_z_m": bed_top, "clearance_m": p_min_z - bed_top})
    ventral_height_changes = {
        point_id: abs(point_maps["P"][point_id]["xyz_world_m"][2] - point_maps["A"][point_id]["xyz_world_m"][2])
        for point_id in sorted(VENTRAL)
    }
    add(
        "torso_not_releveled_by_pose",
        max(ventral_height_changes.values()) <= 0.02,
        "Fixed chest/abdomen controls must not acquire a pose-dependent global height offset.",
        {"ventral_anchor_abs_z_change_m": ventral_height_changes},
    )

    label_map = {item["point_id"]: item for item in labels["points"]}
    sample_matches_probe = set(label_map) == set(point_maps["P"])
    if sample_matches_probe:
        for point_id in label_map:
            sample_matches_probe = sample_matches_probe and math.dist(label_map[point_id]["xyz_world_blender_m"], point_maps["P"][point_id]["xyz_world_m"]) <= 1e-6 and math.dist(label_map[point_id]["uv_pixel_opencv"], point_maps["P"][point_id]["uv_pixel_opencv"]) <= 1e-3 and bool(label_map[point_id]["visible"]) == bool(point_maps["P"][point_id]["visible"])
    add("export_matches_independent_pose_probe", sample_matches_probe, "P sample labels must match the independent snapshot probe.")
    add("independent_rgbd_replay_passed", independent.get("passed") is True, "P RGB-D sample must pass independent ray/depth/backprojection and exact replay verification.", independent.get("summary"))

    expected_pose = {"head_twist": 18.0, "shoulder_r_x": 80.0, "shoulder_r_y": 18.0, "elbow_flexion_r": 25.0, "shoulder_l_x": -80.0, "shoulder_l_y": -18.0, "elbow_flexion_l": 25.0}
    actual_pose = labels.get("scene", {}).get("native_pose_parameters_degrees", {})
    add("native_pose_profile_recorded", actual_pose == expected_pose, "labels must record the exact conservative native pose parameters.", {"actual": actual_pose, "expected": expected_pose})

    passed = all(item["passed"] for item in checks)
    report = {
        "schema": "skel-native-natural-prone-pose-regression-v1",
        "passed": passed,
        "medical_truth": False,
        "checks": checks,
        "summary": {"pass": sum(item["passed"] for item in checks), "fail": sum(not item["passed"] for item in checks)},
        "limitations": [
            "Natural-looking engineering pose, not clinician-approved positioning.",
            "No mattress deformation, face cradle, breathing, soft-tissue contact, or self-intersection solver.",
            "Shape parameters remain zero and no medical acupoints are used.",
        ],
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "summary": report["summary"], "output": str(args.output)}, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
