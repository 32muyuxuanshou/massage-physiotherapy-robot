from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
CROSS_WS = HERE.parent / "controlled_shape_pose_cross_validation_v1"
sys.path.insert(0, str(CROSS_WS))
import run_controlled_cross_validation as cross  # noqa: E402


AI_ROOT = cross.AI_ROOT
SOURCE_ROOT = AI_ROOT / "outputs" / "内部工程证据" / "2026-08-31_15-07-27_CONTROLLED_SHAPE_POSE_CROSS_VALIDATION_V1"
NARROW_PROBE = HERE / "narrow_phase_cluster_probe.py"
CLUSTER_RADIUS_M = 0.025
MATCH_RADIUS_M = 0.040
MATCH_SHARED_FACE_RADIUS_M = 0.065
MAX_DEPTH_INCREASE_M = 0.001
MAX_SEGMENT_INCREASE_M = 0.005
MAX_TOTAL_SEGMENT_INCREASE_M = 0.010
MIN_CLEARANCE_M = 0.003

LOW_BENCHMARKS = [
    "C03_LONG_NARROW__D06_THORAX_EXTENSION_P4",
    "C08_LOWER_PELVIS_WIDE__D03_HEAD_EXTENSION_P6",
    "C02_SHORT_NARROW_THIN__P3_ELBOW_22",
    "C06_THIN_NARROW__P3_ELBOW_22",
]
HIGH_BENCHMARKS = ["C05_THICK_UPPER_WIDE__D07_THORAX_TWIST_P4"]
REPEAT_CASES = [
    "S0_BASE__P0_BASE",
    "C03_LONG_NARROW__P0_BASE",
    "S0_BASE__D01_SCAPULA_ABDUCTION_PAIR_P6",
    LOW_BENCHMARKS[0],
    HIGH_BENCHMARKS[0],
]
SEARCH_SHAPES = ["C02_SHORT_NARROW_THIN", "C03_LONG_NARROW", "C06_THIN_NARROW"]
SEARCH_POSES = [
    "P2_HEAD_POS35", "P3_ELBOW_22", "P4_ARMS_SLIGHTLY_OPEN",
    "D01_SCAPULA_ABDUCTION_PAIR_P6", "D03_HEAD_EXTENSION_P6", "D06_THORAX_EXTENSION_P4",
]
SEARCH_CALIBRATION_CASES = {
    "C03_LONG_NARROW__D06_THORAX_EXTENSION_P4",
    "C02_SHORT_NARROW_THIN__P3_ELBOW_22",
    "C06_THIN_NARROW__P3_ELBOW_22",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return cross.sha256(path)


def source_config() -> dict:
    return read_json(SOURCE_ROOT / "shape_pose_cross_config_v1.json")


def controls() -> list[dict]:
    return [cell for cell in source_config()["cells"] if cell["kind"] != "novel_interaction"]


def by_id() -> dict[str, dict]:
    return {cell["case_id"]: cell for cell in source_config()["cells"]}


def prepare(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if not SOURCE_ROOT.is_dir():
        raise RuntimeError(f"Missing frozen Cross source: {SOURCE_ROOT}")
    required = [
        SOURCE_ROOT / "shape_pose_cross_config_v1.json",
        SOURCE_ROOT / "geometry_preflight_report.json",
        SOURCE_ROOT / "interaction_residual_report.json",
        SOURCE_ROOT / "engineering_fixture_manual20.json",
        SOURCE_ROOT / "body_measurement_contract_v2.json",
        SOURCE_ROOT / "fixed_prone_light_contract_v1.json",
        cross.ATLAS,
    ]
    if not all(path.is_file() for path in required):
        raise RuntimeError("Frozen Cross evidence is incomplete")
    selected_ids = (
        {cell["case_id"] for cell in controls()}
        | set(LOW_BENCHMARKS)
        | set(HIGH_BENCHMARKS)
        | {f"{shape_id}__{pose_id}" for shape_id in SEARCH_SHAPES for pose_id in SEARCH_POSES}
    )
    for name in ("engineering_fixture_manual20.json", "body_measurement_contract_v2.json", "fixed_prone_light_contract_v1.json"):
        shutil.copy2(SOURCE_ROOT / name, root / name)
    shutil.copy2(cross.ATLAS, root / "source_atlas_v5.json")
    for identifier in sorted(selected_ids):
        target = root / "profiles" / f"{identifier}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE_ROOT / "profiles" / f"{identifier}.json", target)
    contract = {
        "schema": "cross-gate-reconciliation-contract-v1",
        "medical_truth": False,
        "source_cross_root": str(SOURCE_ROOT),
        "control_cell_count": len(controls()),
        "low_benchmark_cases": LOW_BENCHMARKS,
        "high_benchmark_cases": HIGH_BENCHMARKS,
        "restricted_search": {
            "shape_ids": SEARCH_SHAPES,
            "pose_ids": SEARCH_POSES,
            "cell_count": len(SEARCH_SHAPES) * len(SEARCH_POSES),
            "calibration_seen_case_ids": sorted(SEARCH_CALIBRATION_CASES),
            "heldout_case_count": len(SEARCH_SHAPES) * len(SEARCH_POSES) - len(SEARCH_CALIBRATION_CASES),
        },
        "bvh_pairs_retained_as_raw_evidence": True,
        "narrow_phase": {
            "epsilon_m": 1e-7,
            "confirmed_types": ["NONCOPLANAR_SEGMENT", "COPLANAR_AREA"],
            "point_contact_is_reported_not_confirmed": True,
            "cluster_radius_m": CLUSTER_RADIUS_M,
        },
        "cluster_matching": {
            "center_radius_m": MATCH_RADIUS_M,
            "shared_face_center_radius_m": MATCH_SHARED_FACE_RADIUS_M,
            "same_coarse_region_required_without_shared_face": True,
            "severity_warning": {
                "max_crossing_depth_increase_m": MAX_DEPTH_INCREASE_M,
                "max_segment_increase_m": MAX_SEGMENT_INCREASE_M,
                "total_segment_increase_m": MAX_TOTAL_SEGMENT_INCREASE_M,
            },
        },
        "hard_gates": {
            "bed_clearance_m_min": MIN_CLEARANCE_M,
            "confirmed_ring2_pair_count_max": 0,
            "control_chain_and_topology_required": True,
        },
        "novel_parent_rule": "A novel cell may be QUALIFIED only when both its Shape-only and Pose-only controls are CROSS_QUALIFIED.",
        "not_claimed": ["physical penetration depth", "soft-tissue contact", "medical validity", "continuous parameter-space safety"],
    }
    write_json(root / "overlap_cluster_contract_v1.json", contract)
    inputs = {str(path): sha256(path) for path in required}
    inputs.update({
        str(HERE / "triangle_narrow_phase.py"): sha256(HERE / "triangle_narrow_phase.py"),
        str(NARROW_PROBE): sha256(NARROW_PROBE),
        str(Path(__file__).resolve()): sha256(Path(__file__).resolve()),
    })
    write_json(root / "input_manifest.json", {"schema": "cross-gate-reconciliation-input-manifest-v1", "files": inputs})
    write_json(root / "source_hashes_before.json", cross.protected_sources())


def run_case(root: Path, phase: str, cell: dict, output_id: str, temp_parent: Path) -> dict:
    phase_root = root / phase
    probe_path = phase_root / "probes" / f"{output_id}.json"
    narrow_path = phase_root / "narrow" / f"{output_id}.json"
    meta_path = phase_root / "meta" / f"{output_id}.json"
    preview_path = phase_root / "previews" / f"{output_id}.png"
    overlay_path = phase_root / "overlays" / f"{output_id}.png"
    for path in (probe_path, narrow_path, meta_path, preview_path, overlay_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    if all(path.is_file() for path in (probe_path, narrow_path, meta_path, preview_path, overlay_path)):
        return read_json(meta_path)

    profile_path = root / "profiles" / f"{cell['case_id']}.json"
    profile = read_json(profile_path)
    temp_case = temp_parent / output_id
    native = temp_case / "native"
    snapshot = temp_case / f"{output_id}.blend"
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
    cross.shared.bj(snapshot, cross.SHAPE_PROBE, [
        "--atlas", root / "source_atlas_v5.json",
        "--contract", root / "body_measurement_contract_v2.json",
        "--profile", profile_path, "--native-parameters", native / "parameters.json",
        "--core-parent", cross.shared.CORE_PARENT, "--output", probe_path, "--width", 1280, "--height", 1024,
    ], "ACU_SHAPE_COMBINATION_PROBE=PASS")
    cross.shared.bj(snapshot, NARROW_PROBE, [
        "--atlas", root / "source_atlas_v5.json", "--output", narrow_path,
        "--qa-root", cross.QA_WS, "--epsilon", "1e-7", "--cluster-radius", str(CLUSTER_RADIUS_M),
    ], "ACU_NARROW_PHASE_CLUSTER_PROBE=PASS")
    cross.shared.bj(snapshot, cross.shared.RENDER, [preview_path], "ACU_NATURAL_PRONE_PREVIEW=PASS")
    probe = read_json(probe_path)
    cross.shared.overlay_from_probe(preview_path, probe, overlay_path)
    native_parameters = read_json(native / "parameters.json")
    meta = {
        "schema": "cross-gate-reconciliation-case-meta-v1",
        "medical_truth": False,
        "output_id": output_id,
        "case_id": cell["case_id"],
        "shape_id": cell["shape_id"],
        "pose_id": cell["pose_id"],
        "kind": cell["kind"],
        "profile_sha256": sha256(profile_path),
        "native_hashes": {name: sha256(native / name) for name in ("parameters.json", "skin_female.obj", "skeleton_female.obj", "joints_female.json")},
        "control_chain": cross.control_chain(profile, native_parameters, probe),
        "topology_ok": probe["model"]["topology_signature_sha256"] == cross.EXPECTED_TOPOLOGY and probe["model"]["vertex_count"] == 6890 and probe["model"]["face_count"] == 13776,
        "bed_clearance_m": float(probe["bed"]["minimum_body_clearance_m"]),
        "probe": str(probe_path.relative_to(root)),
        "narrow": str(narrow_path.relative_to(root)),
        "preview": str(preview_path.relative_to(root)),
        "overlay": str(overlay_path.relative_to(root)),
    }
    write_json(meta_path, meta)
    return meta


def run_group(root: Path, phase: str, cells: list[dict]) -> None:
    prepare(root)
    with tempfile.TemporaryDirectory(prefix=f"acu_{phase}_") as temporary_name:
        temporary = Path(temporary_name)
        for index, cell in enumerate(cells, start=1):
            run_case(root, phase, cell, cell["case_id"], temporary)
            write_json(root / f"{phase}_progress.json", {"completed": index, "total": len(cells), "last_case": cell["case_id"]})
            print(f"{phase.upper()} {index}/{len(cells)} {cell['case_id']}", flush=True)


def cluster_match(current: dict, references: list[dict]) -> dict | None:
    current_center = np.asarray(current["center_local_m"], dtype=np.float64)
    current_faces = set(current["face_indices"])
    candidates = []
    for reference in references:
        reference_center = np.asarray(reference["center_local_m"], dtype=np.float64)
        distance = float(np.linalg.norm(current_center - reference_center))
        face_overlap = len(current_faces.intersection(reference["face_indices"]))
        same_region = current["coarse_region"] == reference["coarse_region"]
        eligible = (face_overlap > 0 and distance <= MATCH_SHARED_FACE_RADIUS_M) or (same_region and distance <= MATCH_RADIUS_M)
        if eligible:
            candidates.append((distance - min(face_overlap, 5) * 0.001, distance, face_overlap, reference))
    if not candidates:
        return None
    _, distance, face_overlap, reference = min(candidates, key=lambda item: item[0])
    depth_delta = float(current["max_crossing_depth_proxy_m"] - reference["max_crossing_depth_proxy_m"])
    segment_delta = float(current["max_segment_length_m"] - reference["max_segment_length_m"])
    total_delta = float(current["total_segment_length_m"] - reference["total_segment_length_m"])
    return {
        "reference_cluster_id": reference["cluster_id"],
        "center_distance_m": distance,
        "shared_face_count": face_overlap,
        "same_region": current["coarse_region"] == reference["coarse_region"],
        "max_crossing_depth_delta_m": depth_delta,
        "max_segment_delta_m": segment_delta,
        "total_segment_delta_m": total_delta,
        "severity_escalation": depth_delta > MAX_DEPTH_INCREASE_M or segment_delta > MAX_SEGMENT_INCREASE_M or total_delta > MAX_TOTAL_SEGMENT_INCREASE_M,
    }


def evaluate_against_references(meta: dict, narrow: dict, references: list[dict]) -> dict:
    clusters = narrow["clusters"]
    matches, new_clusters, escalations = [], [], []
    for cluster in clusters:
        match = cluster_match(cluster, references)
        if match is None:
            new_clusters.append(cluster)
        else:
            record = {"cluster_id": cluster["cluster_id"], **match}
            matches.append(record)
            if match["severity_escalation"]:
                escalations.append(record)
    ring2_count = int(narrow["narrow_phase"]["confirmed_ring2_pair_count"])
    system_ok = bool(meta["control_chain"]["passed"] and meta["topology_ok"])
    if not system_ok:
        status = "ERROR_CONTROL_OR_TOPOLOGY"
    elif meta["bed_clearance_m"] < MIN_CLEARANCE_M:
        status = "REJECT_BED_CLEARANCE"
    elif ring2_count > 0:
        status = "REJECT_CONFIRMED_RING2_INTERSECTION"
    elif any(cluster["intersects_ring3"] for cluster in new_clusters):
        status = "CAUTION_NEW_RING3_CLUSTER"
    elif new_clusters:
        status = "CAUTION_NEW_GLOBAL_CLUSTER"
    elif escalations:
        status = "CAUTION_MATCHED_CLUSTER_SEVERITY_ESCALATION"
    else:
        status = "CROSS_QUALIFIED"
    return {
        "status": status,
        "system_ok": system_ok,
        "bed_clearance_m": meta["bed_clearance_m"],
        "confirmed_ring2_pair_count": ring2_count,
        "confirmed_ring3_pair_count": int(narrow["narrow_phase"]["confirmed_ring3_pair_count"]),
        "bvh_candidate_pair_count": int(narrow["bvh"]["nonadjacent_candidate_pair_count"]),
        "narrow_confirmed_pair_count": int(narrow["narrow_phase"]["confirmed_overlap_pair_count"]),
        "contact_only_pair_count": int(narrow["narrow_phase"]["contact_only_pair_count"]),
        "unconfirmed_candidate_pair_count": int(narrow["narrow_phase"]["unconfirmed_candidate_pair_count"]),
        "cluster_count": len(clusters),
        "matched_cluster_count": len(matches),
        "new_cluster_count": len(new_clusters),
        "new_clusters": new_clusters,
        "matches": matches,
        "severity_escalation_count": len(escalations),
        "severity_escalations": escalations,
    }


def load_case(root: Path, phase: str, identifier: str) -> tuple[dict, dict, dict]:
    return (
        read_json(root / phase / "meta" / f"{identifier}.json"),
        read_json(root / phase / "probes" / f"{identifier}.json"),
        read_json(root / phase / "narrow" / f"{identifier}.json"),
    )


def montage(root: Path, phase: str, identifiers: list[str], statuses: dict[str, str], output: Path, columns: int) -> None:
    thumb = (320, 256)
    rows = math.ceil(len(identifiers) / columns)
    cell_h = thumb[1] + 34
    canvas = Image.new("RGB", (columns * thumb[0], rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, identifier in enumerate(identifiers):
        with Image.open(root / phase / "overlays" / f"{identifier}.png") as source:
            image = source.convert("RGB")
            image.thumbnail(thumb, Image.Resampling.LANCZOS)
        x, y = (index % columns) * thumb[0], (index // columns) * cell_h
        canvas.paste(image, (x + (thumb[0] - image.width) // 2, y + 30))
        status = statuses.get(identifier, "UNCLASSIFIED")
        color = (40, 165, 85) if status == "CROSS_QUALIFIED" else (235, 160, 35) if status.startswith("CAUTION") or status == "PARENT_NOT_CROSS_QUALIFIED" else (210, 55, 55)
        draw.rectangle((x + 1, y + 1, x + thumb[0] - 2, y + cell_h - 2), outline=color, width=3)
        draw.text((x + 5, y + 5), identifier[:42], fill="black", font=font)
        draw.text((x + 5, y + 17), status, fill=color, font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def analyze_controls(root: Path) -> dict:
    baseline_id = "S0_BASE__P0_BASE"
    baseline_meta, _, baseline_narrow = load_case(root, "controls", baseline_id)
    baseline_references = baseline_narrow["clusters"]
    rows = []
    for cell in controls():
        meta, _, narrow = load_case(root, "controls", cell["case_id"])
        analysis = evaluate_against_references(meta, narrow, [] if cell["case_id"] == baseline_id else baseline_references)
        if cell["case_id"] == baseline_id and analysis["system_ok"] and analysis["bed_clearance_m"] >= MIN_CLEARANCE_M and analysis["confirmed_ring2_pair_count"] == 0:
            analysis["status"] = "CROSS_QUALIFIED"
        rows.append({**cell, **analysis})
    report = {
        "schema": "cross-gate-control-reconciliation-v1",
        "medical_truth": False,
        "passed": len(rows) == 15 and not any(row["status"].startswith("ERROR") for row in rows),
        "baseline_cluster_count": len(baseline_references),
        "controls": rows,
    }
    write_json(root / "control_reconciliation_report.json", report)
    status_map = {row["case_id"]: row["status"] for row in rows}
    montage(root, "controls", [cell["case_id"] for cell in controls()], status_map, root / "control_reconciliation_montage.png", 5)
    with (root / "control_reconciliation_matrix.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["case_id", "shape_id", "pose_id", "kind", "status", "bed_clearance_m", "bvh_candidate_pair_count", "narrow_confirmed_pair_count", "contact_only_pair_count", "unconfirmed_candidate_pair_count", "cluster_count", "matched_cluster_count", "new_cluster_count", "severity_escalation_count", "confirmed_ring2_pair_count", "confirmed_ring3_pair_count"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})
    return report


def analyze_benchmarks(root: Path, control_report: dict) -> dict:
    control_by_id = {row["case_id"]: row for row in control_report["controls"]}
    rows = []
    config_by_id = by_id()
    for identifier in LOW_BENCHMARKS + HIGH_BENCHMARKS:
        cell = config_by_id[identifier]
        shape_parent_id = f"{cell['shape_id']}__P0_BASE"
        pose_parent_id = f"S0_BASE__{cell['pose_id']}"
        shape_parent = control_by_id[shape_parent_id]
        pose_parent = control_by_id[pose_parent_id]
        meta, _, narrow = load_case(root, "benchmarks", identifier)
        _, _, shape_narrow = load_case(root, "controls", shape_parent_id)
        _, _, pose_narrow = load_case(root, "controls", pose_parent_id)
        parent_refs = shape_narrow["clusters"] + pose_narrow["clusters"]
        analysis = evaluate_against_references(meta, narrow, parent_refs)
        parents_qualified = shape_parent["status"] == "CROSS_QUALIFIED" and pose_parent["status"] == "CROSS_QUALIFIED"
        geometric_status = analysis["status"]
        if not parents_qualified:
            analysis["status"] = "PARENT_NOT_CROSS_QUALIFIED"
        rows.append({
            **cell,
            **analysis,
            "geometric_status_before_parent_rule": geometric_status,
            "shape_parent_id": shape_parent_id,
            "shape_parent_status": shape_parent["status"],
            "pose_parent_id": pose_parent_id,
            "pose_parent_status": pose_parent["status"],
            "parents_cross_qualified": parents_qualified,
            "benchmark_group": "LOW" if identifier in LOW_BENCHMARKS else "HIGH",
        })
    report = {
        "schema": "cross-gate-overlap-benchmark-v1",
        "medical_truth": False,
        "passed": len(rows) == len(LOW_BENCHMARKS) + len(HIGH_BENCHMARKS) and not any(row["status"].startswith("ERROR") for row in rows),
        "parent_inheritance_rule_enforced": True,
        "benchmarks": rows,
    }
    write_json(root / "overlap_benchmark_report.json", report)
    montage(root, "benchmarks", [row["case_id"] for row in rows], {row["case_id"]: row["status"] for row in rows}, root / "overlap_benchmark_montage.png", 3)
    return report


def compare_repeat(first: dict, second: dict) -> dict:
    scalar_paths = [
        ("bvh", "nonadjacent_candidate_pair_count"),
        ("narrow_phase", "confirmed_overlap_pair_count"),
        ("narrow_phase", "contact_only_pair_count"),
        ("narrow_phase", "unconfirmed_candidate_pair_count"),
    ]
    scalars_equal = all(first[a][b] == second[a][b] for a, b in scalar_paths)
    candidates_equal = first["bvh"]["candidate_pairs"] == second["bvh"]["candidate_pairs"]
    confirmed_equal = [row["faces"] for row in first["narrow_phase"]["confirmed_pairs"]] == [row["faces"] for row in second["narrow_phase"]["confirmed_pairs"]]
    clusters_equal = first["clusters"] == second["clusters"]
    return {"passed": scalars_equal and candidates_equal and confirmed_equal and clusters_equal, "scalars_equal": scalars_equal, "candidate_pairs_equal": candidates_equal, "confirmed_faces_equal": confirmed_equal, "clusters_exactly_equal": clusters_equal}


def run_determinism(root: Path) -> None:
    prepare(root)
    config = by_id()
    with tempfile.TemporaryDirectory(prefix="acu_reconcile_repeat_") as temporary_name:
        temporary = Path(temporary_name)
        for index, identifier in enumerate(REPEAT_CASES, start=1):
            run_case(root, "determinism", config[identifier], identifier, temporary)
            print(f"DETERMINISM {index}/{len(REPEAT_CASES)} {identifier}", flush=True)
        run_case(root, "determinism", config["S0_BASE__P0_BASE"], "R_BASE", temporary)
    rows = []
    for identifier in REPEAT_CASES:
        source_phase = "controls" if config[identifier]["kind"] != "novel_interaction" else "benchmarks"
        _, _, primary = load_case(root, source_phase, identifier)
        _, _, replay = load_case(root, "determinism", identifier)
        rows.append({"case_id": identifier, **compare_repeat(primary, replay)})
    _, _, base = load_case(root, "controls", "S0_BASE__P0_BASE")
    _, _, restored = load_case(root, "determinism", "R_BASE")
    restore = compare_repeat(base, restored)
    report = {"schema": "cross-gate-reconciliation-determinism-v1", "passed": all(row["passed"] for row in rows) and restore["passed"], "fresh_native_and_blender_process": True, "cases": rows, "baseline_restore": restore}
    write_json(root / "determinism_report.json", report)
    if not report["passed"]:
        raise SystemExit(3)


def search_cells() -> list[dict]:
    config = by_id()
    return [config[f"{shape_id}__{pose_id}"] for shape_id in SEARCH_SHAPES for pose_id in SEARCH_POSES]


def analyze_search(root: Path) -> dict:
    control_report = analyze_controls(root)
    control_by_id = {row["case_id"]: row for row in control_report["controls"]}
    rows = []
    for cell in search_cells():
        identifier = cell["case_id"]
        shape_parent_id = f"{cell['shape_id']}__P0_BASE"
        pose_parent_id = f"S0_BASE__{cell['pose_id']}"
        shape_parent, pose_parent = control_by_id[shape_parent_id], control_by_id[pose_parent_id]
        meta, _, narrow = load_case(root, "search", identifier)
        _, _, shape_narrow = load_case(root, "controls", shape_parent_id)
        _, _, pose_narrow = load_case(root, "controls", pose_parent_id)
        analysis = evaluate_against_references(meta, narrow, shape_narrow["clusters"] + pose_narrow["clusters"])
        parents_qualified = shape_parent["status"] == "CROSS_QUALIFIED" and pose_parent["status"] == "CROSS_QUALIFIED"
        geometric_status = analysis["status"]
        if not parents_qualified:
            analysis["status"] = "PARENT_NOT_CROSS_QUALIFIED"
        rows.append({
            **cell,
            **analysis,
            "geometric_status_before_parent_rule": geometric_status,
            "shape_parent_status": shape_parent["status"],
            "pose_parent_status": pose_parent["status"],
            "parents_cross_qualified": parents_qualified,
            "calibration_seen": identifier in SEARCH_CALIBRATION_CASES,
        })
    report = {
        "schema": "cross-qualified-parent-restricted-search-v1",
        "medical_truth": False,
        "passed": len(rows) == 18 and not any(row["status"].startswith("ERROR") for row in rows),
        "cell_count": len(rows),
        "calibration_seen_count": sum(row["calibration_seen"] for row in rows),
        "heldout_count": sum(not row["calibration_seen"] for row in rows),
        "qualified_count": sum(row["status"] == "CROSS_QUALIFIED" for row in rows),
        "qualified_heldout_count": sum(row["status"] == "CROSS_QUALIFIED" and not row["calibration_seen"] for row in rows),
        "cells": rows,
    }
    write_json(root / "restricted_search_report.json", report)
    montage(root, "search", [row["case_id"] for row in rows], {row["case_id"]: row["status"] for row in rows}, root / "restricted_search_montage.png", 6)
    with (root / "restricted_search_matrix.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["case_id", "shape_id", "pose_id", "status", "calibration_seen", "bed_clearance_m", "bvh_candidate_pair_count", "narrow_confirmed_pair_count", "cluster_count", "matched_cluster_count", "new_cluster_count", "severity_escalation_count", "confirmed_ring2_pair_count", "confirmed_ring3_pair_count"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})
    return report


def run_search_determinism(root: Path) -> None:
    report = read_json(root / "restricted_search_report.json")
    config = by_id()
    with tempfile.TemporaryDirectory(prefix="acu_restricted_search_repeat_") as temporary_name:
        temporary = Path(temporary_name)
        for index, row in enumerate(report["cells"], start=1):
            identifier = row["case_id"]
            run_case(root, "search_determinism", config[identifier], identifier, temporary)
            print(f"SEARCH_DETERMINISM {index}/{len(report['cells'])} {identifier}", flush=True)
    rows = []
    for row in report["cells"]:
        identifier = row["case_id"]
        _, _, primary = load_case(root, "search", identifier)
        _, _, replay = load_case(root, "search_determinism", identifier)
        rows.append({"case_id": identifier, "status": row["status"], **compare_repeat(primary, replay)})
    payload = {
        "schema": "restricted-shape-pose-search-determinism-v1",
        "passed": len(rows) == 18 and all(row["passed"] for row in rows),
        "fresh_native_and_blender_process_per_cell": True,
        "cells": rows,
    }
    write_json(root / "restricted_search_determinism_report.json", payload)
    if not payload["passed"]:
        raise SystemExit(5)


def finalize_search(root: Path) -> None:
    reconciliation = read_json(root / "verification.json")
    search = analyze_search(root)
    determinism = read_json(root / "restricted_search_determinism_report.json")
    source_unchanged = read_json(root / "source_hashes_before.json") == cross.protected_sources()
    qualified = [row for row in search["cells"] if row["status"] == "CROSS_QUALIFIED"]
    cautions = [row for row in search["cells"] if row["status"] != "CROSS_QUALIFIED"]
    write_json(root / "CROSS_QUALIFIED_SHAPE_POSE_SEARCH_V1.json", {
        "schema": "cross-qualified-shape-pose-search-v1",
        "medical_truth": False,
        "scope": "3 cross-qualified nonbaseline Shapes x 6 cross-qualified nonbaseline Poses; fixed prone scene and cluster gate v1",
        "combination_count": len(qualified),
        "heldout_combination_count": sum(not row["calibration_seen"] for row in qualified),
        "combinations": [{
            "case_id": row["case_id"], "shape_id": row["shape_id"], "pose_id": row["pose_id"],
            "calibration_seen": row["calibration_seen"], "status": row["status"],
            "bed_clearance_m": row["bed_clearance_m"], "cluster_count": row["cluster_count"],
        } for row in qualified],
        "not_claimed": ["continuous parameter-space safety", "medical validity", "global zero self-intersection", "real soft-tissue contact"],
    })
    write_json(root / "restricted_search_cautions.json", {
        "schema": "restricted-shape-pose-search-cautions-v1", "medical_truth": False,
        "count": len(cautions),
        "cells": [{"case_id": row["case_id"], "status": row["status"], "new_cluster_count": row["new_cluster_count"], "severity_escalation_count": row["severity_escalation_count"]} for row in cautions],
    })
    verification = {
        "schema": "restricted-shape-pose-search-verification-v1",
        "passed": bool(reconciliation["passed"] and search["passed"] and determinism["passed"] and source_unchanged and search["qualified_heldout_count"] > 0),
        "matrix_cells": 18,
        "calibration_seen_cells": search["calibration_seen_count"],
        "heldout_cells": search["heldout_count"],
        "qualified_count": len(qualified),
        "qualified_heldout_count": search["qualified_heldout_count"],
        "caution_count": len(cautions),
        "determinism_passed": determinism["passed"],
        "protected_sources_unchanged": source_unchanged,
        "next_gate": "Qualified cells may proceed to fixed-camera RGB-D replay before any camera diversity or Pilot expansion.",
        "truth_status": {"kind": "ENGINEERING_QA", "medical_truth": False, "medical_validated": False},
    }
    write_json(root / "restricted_search_verification.json", verification)
    lines = [
        "# CROSS_GATE_RECONCILIATION_V1 + RESTRICTED_SEARCH", "",
        f"统一门禁：**{'PASS' if reconciliation['passed'] else 'FAIL'}**。受限18格搜索：**{'PASS' if verification['passed'] else 'FAIL'}**。", "",
        f"- 18格中合格：{len(qualified)}",
        f"- 15个未参与校准的留出格中合格：{search['qualified_heldout_count']}",
        f"- CAUTION：{len(cautions)}",
        "- 下一步只能对合格格做固定相机 RGB-D 重放，不得直接扩到 Camera diversity 或 300–500 Pilot。",
        "- 结果仍是工程几何 QA，不是医学或机器人安全结论。",
    ]
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = build_manifest(root)
    print(json.dumps({"SEARCH_FINAL": "PASS" if verification["passed"] else "FAIL", **result, "qualified": len(qualified), "qualified_heldout": search["qualified_heldout_count"]}, ensure_ascii=False), flush=True)
    if not verification["passed"]:
        raise SystemExit(6)


def qualified_search_cells(root: Path) -> list[dict]:
    frozen = read_json(root / "CROSS_QUALIFIED_SHAPE_POSE_SEARCH_V1.json")
    config = by_id()
    return [config[item["case_id"]] for item in frozen["combinations"]]


def run_search_rgbd(root: Path) -> None:
    verification = read_json(root / "restricted_search_verification.json")
    if not verification["passed"]:
        raise RuntimeError("Restricted search must pass before fixed-camera RGB-D replay")
    cells = qualified_search_cells(root)
    results = []
    with tempfile.TemporaryDirectory(prefix="acu_restricted_rgbd_") as temporary_name:
        temporary = Path(temporary_name)
        for index, cell in enumerate(cells, start=1):
            identifier = cell["case_id"]
            cross.run_case(root, "restricted_rgbd", cell, identifier, temporary, export_rgbd=True)
            meta, probe, geometry = cross.load_case(root, "restricted_rgbd", identifier)
            _, search_probe, search_narrow = load_case(root, "search", identifier)
            probe_replay = cross.shared.compare_probes(search_probe, probe)
            candidate_pairs_equal = (
                geometry["geometry"]["global_nonadjacent_overlap_pairs"]
                == search_narrow["bvh"]["candidate_pairs"]
            )
            qc = read_json(root / "restricted_rgbd" / "qc" / f"{identifier}.json")
            passed = bool(meta.get("qc_passed") and probe_replay["passed"] and candidate_pairs_equal)
            results.append({
                "case_id": identifier,
                "passed": passed,
                "qc": qc,
                "probe_replay_against_restricted_search": probe_replay,
                "bvh_candidate_pairs_equal": candidate_pairs_equal,
                "sample": str((root / "restricted_rgbd" / "samples" / identifier).relative_to(root)),
            })
            write_json(root / "restricted_rgbd_progress.json", {
                "completed": index, "total": len(cells), "last_case": identifier,
            })
            print(f"RESTRICTED_RGBD {index}/{len(cells)} {identifier}: {'PASS' if passed else 'FAIL'}", flush=True)
    report = {
        "schema": "restricted-shape-pose-fixed-camera-rgbd-v1",
        "medical_truth": False,
        "passed": len(results) == len(cells) and all(item["passed"] for item in results),
        "qualified_input_count": len(cells),
        "fixed_camera_and_scene": True,
        "rgb_exact_hash_required": False,
        "geometry_depth_valid_skin_masks_are_hard_gates": True,
        "cases": results,
    }
    write_json(root / "restricted_rgbd_report.json", report)
    if not report["passed"]:
        raise SystemExit(7)


def run_search_rgbd_determinism(root: Path) -> None:
    rgbd = read_json(root / "restricted_rgbd_report.json")
    if not rgbd["passed"]:
        raise RuntimeError("Fixed-camera RGB-D replay must pass before determinism")
    config = by_id()
    results = []
    with tempfile.TemporaryDirectory(prefix="acu_restricted_rgbd_repeat_") as temporary_name:
        temporary = Path(temporary_name)
        for index, primary in enumerate(rgbd["cases"], start=1):
            identifier = primary["case_id"]
            cross.run_case(
                root, "restricted_rgbd_determinism", config[identifier], identifier,
                temporary, export_rgbd=True, temporary_sample=True,
            )
            _, probe, geometry = cross.load_case(root, "restricted_rgbd_determinism", identifier)
            _, primary_probe, primary_geometry = cross.load_case(root, "restricted_rgbd", identifier)
            probe_replay = cross.shared.compare_probes(primary_probe, probe)
            candidate_pairs_equal = (
                primary_geometry["geometry"]["global_nonadjacent_overlap_pairs"]
                == geometry["geometry"]["global_nonadjacent_overlap_pairs"]
            )
            buffers = cross.compare_buffers(
                root / "restricted_rgbd" / "samples" / identifier,
                temporary / identifier / "sample",
            )
            qc = read_json(root / "restricted_rgbd_determinism" / "qc" / f"{identifier}.json")
            passed = bool(probe_replay["passed"] and candidate_pairs_equal and buffers["passed"] and qc["passed"])
            results.append({
                "case_id": identifier,
                "passed": passed,
                "probe_replay": probe_replay,
                "bvh_candidate_pairs_equal": candidate_pairs_equal,
                "buffers": buffers,
                "qc": qc,
            })
            write_json(root / "restricted_rgbd_determinism_progress.json", {
                "completed": index, "total": len(rgbd["cases"]), "last_case": identifier,
            })
            print(f"RESTRICTED_RGBD_DETERMINISM {index}/{len(rgbd['cases'])} {identifier}: {'PASS' if passed else 'FAIL'}", flush=True)
    report = {
        "schema": "restricted-shape-pose-fixed-camera-rgbd-determinism-v1",
        "medical_truth": False,
        "passed": len(results) == len(rgbd["cases"]) and all(item["passed"] for item in results),
        "fresh_native_generation_and_blender_process_per_case": True,
        "rgb_exact_hash_reported_not_required": True,
        "cases": results,
    }
    write_json(root / "restricted_rgbd_determinism_report.json", report)
    if not report["passed"]:
        raise SystemExit(8)


def finalize_search_rgbd(root: Path) -> None:
    search = read_json(root / "restricted_search_verification.json")
    rgbd = read_json(root / "restricted_rgbd_report.json")
    determinism = read_json(root / "restricted_rgbd_determinism_report.json")
    source_unchanged = read_json(root / "source_hashes_before.json") == cross.protected_sources()
    cases = rgbd["cases"]
    max_depth = max(float(item["qc"]["max_depth_error_m"]) for item in cases)
    max_backprojection = max(float(item["qc"]["max_backprojection_error_m"]) for item in cases)
    verification = {
        "schema": "restricted-shape-pose-fixed-camera-rgbd-verification-v1",
        "passed": bool(search["passed"] and rgbd["passed"] and determinism["passed"] and source_unchanged),
        "qualified_input_count": len(cases),
        "rgbd_passed_count": sum(bool(item["passed"]) for item in cases),
        "determinism_passed": determinism["passed"],
        "maximum_depth_error_m": max_depth,
        "maximum_backprojection_error_m": max_backprojection,
        "protected_sources_unchanged": source_unchanged,
        "scope": "fixed prone scene, fixed camera, 20 non-medical engineering points",
        "next_gate": "Camera diversity remains a separate future gate; this result only freezes fixed-camera RGB-D replay for 17 discrete combinations.",
        "truth_status": {"kind": "ENGINEERING_QA", "medical_truth": False, "medical_validated": False},
    }
    write_json(root / "restricted_rgbd_verification.json", verification)
    lines = [
        "# CROSS_GATE_RECONCILIATION_V1 + RESTRICTED_SEARCH + FIXED_CAMERA_RGBD", "",
        f"统一门禁：**{'PASS' if read_json(root / 'verification.json')['passed'] else 'FAIL'}**。",
        f"受限18格搜索：**{'PASS' if search['passed'] else 'FAIL'}**，17格合格、1格 CAUTION。",
        f"17格固定相机 RGB-D：**{'PASS' if verification['passed'] else 'FAIL'}**。", "",
        f"- 最大 Depth 误差：{max_depth * 1000.0:.3f} mm",
        f"- 最大反投影误差：{max_backprojection * 1000.0:.3f} mm",
        "- Depth / Valid Mask / Skin Mask 的确定性是硬门禁；Eevee RGB 精确哈希只记录、不作为硬门禁。",
        "- 当前只证明离散 Shape×Pose 在固定相机俯卧工程场景中的几何与数据合同。",
        "- 不代表连续参数空间安全、全身零自交、医学有效或机器人接触安全。",
    ]
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = build_manifest(root)
    print(json.dumps({"RESTRICTED_RGBD_FINAL": "PASS" if verification["passed"] else "FAIL", **result, "cases": len(cases)}, ensure_ascii=False), flush=True)
    if not verification["passed"]:
        raise SystemExit(9)


def build_manifest(root: Path) -> dict:
    manifest = root / "SHA256SUMS.txt"
    rows = [f"{sha256(path)}  {path.relative_to(root).as_posix()}" for path in sorted(root.rglob("*")) if path.is_file() and path != manifest]
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"entries": len(rows), "manifest_sha256": sha256(manifest)}


def finalize(root: Path) -> None:
    control_report = analyze_controls(root)
    benchmark_report = analyze_benchmarks(root, control_report)
    determinism = read_json(root / "determinism_report.json")
    qualified_shapes = [row for row in control_report["controls"] if row["kind"] == "shape_only_control" and row["status"] == "CROSS_QUALIFIED"]
    qualified_poses = [row for row in control_report["controls"] if row["kind"] == "pose_only_control" and row["status"] == "CROSS_QUALIFIED"]
    baseline = next(row for row in control_report["controls"] if row["kind"] == "baseline")
    write_json(root / "CROSS_QUALIFIED_SHAPES_V1.json", {
        "schema": "cross-qualified-shapes-v1", "medical_truth": False,
        "shape_count_including_baseline": 1 + len(qualified_shapes),
        "shapes": [{"shape_id": "S0_BASE", "status": baseline["status"]}] + [{"shape_id": row["shape_id"], "status": row["status"]} for row in qualified_shapes],
        "scope": "fixed canonical SKEL, natural prone P0 control, cluster gate v1",
    })
    write_json(root / "CROSS_QUALIFIED_POSES_V1.json", {
        "schema": "cross-qualified-poses-v1", "medical_truth": False,
        "pose_count_including_baseline": 1 + len(qualified_poses),
        "poses": [{"pose_id": "P0_BASE", "status": baseline["status"]}] + [{"pose_id": row["pose_id"], "status": row["status"]} for row in qualified_poses],
        "scope": "fixed canonical SKEL, baseline S0 control, cluster gate v1",
    })
    source_unchanged = read_json(root / "source_hashes_before.json") == cross.protected_sources()
    verification = {
        "schema": "cross-gate-reconciliation-verification-v1",
        "passed": bool(control_report["passed"] and benchmark_report["passed"] and determinism["passed"] and source_unchanged and baseline["status"] == "CROSS_QUALIFIED"),
        "control_count": len(control_report["controls"]),
        "cross_qualified_nonbaseline_shape_count": len(qualified_shapes),
        "cross_qualified_nonbaseline_pose_count": len(qualified_poses),
        "benchmark_count": len(benchmark_report["benchmarks"]),
        "benchmark_parent_rule_blocked_count": sum(row["status"] == "PARENT_NOT_CROSS_QUALIFIED" for row in benchmark_report["benchmarks"]),
        "determinism_passed": determinism["passed"],
        "protected_sources_unchanged": source_unchanged,
        "truth_status": {"kind": "ENGINEERING_QA", "medical_truth": False, "medical_validated": False},
        "next_gate": "Do not run a new Shape×Pose search unless at least one nonbaseline Shape and one nonbaseline Pose are CROSS_QUALIFIED.",
    }
    write_json(root / "verification.json", verification)
    lines = [
        "# CROSS_GATE_RECONCILIATION_V1", "",
        f"结果：**{'PASS' if verification['passed'] else 'FAIL'}**。15 个 control 已按同一 cluster gate 复核。", "",
        f"- Cross-qualified 非 baseline Shape：{len(qualified_shapes)}",
        f"- Cross-qualified 非 baseline Pose：{len(qualified_poses)}",
        f"- 校准 benchmark：{len(benchmark_report['benchmarks'])}",
        f"- 父项规则阻止：{verification['benchmark_parent_rule_blocked_count']}",
        "- 该结果是工程几何 QA，不是医学、软组织或机器人安全结论。",
    ]
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = build_manifest(root)
    print(json.dumps({"FINAL": "PASS" if verification["passed"] else "FAIL", **result, "qualified_shapes": len(qualified_shapes), "qualified_poses": len(qualified_poses)}, ensure_ascii=False), flush=True)
    if not verification["passed"]:
        raise SystemExit(4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=(
        "prepare", "controls", "benchmarks", "determinism", "finalize",
        "search", "search_determinism", "search_finalize",
        "search_rgbd", "search_rgbd_determinism", "search_rgbd_finalize",
    ))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.root)
    elif args.mode == "controls":
        run_group(args.root, "controls", controls())
        analyze_controls(args.root)
    elif args.mode == "benchmarks":
        config = by_id()
        run_group(args.root, "benchmarks", [config[identifier] for identifier in LOW_BENCHMARKS + HIGH_BENCHMARKS])
        analyze_benchmarks(args.root, analyze_controls(args.root))
    elif args.mode == "determinism":
        run_determinism(args.root)
    elif args.mode == "finalize":
        finalize(args.root)
    elif args.mode == "search":
        run_group(args.root, "search", search_cells())
        analyze_search(args.root)
    elif args.mode == "search_determinism":
        run_search_determinism(args.root)
    elif args.mode == "search_finalize":
        finalize_search(args.root)
    elif args.mode == "search_rgbd":
        run_search_rgbd(args.root)
    elif args.mode == "search_rgbd_determinism":
        run_search_rgbd_determinism(args.root)
    elif args.mode == "search_rgbd_finalize":
        finalize_search_rgbd(args.root)


if __name__ == "__main__":
    main()
