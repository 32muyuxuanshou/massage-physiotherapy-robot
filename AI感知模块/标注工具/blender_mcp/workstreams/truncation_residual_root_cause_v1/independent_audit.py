from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SPLITS=("COMBINATION_HOLDOUT","SHAPE_HOLDOUT","POSE_HOLDOUT")


def read(path:Path)->dict: return json.loads(path.read_text(encoding="utf-8-sig"))
def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main()->None:
    parser=argparse.ArgumentParser(); parser.add_argument("--evidence",type=Path,required=True); args=parser.parse_args(); root=args.evidence.resolve()
    perfect=read(root/"gate_a2"/"perfect_heatmap_audit.json"); holdout=read(root/"decoder_evaluation"/"decoder_comparison.json"); main_test=read(root/"main_test_decoder_evaluation"/"main_test_decoder_comparison.json")
    checks={
        "perfect_target_near_edge_p95_matches_one_heatmap_cell":30<=perfect["actual_nearest_edge_lt64"]["p95_expectation_error_px"]<=38,
        "perfect_target_bias_is_inward":perfect["actual_nearest_edge_lt64"]["mean_inward_bias_px"]>15,
        "holdout_decoder_gate_passed":holdout["verification"]["passed"],
        "main_test_decoder_gate_passed":main_test["verification"]["passed"],
    }
    detail={"holdout":{},"main_test":{}}
    for split in SPLITS:
        e=holdout["splits"][split]["expectation"]; h=holdout["splits"][split]["boundary_hybrid"]
        detail["holdout"][split]={"p95_2d_before_after":[e["visible_2d"]["p95"],h["visible_2d"]["p95"]],"tail_gt30mm_before_after":[e["tail_gt30mm_count"],h["tail_gt30mm_count"]],"hybrid_invalid_3d":h["invalid_3d_count"]}
        checks[f"{split}_holdout_no_invalid"] = h["invalid_3d_count"]==0
        e=main_test["splits"][split]["expectation"]; h=main_test["splits"][split]["boundary_hybrid"]
        detail["main_test"][split]={"normal_mean_2d_before_after":[e["by_camera"]["NORMAL_MAIN"]["mean"],h["by_camera"]["NORMAL_MAIN"]["mean"]],"c2_p95_2d_before_after":[e["by_camera"]["C2_EDGE_CROP"]["p95"],h["by_camera"]["C2_EDGE_CROP"]["p95"]],"tail_gt30mm_before_after":[e["tail_gt30mm_count"],h["tail_gt30mm_count"]],"hybrid_invalid_3d":h["invalid_3d_count"]}
        checks[f"{split}_normal_exactly_unchanged"] = e["by_camera"]["NORMAL_MAIN"]==h["by_camera"]["NORMAL_MAIN"]
        checks[f"{split}_main_no_invalid"] = h["invalid_3d_count"]==0
    prior=Path(r"E:\项目-按摩理疗机器人\AI感知模块\outputs\内部工程证据\2026-09-01_14-37-04_FAILURE_DRIVEN_PILOT_V2\SHA256SUMS.txt")
    checks["prior_evidence_unchanged"] = sha(prior)=="E9AA524E65F8178A282B694540CA4AAB68365411F2451F2F95C942702F4FD367"
    report={"schema":"truncation-root-cause-independent-audit-v1","passed":all(checks.values()),"checks":checks,"detail":detail,"training_performed":False,"candidate_status":"DIAGNOSTIC_VALIDATED_ON_EXISTING_FROZEN_TESTS_NOT_FINAL_UNTOUCHED_TEST","restrictions":["E01-E20 are non-medical engineering points","No robot-safety claim","Decoder choice was informed by observed truncation failures"]}
    (root/"independent_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"passed":report["passed"],"checks":checks},ensure_ascii=False))
    if not report["passed"]: raise SystemExit(2)


if __name__=="__main__": main()
