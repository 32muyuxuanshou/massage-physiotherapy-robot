from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


SPLITS = ("COMBINATION_HOLDOUT", "SHAPE_HOLDOUT", "POSE_HOLDOUT")
DECODERS = ("expectation", "argmax", "log_quadratic", "boundary_hybrid")
WIDTH, HEIGHT = 1280, 1024


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def summary(values: list[float], unit: str) -> dict:
    a = np.asarray(values, dtype=np.float64)
    if not a.size:
        return {"count": 0, "mean": None, "p95": None, "max": None, "unit": unit}
    return {"count": int(a.size), "mean": float(a.mean()), "p95": float(np.percentile(a, 95)), "max": float(a.max()), "unit": unit}


def edge(uv: np.ndarray) -> tuple[str, float]:
    values = {"LEFT": uv[0], "RIGHT": WIDTH - uv[0], "TOP": uv[1], "BOTTOM": HEIGHT - uv[1]}
    key = min(values, key=values.get)
    return key, float(values[key])


def bucket(distance: float) -> str:
    if distance < 16: return "0-16"
    if distance < 32: return "16-32"
    if distance < 64: return "32-64"
    if distance < 128: return "64-128"
    return ">=128"


def inward(edge_name: str, delta: np.ndarray) -> float:
    return {"LEFT": delta[0], "RIGHT": -delta[0], "TOP": delta[1], "BOTTOM": -delta[1]}[edge_name]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-v2", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    evidence = args.evidence_v2.resolve(); data = np.load(evidence / "truncation_holdout_v2.npz", allow_pickle=False)
    manifest = read_json(evidence / "dataset_manifest.json"); by_id = {x["sample_id"]: x for x in manifest["truncation_holdout"]}
    sample_ids = data["sample_ids"].astype(str); point_ids = data["point_ids"].astype(str)
    report = {"schema": "frozen-v2-decoder-comparison-v1", "medical_truth": False, "splits": {}}
    cache = {}
    for split in SPLITS:
        pred_file = np.load(args.predictions / f"{split}_decoder_predictions.npz", allow_pickle=False)
        selection = pred_file["selection"].astype(np.int64)
        report["splits"][split] = {}
        for decoder in DECODERS:
            pred = pred_file[decoder].astype(np.float64); errors=[]; errors3=[]; inward_values=[]; invalid=0; invalid_details=[]
            bins=defaultdict(list); point_groups=defaultdict(list)
            for local, global_index in enumerate(selection):
                row = by_id[sample_ids[global_index]]; sample_dir = Path(row["gate_sample_directory"])
                if str(sample_dir) not in cache:
                    labels=read_json(sample_dir/"labels.json"); depth=np.load(sample_dir/"scene_depth_z.npy",allow_pickle=False)
                    with Image.open(sample_dir/"depth_valid_mask.png") as image: valid=np.asarray(image.convert("L"),dtype=np.uint8)
                    with Image.open(sample_dir/"skin_mask.png") as image: skin=np.asarray(image.convert("L"),dtype=np.uint8)
                    cache[str(sample_dir)]=(labels,depth,valid,skin)
                labels,depth,valid,skin=cache[str(sample_dir)]; k=labels["camera"]["intrinsics"]
                for j, point_id in enumerate(point_ids):
                    if not bool(data["visible"][global_index,j]): continue
                    gt=data["uv"][global_index,j].astype(np.float64); delta=pred[local,j]-gt; err=float(np.linalg.norm(delta))
                    edge_name,distance=edge(gt); errors.append(err); inward_values.append(inward(edge_name,delta)); bins[bucket(distance)].append(err); point_groups[str(point_id)].append(err)
                    u,v=pred[local,j]; col,r=int(math.floor(u)),int(math.floor(v))
                    reason = None
                    if not (0<=col<depth.shape[1] and 0<=r<depth.shape[0]): reason = "PREDICTED_OUT_OF_FRAME"
                    elif depth[r,col]<=0 or valid[r,col]!=255: reason = "INVALID_DEPTH"
                    elif skin[r,col]!=255: reason = "NON_SKIN_FIRST_SURFACE"
                    if reason:
                        invalid+=1
                        invalid_details.append({"sample_id":row["sample_id"],"point_id":str(point_id),"reason":reason,"predicted_uv":[float(u),float(v)],"target_uv":gt.tolist(),"error_2d_px":err})
                        continue
                    z=float(depth[r,col]); xyz=np.asarray([(u-k["cx"])*z/k["fx"],(v-k["cy"])*z/k["fy"],z]); target=np.asarray(labels["points"][j]["xyz_camera_opencv_m"])
                    errors3.append(float(np.linalg.norm(xyz-target)*1000.0))
            report["splits"][split][decoder]={
                "visible_2d":summary(errors,"px"), "final_3d":summary(errors3,"mm"), "invalid_3d_count":invalid, "invalid_3d_details":invalid_details,
                "tail_gt30mm_count":sum(v>30 for v in errors3), "mean_signed_inward_bias_px":float(np.mean(inward_values)),
                "by_edge_distance":{key:summary(values,"px") for key,values in sorted(bins.items())},
                "worst_points":sorted(({"point_id":key,**summary(values,"px")} for key,values in point_groups.items()),key=lambda x:x["p95"],reverse=True)[:6],
            }
    checks={}
    for split in SPLITS:
        base=report["splits"][split]["expectation"]; candidate=report["splits"][split]["boundary_hybrid"]
        checks[f"{split}_hybrid_reduces_p95_2d"] = candidate["visible_2d"]["p95"] < base["visible_2d"]["p95"]
        checks[f"{split}_hybrid_reduces_tail_gt30mm"] = candidate["tail_gt30mm_count"] < base["tail_gt30mm_count"]
    report["verification"]={"passed":all(checks.values()),"checks":checks}
    report["restriction"]="Decoder comparison reuses frozen V2 weights and test holdout; it is diagnostic evidence, not a test-tuned production decoder approval."
    (args.output/"decoder_comparison.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({s:{d:report['splits'][s][d]['visible_2d'] for d in DECODERS} for s in SPLITS},ensure_ascii=False))
    if not report["verification"]["passed"]: raise SystemExit(2)


if __name__ == "__main__":
    main()
