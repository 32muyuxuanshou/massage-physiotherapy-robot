from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
DECODER_WS = HERE.parent / "decoder_contract_v1"
RECON_WS = HERE.parent / "cross_gate_reconciliation_v1"
sys.path.insert(0, str(DECODER_WS))
from prepare_geometry_gate import RECON_ROOT, interpolate, read, sha, write  # noqa: E402
sys.path.insert(0, str(RECON_WS))
import run_cross_gate_reconciliation as reconcile  # noqa: E402

DESIGN = HERE / "profile_design_v1.json"
CAMERAS = HERE / "camera_design_v1.json"
EXPECTED = {"RELIABILITY_TRAIN": 12, "CALIBRATION": 6, "UNTOUCHED_TEST": 6}


def canonical_probe_hash(path: Path) -> str:
    payload = read(path)
    payload.pop("source_blend", None)
    payload.pop("source_blend_sha256", None)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def vector_key(profile: dict) -> str:
    return json.dumps(
        [profile["betas"], profile["pose_vector_degrees"]],
        sort_keys=True,
        separators=(",", ":"),
    )


def prepare(root: Path) -> None:
    reconcile.prepare(root)
    shutil.copy2(DESIGN, root / DESIGN.name)
    shutil.copy2(CAMERAS, root / CAMERAS.name)
    design = read(DESIGN)
    old_vectors = {
        vector_key(read(path)): path.stem for path in (RECON_ROOT / "profiles").glob("*.json")
    }
    cells = []
    new_vectors = {}
    for item in design["profiles"]:
        parent_a = read(RECON_ROOT / "profiles" / f"{item['parent_a']}.json")
        parent_b = read(RECON_ROOT / "profiles" / f"{item['parent_b']}.json")
        adapted = {**item, "split": item["partition"]}
        profile = interpolate(parent_a, parent_b, float(item["t"]), adapted)
        profile["partition"] = item["partition"]
        profile["description"] = "Reliability-dataset body fixed before locator prediction."
        write(root / "profiles" / f"{item['profile_id']}.json", profile)
        key = vector_key(profile)
        cells.append(
            {
                "case_id": item["profile_id"],
                "shape_id": profile["shape_profile_id"],
                "pose_id": profile["pose_profile_id"],
                "kind": "reliability_dataset_new_body",
                "partition": item["partition"],
                "parent_a": item["parent_a"],
                "parent_b": item["parent_b"],
                "interpolation_t": item["t"],
                "parameter_vector_sha256": hashlib.sha256(key.encode()).hexdigest(),
                "matches_old_profile": old_vectors.get(key),
            }
        )
        new_vectors.setdefault(key, []).append(item["profile_id"])
    counts = {name: sum(c["partition"] == name for c in cells) for name in EXPECTED}
    checks = {
        "exact_partition_counts": counts == EXPECTED,
        "all_case_ids_unique": len({c["case_id"] for c in cells}) == len(cells),
        "all_parameter_vectors_unique": all(len(ids) == 1 for ids in new_vectors.values()),
        "no_exact_old_profile_match": all(c["matches_old_profile"] is None for c in cells),
        "camera_count_is_seven": len(read(CAMERAS)["scenarios"]) == 7,
        "external_occluder_included": any(
            c["kind"] == "EXTERNAL_OCCLUSION" for c in read(CAMERAS)["scenarios"]
        ),
        "c4_excluded": not any("C4" in c["camera_id"] for c in read(CAMERAS)["scenarios"]),
    }
    manifest = {
        "schema": "reliability-dataset-body-input-manifest-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "partition_counts": counts,
        "cells": cells,
        "profile_design_sha256": sha(root / DESIGN.name),
        "camera_design_sha256": sha(root / CAMERAS.name),
        "created_before_locator_predictions": True,
    }
    write(root / "body_input_manifest.json", manifest)
    if not manifest["passed"]:
        raise SystemExit(2)


def run(root: Path, phase: str) -> None:
    manifest = read(root / "body_input_manifest.json")
    rows = []
    with tempfile.TemporaryDirectory(prefix=f"acu_reliability_{phase}_") as temp:
        for index, cell in enumerate(manifest["cells"], 1):
            meta = reconcile.run_case(root, phase, cell, cell["case_id"], Path(temp))
            narrow_path = root / phase / "narrow" / f"{cell['case_id']}.json"
            probe_path = root / phase / "probes" / f"{cell['case_id']}.json"
            narrow = read(narrow_path)
            references = []
            for parent in (cell["parent_a"], cell["parent_b"]):
                references.extend(
                    read(RECON_ROOT / "search" / "narrow" / f"{parent}.json")["clusters"]
                )
            gate = reconcile.evaluate_against_references(meta, narrow, references)
            row = {
                **cell,
                "status": gate["status"],
                "passed": gate["status"] == "CROSS_QUALIFIED",
                "bed_clearance_m": meta["bed_clearance_m"],
                "gate": gate,
                "canonical_probe_sha256": canonical_probe_hash(probe_path),
                "narrow_sha256": sha(narrow_path),
            }
            rows.append(row)
            print(index, "/", len(manifest["cells"]), cell["case_id"], row["status"], flush=True)
    report = {
        "schema": f"reliability-dataset-{phase}-geometry-gate-v1",
        "phase": phase,
        "passed": all(row["passed"] for row in rows),
        "qualified_count": sum(row["passed"] for row in rows),
        "rows": rows,
    }
    write(root / f"{phase}_report.json", report)
    if not report["passed"]:
        raise SystemExit(3)


def verify_repeat(root: Path) -> None:
    first = read(root / "geometry_primary_report.json")
    repeat = read(root / "geometry_repeat_report.json")
    repeat_by_id = {row["case_id"]: row for row in repeat["rows"]}
    rows = []
    for row in first["rows"]:
        other = repeat_by_id[row["case_id"]]
        checks = {
            "status_equal": row["status"] == other["status"] == "CROSS_QUALIFIED",
            "bed_clearance_equal": row["bed_clearance_m"] == other["bed_clearance_m"],
            "probe_equal": row["canonical_probe_sha256"] == other["canonical_probe_sha256"],
            "narrow_equal": row["narrow_sha256"] == other["narrow_sha256"],
        }
        rows.append({"case_id": row["case_id"], "checks": checks, "passed": all(checks.values())})
    report = {
        "schema": "reliability-dataset-geometry-determinism-v1",
        "passed": len(rows) == 24 and all(row["passed"] for row in rows),
        "rows": rows,
    }
    write(root / "geometry_determinism.json", report)
    if not report["passed"]:
        raise SystemExit(4)


def freeze(root: Path) -> None:
    manifest = read(root / "body_input_manifest.json")
    geometry = read(root / "geometry_primary_report.json")
    repeat = read(root / "geometry_determinism.json")
    predictions = list(root.rglob("*prediction*")) + list(root.rglob("*model_state*"))
    sample_dirs = [path for path in root.rglob("samples") if path.is_dir()]
    checks = {
        "input_manifest_passed": manifest["passed"],
        "all_24_geometry_qualified": geometry["passed"] and geometry["qualified_count"] == 24,
        "geometry_repeat_passed": repeat["passed"],
        "no_locator_predictions_exist": not predictions,
        "no_samples_generated": not sample_dirs,
    }
    protected = {
        name: {"path": str(root / name), "sha256": sha(root / name)}
        for name in (
            "profile_design_v1.json",
            "camera_design_v1.json",
            "body_input_manifest.json",
            "geometry_primary_report.json",
            "geometry_determinism.json",
        )
    }
    receipt = {
        "schema": "reliability-dataset-partition-freeze-receipt-v1",
        "passed": all(checks.values()),
        "status": "PARTITIONS_FROZEN_BEFORE_PREDICTIONS" if all(checks.values()) else "FREEZE_FAILED",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "partition_counts": manifest["partition_counts"],
        "protected_inputs": protected,
        "training_authorized": False,
    }
    write(root / "partition_freeze_receipt.json", receipt)
    if not receipt["passed"]:
        raise SystemExit(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "geometry", "repeat", "verify", "freeze"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.mode == "prepare":
        prepare(root)
    elif args.mode == "geometry":
        run(root, "geometry_primary")
    elif args.mode == "repeat":
        run(root, "geometry_repeat")
    elif args.mode == "verify":
        verify_repeat(root)
    else:
        freeze(root)


if __name__ == "__main__":
    main()
