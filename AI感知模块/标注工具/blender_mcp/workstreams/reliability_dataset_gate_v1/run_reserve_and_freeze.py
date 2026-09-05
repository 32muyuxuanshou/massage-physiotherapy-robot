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
BASE = HERE / "run_geometry_gate.py"
DECODER_WS = HERE.parent / "decoder_contract_v1"
RECON_WS = HERE.parent / "cross_gate_reconciliation_v1"
sys.path.insert(0, str(HERE))
import run_geometry_gate as base  # noqa: E402
sys.path.insert(0, str(DECODER_WS))
from prepare_geometry_gate import RECON_ROOT, interpolate, read, sha, write  # noqa: E402
sys.path.insert(0, str(RECON_WS))
import run_cross_gate_reconciliation as reconcile  # noqa: E402

DESIGN = HERE / "profile_design_reserve_v1.json"
EXPECTED = {"RELIABILITY_TRAIN": 12, "CALIBRATION": 6, "UNTOUCHED_TEST": 6}


def prepare(root: Path) -> None:
    shutil.copy2(DESIGN, root / DESIGN.name)
    design = read(DESIGN)
    cells = []
    for item in design["profiles"]:
        pa = read(RECON_ROOT / "profiles" / f"{item['parent_a']}.json")
        pb = read(RECON_ROOT / "profiles" / f"{item['parent_b']}.json")
        adapted = {**item, "split": item["partition"]}
        profile = interpolate(pa, pb, float(item["t"]), adapted)
        profile["partition"] = item["partition"]
        profile["description"] = "Geometry-only reserve body; fixed before locator prediction."
        write(root / "profiles" / f"{item['profile_id']}.json", profile)
        key = base.vector_key(profile)
        cells.append(
            {
                "case_id": item["profile_id"],
                "shape_id": profile["shape_profile_id"],
                "pose_id": profile["pose_profile_id"],
                "kind": "reliability_dataset_geometry_reserve",
                "partition": item["partition"],
                "replaces": item["replaces"],
                "parent_a": item["parent_a"],
                "parent_b": item["parent_b"],
                "interpolation_t": item["t"],
                "parameter_vector_sha256": hashlib.sha256(key.encode()).hexdigest(),
            }
        )
    primary = read(root / "geometry_primary_report.json")
    checks = {
        "ten_primary_cautions": sum(not row["passed"] for row in primary["rows"]) == 10,
        "one_reserve_per_primary_caution": {
            c["replaces"] for c in cells
        } == {row["case_id"] for row in primary["rows"] if not row["passed"]},
        "no_predictions_exist": not list(root.rglob("*prediction*")),
        "no_samples_exist": not [path for path in root.rglob("samples") if path.is_dir()],
    }
    payload = {
        "schema": "reliability-dataset-geometry-reserve-manifest-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "cells": cells,
        "design_sha256": sha(root / DESIGN.name),
    }
    write(root / "reserve_body_manifest.json", payload)
    if not payload["passed"]:
        raise SystemExit(2)


def run_cells(root: Path, phase: str, cells: list[dict]) -> list[dict]:
    rows = []
    with tempfile.TemporaryDirectory(prefix=f"acu_reliability_{phase}_") as temp:
        for index, cell in enumerate(cells, 1):
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
                "canonical_probe_sha256": base.canonical_probe_hash(probe_path),
                "narrow_sha256": sha(narrow_path),
            }
            rows.append(row)
            print(index, "/", len(cells), cell["case_id"], row["status"], flush=True)
    return rows


def run_reserve(root: Path) -> None:
    rows = run_cells(root, "geometry_reserve", read(root / "reserve_body_manifest.json")["cells"])
    report = {
        "schema": "reliability-dataset-reserve-geometry-gate-v1",
        "passed": all(row["passed"] for row in rows),
        "qualified_count": sum(row["passed"] for row in rows),
        "rows": rows,
    }
    write(root / "geometry_reserve_report.json", report)
    if not report["passed"]:
        raise SystemExit(3)


def select(root: Path) -> None:
    primary = read(root / "geometry_primary_report.json")["rows"]
    reserve = read(root / "geometry_reserve_report.json")["rows"]
    selected = [row for row in primary if row["passed"]] + [row for row in reserve if row["passed"]]
    selected.sort(key=lambda row: (list(EXPECTED).index(row["partition"]), row["case_id"]))
    counts = {name: sum(row["partition"] == name for row in selected) for name in EXPECTED}
    checks = {
        "exact_partition_counts": counts == EXPECTED,
        "exactly_24_selected": len(selected) == 24,
        "all_selected_cross_qualified": all(row["status"] == "CROSS_QUALIFIED" for row in selected),
        "all_parameter_vectors_unique": len({row["parameter_vector_sha256"] for row in selected}) == 24,
        "no_predictions_exist": not list(root.rglob("*prediction*")),
        "no_samples_exist": not [path for path in root.rglob("samples") if path.is_dir()],
    }
    payload = {
        "schema": "reliability-dataset-qualified-body-selection-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "partition_counts": counts,
        "selection_policy": "All primary geometry-qualified bodies plus one predeclared reserve for every primary CAUTION; no locator prediction existed.",
        "selected": selected,
        "excluded_primary_cautions": [row for row in primary if not row["passed"]],
    }
    write(root / "qualified_body_selection.json", payload)
    if not payload["passed"]:
        raise SystemExit(4)


def repeat(root: Path) -> None:
    selected = read(root / "qualified_body_selection.json")["selected"]
    rows = run_cells(root, "geometry_selected_repeat", selected)
    write(
        root / "geometry_selected_repeat_report.json",
        {
            "schema": "reliability-dataset-selected-geometry-repeat-v1",
            "passed": all(row["passed"] for row in rows),
            "rows": rows,
        },
    )


def verify_and_freeze(root: Path) -> None:
    selection = read(root / "qualified_body_selection.json")
    repeated = read(root / "geometry_selected_repeat_report.json")
    first = {row["case_id"]: row for row in selection["selected"]}
    rows = []
    for now in repeated["rows"]:
        old = first[now["case_id"]]
        checks = {
            "status_equal": old["status"] == now["status"] == "CROSS_QUALIFIED",
            "bed_clearance_equal": old["bed_clearance_m"] == now["bed_clearance_m"],
            "probe_equal": old["canonical_probe_sha256"] == now["canonical_probe_sha256"],
            "narrow_equal": old["narrow_sha256"] == now["narrow_sha256"],
        }
        rows.append({"case_id": now["case_id"], "checks": checks, "passed": all(checks.values())})
    determinism = {
        "schema": "reliability-dataset-selected-geometry-determinism-v1",
        "passed": len(rows) == 24 and all(row["passed"] for row in rows),
        "rows": rows,
    }
    write(root / "selected_geometry_determinism.json", determinism)
    predictions = list(root.rglob("*prediction*")) + list(root.rglob("*model_state*"))
    samples = [path for path in root.rglob("samples") if path.is_dir()]
    checks = {
        "qualified_selection_passed": selection["passed"],
        "selected_geometry_determinism_passed": determinism["passed"],
        "no_locator_predictions_exist": not predictions,
        "no_samples_generated": not samples,
    }
    protected_names = (
        "profile_design_v1.json",
        "profile_design_reserve_v1.json",
        "camera_design_v1.json",
        "body_input_manifest.json",
        "geometry_primary_report.json",
        "geometry_reserve_report.json",
        "qualified_body_selection.json",
        "selected_geometry_determinism.json",
    )
    receipt = {
        "schema": "reliability-dataset-partition-freeze-receipt-v1",
        "passed": all(checks.values()),
        "status": "PARTITIONS_FROZEN_BEFORE_PREDICTIONS" if all(checks.values()) else "FREEZE_FAILED",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "partition_counts": selection["partition_counts"],
        "protected_inputs": {
            name: {"path": str(root / name), "sha256": sha(root / name)}
            for name in protected_names
        },
        "training_authorized": False,
    }
    write(root / "partition_freeze_receipt.json", receipt)
    if not receipt["passed"]:
        raise SystemExit(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "reserve", "select", "repeat", "freeze"))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "prepare":
        prepare(root)
    elif args.mode == "reserve":
        run_reserve(root)
    elif args.mode == "select":
        select(root)
    elif args.mode == "repeat":
        repeat(root)
    else:
        verify_and_freeze(root)


if __name__ == "__main__":
    main()
