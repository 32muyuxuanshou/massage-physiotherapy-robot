"""Compare rule-only proxy geometry with prior topology-seed propagation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "docs/handoffs/real-scene-2026-09-21/posterior-torso-v1"
SANITY = Path(__file__).with_name("rule_sanity_v1")


def main() -> None:
    canonical = {r["id"]: np.asarray(r["canonical_xyz_mm"], dtype=float) for r in json.loads((BASE / "VIRTUAL_ACUPOINTS_ENGINEERING_V1.json").read_text(encoding="utf-8"))["records"]}
    sample_rows = []
    for sample in ["canonical_mhr", "B1", "B2", "B3", "B4", "B5"]:
        rule = json.loads((SANITY / sample / "RULE_OUTPUT.json").read_text(encoding="utf-8"))
        if sample == "canonical_mhr":
            transfer, scale = canonical, 1.0
        else:
            transfer_path = BASE / "prediction_propagation_v1" / sample / "PROPAGATED_POINTS.json"
            transfer = {r["id"]: np.asarray(r["xyz"], dtype=float) for r in json.loads(transfer_path.read_text(encoding="utf-8"))["acupoints"]}
            scale = 1000.0
        distances, per_point = [], []
        for row in rule["rules"]:
            delta = float(np.linalg.norm(np.asarray(row["surface_xyz"]) - transfer[row["id"]]) * scale)
            distances.append(delta)
            per_point.append({"id": row["id"], "rule_vs_transfer_distance_mm": delta})
        sample_rows.append({"sample": sample, "median_mm": float(np.median(distances)), "max_mm": float(np.max(distances)), "per_point": per_point, "medical_truth": False})
    output = {
        "schema": "RULE_ONLY_VS_TOPOLOGY_SEED_GEOMETRY_V1", "status": "ENGINEERING_PROXY_ONLY", "medical_truth": False,
        "comparison": "surface-projected rule point versus previous canonical-atlas topology seed propagation",
        "samples": sample_rows,
        "interpretation": "Distances measure disagreement between two provisional engineering constructions. They are not errors against human acupoint ground truth."
    }
    (SANITY / "RULE_ONLY_VS_TRANSFER_GEOMETRY_V1.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    lines = ["# Rule-only 与 topology seed 的几何对照", "", "这不是临床误差；它只比较两种 provisional engineering construction。", "", "| sample | median | max |", "|---|---:|---:|"]
    lines.extend(f"| {r['sample']} | {r['median_mm']:.3f} mm | {r['max_mm']:.3f} mm |" for r in sample_rows)
    lines += ["", "所有点均标记 `medical_truth=false`。没有医生或独立真人参考时，不把这些差异用于接受/拒绝穴位定位。"]
    (SANITY / "RULE_ONLY_VS_TRANSFER_GEOMETRY_V1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
