from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prepare_geometry_gate import RECON_ROOT, read, sha, write  # noqa: E402

RECON_WS = HERE.parent / "cross_gate_reconciliation_v1"
sys.path.insert(0, str(RECON_WS))
import run_cross_gate_reconciliation as reconcile  # noqa: E402


def primary_rows(root: Path) -> dict[str, dict]:
    rows = read(root / "geometry_primary_report.json")["cells"]
    rows += read(root / "reserve_geometry_report.json")["cells"]
    return {row["case_id"]: row for row in rows}


def canonical_probe_hash(path: Path) -> str:
    """Hash geometry content, excluding temp-path-dependent Blend provenance."""
    payload = read(path)
    payload.pop("source_blend", None)
    payload.pop("source_blend_sha256", None)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def run(root: Path) -> None:
    selection = read(root / "qualified_new_geometry.json")
    cells = selection["validation"] + selection["untouched_test"]
    first = primary_rows(root)
    results = []
    with tempfile.TemporaryDirectory(prefix="acu_decoder_selected_repeat_") as temp:
        for index, cell in enumerate(cells, 1):
            case_id = cell["case_id"]
            meta = reconcile.run_case(
                root, "geometry_selected_repeat", cell, case_id, Path(temp)
            )
            narrow_path = root / "geometry_selected_repeat" / "narrow" / f"{case_id}.json"
            probe_path = root / "geometry_selected_repeat" / "probes" / f"{case_id}.json"
            narrow = read(narrow_path)
            references = []
            for parent in (cell["parent_a"], cell["parent_b"]):
                references.extend(
                    read(RECON_ROOT / "search" / "narrow" / f"{parent}.json")["clusters"]
                )
            gate = reconcile.evaluate_against_references(meta, narrow, references)
            now = {
                "case_id": case_id,
                "split": cell["split"],
                "status": gate["status"],
                "bed_clearance_m": meta["bed_clearance_m"],
                "probe_sha256": sha(probe_path),
                "canonical_probe_sha256": canonical_probe_hash(probe_path),
                "narrow_sha256": sha(narrow_path),
            }
            old = first[case_id]
            primary_probe = root / (
                "geometry_primary" if case_id in {
                    row["case_id"] for row in read(root / "geometry_primary_report.json")["cells"]
                } else "reserve_geometry"
            ) / "probes" / f"{case_id}.json"
            checks = {
                "status_equal": now["status"] == old["status"] == "CROSS_QUALIFIED",
                "bed_clearance_equal": now["bed_clearance_m"] == old["bed_clearance_m"],
                "canonical_probe_equal": now["canonical_probe_sha256"]
                == canonical_probe_hash(primary_probe),
                "narrow_equal": now["narrow_sha256"] == old["narrow_sha256"],
            }
            row = {**now, "checks": checks, "passed": all(checks.values())}
            results.append(row)
            print(index, case_id, "PASS" if row["passed"] else "FAIL", flush=True)
    split_checks = {
        "validation_four": sum(r["split"] == "VALIDATION" for r in results) == 4,
        "untouched_test_four": sum(r["split"] == "UNTOUCHED_TEST" for r in results) == 4,
    }
    payload = {
        "schema": "decoder-contract-selected-geometry-determinism-v1",
        "passed": all(r["passed"] for r in results) and all(split_checks.values()),
        "checks": split_checks,
        "rows": results,
    }
    write(root / "selected_geometry_determinism.json", payload)
    if not payload["passed"]:
        raise SystemExit(4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    run(args.root.resolve())


if __name__ == "__main__":
    main()
