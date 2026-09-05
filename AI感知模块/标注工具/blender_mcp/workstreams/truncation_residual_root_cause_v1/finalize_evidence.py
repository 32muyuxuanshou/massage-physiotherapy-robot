from __future__ import annotations

import argparse,hashlib,json
from pathlib import Path


def read(path:Path)->dict:return json.loads(path.read_text(encoding="utf-8-sig"))
def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest().upper()


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--evidence",type=Path,required=True);args=parser.parse_args();root=args.evidence.resolve()
    audit=read(root/"independent_audit.json");perfect=read(root/"gate_a2"/"perfect_heatmap_audit.json");hold=read(root/"decoder_evaluation"/"decoder_comparison.json");main=read(root/"main_test_decoder_evaluation"/"main_test_decoder_comparison.json")
    checks={"independent_audit_passed":audit["passed"],"perfect_heatmap_near_edge_instances_present":perfect["actual_nearest_edge_lt64_count"]==431,"holdout_gate_passed":hold["verification"]["passed"],"main_test_gate_passed":main["verification"]["passed"],"no_training_performed":audit["training_performed"] is False,"summary_visual_present":(root/"visuals"/"root_cause_and_decoder_summary.png").is_file()}
    result={"schema":"truncation-residual-root-cause-final-verification-v1","status":"PASS_ROOT_CAUSE_CONFIRMED_CANDIDATE_NOT_YET_FROZEN" if all(checks.values()) else "FAIL","checks":checks,"candidate":"BOUNDARY_HYBRID_V1","candidate_production_ready":False,"next_gate":"VALIDATION_FROZEN_DECODER_CONTRACT_AND_UNTOUCHED_TEST_V1","medical_truth":False,"robot_safety_validated":False}
    (root/"final_verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    files=sorted(p for p in root.rglob("*") if p.is_file() and p.name!="SHA256SUMS.txt");lines=[f"{sha(p)} *{p.relative_to(root).as_posix()}" for p in files];(root/"SHA256SUMS.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"files":len(files),"manifest_sha256":sha(root/"SHA256SUMS.txt")},ensure_ascii=False))
    if result["status"]=="FAIL":raise SystemExit(2)


if __name__=="__main__":main()
