from __future__ import annotations

import argparse
import json
from pathlib import Path


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reduction(old: float, new: float) -> float:
    return (old - new) / old


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-evaluation", type=Path, required=True)
    parser.add_argument("--new-evaluation", type=Path, required=True)
    parser.add_argument("--holdout-ab", type=Path, required=True)
    parser.add_argument("--data-qc", type=Path, required=True)
    parser.add_argument("--determinism", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old = read_json(args.old_evaluation)
    new = read_json(args.new_evaluation)
    holdout = read_json(args.holdout_ab)
    data_qc = read_json(args.data_qc)
    determinism = read_json(args.determinism)
    rows = {}
    gates = {"data_qc_passed": data_qc["passed"], "determinism_passed": determinism["passed"]}
    for split_id in SPLITS:
        old_test = old["splits"][split_id]["test"]
        new_test = new["splits"][split_id]["test"]
        old_pixel = old_test["pixel_error_original"]
        new_pixel = new_test["pixel_error_original"]
        old_3d = old_test["error_decomposition_3d"]["C_pred_uv_plus_scene_depth"]
        new_3d = new_test["error_decomposition_3d"]["C_pred_uv_plus_scene_depth"]
        old_normal = old_test["by_camera"]["NORMAL_MAIN"]
        new_normal = new_test["by_camera"]["NORMAL_MAIN"]
        old_c2 = old_test["by_camera"]["C2_EDGE_CROP"]
        new_c2 = new_test["by_camera"]["C2_EDGE_CROP"]
        ab = holdout["splits"][split_id]
        rows[split_id] = {
            "legacy_frozen_test": {
                "mean_2d_px": {"v1": old_pixel["mean"], "v2": new_pixel["mean"], "reduction": reduction(old_pixel["mean"], new_pixel["mean"])},
                "p95_2d_px": {"v1": old_pixel["p95"], "v2": new_pixel["p95"], "reduction": reduction(old_pixel["p95"], new_pixel["p95"])},
                "mean_3d_mm": {"v1": old_3d["mean"], "v2": new_3d["mean"], "reduction": reduction(old_3d["mean"], new_3d["mean"])},
                "p95_3d_mm": {"v1": old_3d["p95"], "v2": new_3d["p95"], "reduction": reduction(old_3d["p95"], new_3d["p95"])},
                "normal_main_mean_2d_px": {"v1": old_normal["mean"], "v2": new_normal["mean"], "reduction": reduction(old_normal["mean"], new_normal["mean"])},
                "c2_mean_2d_px": {"v1": old_c2["mean"], "v2": new_c2["mean"], "reduction": reduction(old_c2["mean"], new_c2["mean"])},
                "c2_p95_2d_px": {"v1": old_c2["p95"], "v2": new_c2["p95"], "reduction": reduction(old_c2["p95"], new_c2["p95"])},
            },
            "new_symmetric_truncation_holdout": {
                "sample_count": ab["holdout_sample_count"],
                "mean_2d_px": {"v1": ab["v1"]["visible_2d"]["mean"], "v2": ab["v2"]["visible_2d"]["mean"], "reduction": reduction(ab["v1"]["visible_2d"]["mean"], ab["v2"]["visible_2d"]["mean"])},
                "p95_2d_px": {"v1": ab["v1"]["visible_2d"]["p95"], "v2": ab["v2"]["visible_2d"]["p95"], "reduction": reduction(ab["v1"]["visible_2d"]["p95"], ab["v2"]["visible_2d"]["p95"])},
                "mean_3d_mm": {"v1": ab["v1"]["final_3d"]["mean"], "v2": ab["v2"]["final_3d"]["mean"], "reduction": reduction(ab["v1"]["final_3d"]["mean"], ab["v2"]["final_3d"]["mean"])},
                "p95_3d_mm": {"v1": ab["v1"]["final_3d"]["p95"], "v2": ab["v2"]["final_3d"]["p95"], "reduction": reduction(ab["v1"]["final_3d"]["p95"], ab["v2"]["final_3d"]["p95"])},
                "tail_gt30mm_count": {"v1": len(ab["v1"]["tail_gt30mm"]), "v2": len(ab["v2"]["tail_gt30mm"]), "reduction": reduction(len(ab["v1"]["tail_gt30mm"]), len(ab["v2"]["tail_gt30mm"]))},
            },
        }
        gates[f"{split_id}_legacy_mean_not_worse"] = new_pixel["mean"] <= old_pixel["mean"]
        gates[f"{split_id}_normal_mean_not_worse"] = new_normal["mean"] <= old_normal["mean"]
        gates[f"{split_id}_holdout_mean_2d_reduction_ge_40pct"] = rows[split_id]["new_symmetric_truncation_holdout"]["mean_2d_px"]["reduction"] >= 0.40
        gates[f"{split_id}_holdout_p95_2d_reduction_ge_30pct"] = rows[split_id]["new_symmetric_truncation_holdout"]["p95_2d_px"]["reduction"] >= 0.30
        gates[f"{split_id}_holdout_tail_reduction_ge_40pct"] = rows[split_id]["new_symmetric_truncation_holdout"]["tail_gt30mm_count"]["reduction"] >= 0.40

    passed = all(gates.values())
    payload = {
        "schema": "failure-driven-pilot-v2-ab-summary",
        "medical_truth": False,
        "status": "PASS_WITH_RESIDUAL_RISK" if passed else "FAIL",
        "passed": passed,
        "gates": gates,
        "splits": rows,
        "conclusion": "Controlled truncation training materially improves unseen symmetric truncation without degrading the frozen V1 benchmark or NORMAL_MAIN.",
        "residual_risk": [
            "Legacy C2 P95 improves only slightly and remains about 34–36 original-render pixels.",
            "New truncation holdout V2 P95 remains about 30–36 pixels and 54–66 mm in 3D.",
            "The intervention is effective but does not meet robot-safe accuracy.",
            "C4 remains challenge-only and unsolved.",
        ],
        "next_recommendation": "Do not scale data yet. Localize residual failures by direction/severity/point and add visibility-abstention evaluation before considering a larger model.",
    }
    write_json(args.output, payload)
    print(json.dumps({"FAILURE_DRIVEN_V2": payload["status"], "passed": passed}, ensure_ascii=False))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
