from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence.resolve()
    rows = list(csv.DictReader((root / "analysis" / "point_residuals.csv").open(encoding="utf-8-sig")))
    checks = {}
    detail = {}
    for split in SPLITS:
        v2 = [r for r in rows if r["split"] == split and r["version"] == "v2"]
        v1 = [r for r in rows if r["split"] == split and r["version"] == "v1"]
        checks[f"{split}_same_v1_v2_instances"] = {(r["sample_id"], r["point_id"]) for r in v1} == {(r["sample_id"], r["point_id"]) for r in v2}
        visible = [r for r in v2 if r["visible"] == "True" and r["error_3d_mm"]]
        tail = [r for r in visible if float(r["error_3d_mm"]) > 30]
        safe = [r for r in visible if float(r["error_3d_mm"]) <= 30]
        tail_peak = sum(float(r["peak_probability"]) for r in tail) / len(tail)
        safe_peak = sum(float(r["peak_probability"]) for r in safe) / len(safe)
        checks[f"{split}_tail_peak_exceeds_safe_peak"] = tail_peak > safe_peak
        left = [float(r["error_2d_px"]) for r in visible if r["direction"] == "LEFT"]
        right = [float(r["error_2d_px"]) for r in visible if r["direction"] == "RIGHT"]
        detail[split] = {"tail_count": len(tail), "tail_peak_mean": tail_peak, "non_tail_peak_mean": safe_peak, "left_mean_2d_px": sum(left) / len(left), "right_mean_2d_px": sum(right) / len(right)}
    protected = [
        Path(r"E:\项目-按摩理疗机器人\AI感知模块\outputs\内部工程证据\2026-09-01_14-37-04_FAILURE_DRIVEN_PILOT_V2\SHA256SUMS.txt"),
        Path(r"E:\项目-按摩理疗机器人\AI感知模块\outputs\内部工程证据\2026-09-01_14-37-04_FAILURE_DRIVEN_PILOT_V2\truncation_holdout_v2.npz"),
    ]
    report = {
        "schema": "truncation-residual-independent-audit-v1",
        "passed": all(checks.values()), "checks": checks, "detail": detail,
        "frozen_input_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected},
        "restrictions": ["Audit recomputes from exchange CSV only", "It does not import inference or analysis modules", "This is engineering, not medical or robot-safety validation"],
    }
    (root / "independent_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "detail": detail}, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
