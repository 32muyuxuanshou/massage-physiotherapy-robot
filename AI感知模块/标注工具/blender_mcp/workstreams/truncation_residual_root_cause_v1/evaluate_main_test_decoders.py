from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


SPLITS=("COMBINATION_HOLDOUT","SHAPE_HOLDOUT","POSE_HOLDOUT")
DECODERS=("expectation","argmax","log_quadratic","boundary_hybrid")


def read_json(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8-sig"))


def stats(values:list[float],unit:str)->dict:
    a=np.asarray(values,dtype=np.float64)
    return {"count":int(a.size),"mean":float(a.mean()) if a.size else None,"p95":float(np.percentile(a,95)) if a.size else None,"max":float(a.max()) if a.size else None,"unit":unit}


def main()->None:
    parser=argparse.ArgumentParser(); parser.add_argument("--evidence-v2",type=Path,required=True); parser.add_argument("--v1-dataset",type=Path,required=True); parser.add_argument("--predictions",type=Path,required=True); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    evidence=args.evidence_v2.resolve(); v1root=args.v1_dataset.resolve(); data=np.load(evidence/"training_cache_v2.npz",allow_pickle=False)
    manifest=read_json(v1root/"dataset_manifest.json"); by_id={x["sample_id"]:x for x in manifest["main_samples"]}; sample_ids=data["sample_ids"].astype(str); point_ids=data["point_ids"].astype(str)
    cache={}; report={"schema":"frozen-v2-main-test-decoder-comparison-v1","medical_truth":False,"splits":{}}
    for split in SPLITS:
        pred_file=np.load(args.predictions/f"{split}_main_test_decoders.npz",allow_pickle=False); selection=pred_file["selection"].astype(np.int64); report["splits"][split]={}
        for decoder in DECODERS:
            pred=pred_file[decoder].astype(np.float64); err2=[]; err3=[]; invalid=[]; by_camera=defaultdict(list); by_point=defaultdict(list)
            for local,index in enumerate(selection):
                row=by_id[sample_ids[index]]; sample_dir=v1root/row["geometry_relative_directory"]
                if str(sample_dir) not in cache:
                    labels=read_json(sample_dir/"labels.json"); depth=np.load(sample_dir/"scene_depth_z.npy",allow_pickle=False)
                    with Image.open(sample_dir/"depth_valid_mask.png") as image: valid=np.asarray(image.convert("L"),dtype=np.uint8)
                    with Image.open(sample_dir/"skin_mask.png") as image: skin=np.asarray(image.convert("L"),dtype=np.uint8)
                    cache[str(sample_dir)]=(labels,depth,valid,skin)
                labels,depth,valid,skin=cache[str(sample_dir)]; k=labels["camera"]["intrinsics"]
                for j,point_id in enumerate(point_ids):
                    if not bool(data["visible"][index,j]): continue
                    gt=data["uv"][index,j].astype(np.float64); e2=float(np.linalg.norm(pred[local,j]-gt)); err2.append(e2); by_camera[row["camera_id"]].append(e2); by_point[str(point_id)].append(e2)
                    u,v=pred[local,j]; col,r=int(math.floor(u)),int(math.floor(v)); reason=None
                    if not(0<=col<depth.shape[1] and 0<=r<depth.shape[0]): reason="PREDICTED_OUT_OF_FRAME"
                    elif depth[r,col]<=0 or valid[r,col]!=255: reason="INVALID_DEPTH"
                    elif skin[r,col]!=255: reason="NON_SKIN_FIRST_SURFACE"
                    if reason: invalid.append({"sample_id":row["sample_id"],"point_id":str(point_id),"reason":reason}); continue
                    z=float(depth[r,col]); xyz=np.asarray([(u-k["cx"])*z/k["fx"],(v-k["cy"])*z/k["fy"],z]); target=np.asarray(labels["points"][j]["xyz_camera_opencv_m"]); err3.append(float(np.linalg.norm(xyz-target)*1000))
            report["splits"][split][decoder]={"visible_2d":stats(err2,"px"),"final_3d":stats(err3,"mm"),"tail_gt30mm_count":sum(x>30 for x in err3),"invalid_3d_count":len(invalid),"invalid_3d_details":invalid,"by_camera":{k:stats(v,"px") for k,v in sorted(by_camera.items())},"worst_points":sorted(({"point_id":k,**stats(v,"px")} for k,v in by_point.items()),key=lambda x:x["p95"],reverse=True)[:6]}
    checks={}
    for split in SPLITS:
        base=report["splits"][split]["expectation"]; cand=report["splits"][split]["boundary_hybrid"]
        checks[f"{split}_normal_main_not_regressed"] = cand["by_camera"]["NORMAL_MAIN"]["mean"] <= base["by_camera"]["NORMAL_MAIN"]["mean"] + 0.25
        checks[f"{split}_legacy_c2_p95_reduced"] = cand["by_camera"]["C2_EDGE_CROP"]["p95"] < base["by_camera"]["C2_EDGE_CROP"]["p95"]
        checks[f"{split}_no_new_invalid_3d"] = cand["invalid_3d_count"] <= base["invalid_3d_count"]
    report["verification"]={"passed":all(checks.values()),"checks":checks}; report["restriction"]="Same frozen V2 weights and V1 test samples; decoder was selected after inspecting truncation failures, so this is a diagnostic gate, not an untouched final test."
    (args.output/"main_test_decoder_comparison.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({s:{d:{"all":report['splits'][s][d]['visible_2d'],"normal":report['splits'][s][d]['by_camera']['NORMAL_MAIN'],"c2":report['splits'][s][d]['by_camera']['C2_EDGE_CROP']} for d in DECODERS} for s in SPLITS},ensure_ascii=False))
    if not report["verification"]["passed"]: raise SystemExit(2)


if __name__=="__main__": main()
