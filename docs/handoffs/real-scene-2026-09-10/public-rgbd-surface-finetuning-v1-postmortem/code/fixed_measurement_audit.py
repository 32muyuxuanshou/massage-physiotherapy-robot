"""Read-only fixed-point VAL rescoring and consumed-test measurement audit."""
from __future__ import annotations

import argparse, csv, hashlib, json, sys, time
from pathlib import Path
import numpy as np
import torch


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def summary(x):
    x = np.asarray(x, np.float64)
    return {"count": int(x.size), "mean_mm": float(x.mean()),
            "median_mm": float(np.median(x)), "p90_mm": float(np.percentile(x, 90)),
            "p95_mm": float(np.percentile(x, 95))}


def fixed_indices(n, maximum, seed):
    return np.arange(n, dtype=np.int64) if n <= maximum else np.sort(
        np.random.default_rng(seed).choice(n, maximum, replace=False))


def aggregate(rows):
    by_subject = {}
    for row in rows:
        by_subject.setdefault(row["subject_id"], []).append(row)
    subjects = []
    for sid, values in sorted(by_subject.items()):
        subjects.append({
            "subject_id": sid,
            "point_to_triangle_frame_median_mm": float(np.median([v["point_to_triangle"]["median_mm"] for v in values])),
            "point_to_triangle_frame_p90_mm": float(np.median([v["point_to_triangle"]["p90_mm"] for v in values])),
            "point_to_triangle_frame_p95_mm": float(np.median([v["point_to_triangle"]["p95_mm"] for v in values])),
            "rendered_depth_frame_median_mm": float(np.median([v["rendered_depth"]["median_mm"] for v in values])),
            "rendered_depth_frame_p90_mm": float(np.median([v["rendered_depth"]["p90_mm"] for v in values])),
            "rendered_depth_frame_p95_mm": float(np.median([v["rendered_depth"]["p95_mm"] for v in values])),
            "rendered_depth_coverage": float(np.median([v["rendered_depth"]["mesh_coverage_of_observed_points"] for v in values])),
        })
    return {
        "subject_count": len(subjects),
        "point_to_triangle_mean_of_subject_frame_medians_mm": float(np.mean([x["point_to_triangle_frame_median_mm"] for x in subjects])),
        "point_to_triangle_median_of_subject_frame_medians_mm": float(np.median([x["point_to_triangle_frame_median_mm"] for x in subjects])),
        "point_to_triangle_p90_of_subject_frame_medians_mm": float(np.percentile([x["point_to_triangle_frame_median_mm"] for x in subjects], 90)),
        "point_to_triangle_p95_of_subject_frame_medians_mm": float(np.percentile([x["point_to_triangle_frame_median_mm"] for x in subjects], 95)),
        "point_to_triangle_mean_of_subject_frame_p90_mm": float(np.mean([x["point_to_triangle_frame_p90_mm"] for x in subjects])),
        "point_to_triangle_mean_of_subject_frame_p95_mm": float(np.mean([x["point_to_triangle_frame_p95_mm"] for x in subjects])),
        "rendered_depth_mean_of_subject_frame_medians_mm": float(np.mean([x["rendered_depth_frame_median_mm"] for x in subjects])),
        "rendered_depth_mean_of_subject_frame_p90_mm": float(np.mean([x["rendered_depth_frame_p90_mm"] for x in subjects])),
        "rendered_depth_mean_of_subject_frame_p95_mm": float(np.mean([x["rendered_depth_frame_p95_mm"] for x in subjects])),
        "rendered_depth_median_coverage": float(np.median([x["rendered_depth_coverage"] for x in subjects])),
        "subjects": subjects,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=Path, required=True)
    ap.add_argument("--sam-repo", type=Path, required=True)
    ap.add_argument("--official", type=Path, required=True)
    ap.add_argument("--mhr", type=Path, required=True)
    ap.add_argument("--checkpoints", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    protocol = json.load(open(args.pilot / "TRAINING_PROTOCOL_V1.json"))
    maximum = int(protocol["validation"]["maximum_eval_points"]); seed = int(protocol["seed"])
    sys.path[:0] = [str(args.pilot / "code"), str(args.sam_repo)]
    from surface_metrics import camera_to_world, point_to_triangle, render_depth, rendered_depth, world_to_camera
    from train_rgbd_surface import forward_observation
    from sam_3d_body import SAM3DBodyEstimator, load_sam_3d_body
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to

    def load_manifest(name):
        d = json.load(open(args.pilot / name)); return d, d["samples"]
    val_manifest, val_rows = load_manifest("VAL_EVALUATION_MANIFEST_V1.json")
    sealed_manifest, sealed_rows = load_manifest("SEALED_EVALUATION_MANIFEST_V1.json")
    all_rows = val_rows + sealed_rows
    index_map, manifest_rows = {}, []
    for i, row in enumerate(all_rows):
        with np.load(row["observation_npz"]) as obs: n = len(obs["points_b"])
        ids = fixed_indices(n, maximum, seed + i)
        index_map[row["id"]] = ids
        manifest_rows.append({"id": row["id"], "split": row["split"], "subject_id": row["subject_id"],
            "source_point_count": n, "selected_point_count": int(len(ids)), "cap_triggered": n > maximum,
            "index_sha256": hashlib.sha256(ids.tobytes()).hexdigest(), "indices": ids.tolist()})
    fixed_manifest = {"status":"FROZEN", "seed":seed, "maximum_eval_points":maximum,
        "index_dtype":"int64", "selection":"all points if N<=cap, otherwise sorted PCG64 sample without replacement",
        "val_cap_triggered_frames":sum(x["cap_triggered"] and x["split"]=="VAL" for x in manifest_rows),
        "val_total_frames":len(val_rows), "rows":manifest_rows}
    (args.output / "FIXED_EVAL_POINT_MANIFEST_V1.json").write_text(json.dumps(fixed_manifest,indent=2),encoding="utf-8")

    model,cfg=load_sam_3d_body(str(args.official),device="cuda",mhr_path=str(args.mhr)); model.eval().requires_grad_(False)
    estimator=SAM3DBodyEstimator(model,cfg); faces=model.head_pose.faces.detach().cpu().numpy().astype(np.int64)
    official_pose={k:v.detach().cpu().clone() for k,v in model.head_pose.proj.state_dict().items()}
    official_camera={k:v.detach().cpu().clone() for k,v in model.head_camera.proj.state_dict().items()}

    def predict(row):
        with torch.inference_mode():
            out,_=forward_observation(model,estimator,prepare_batch,recursive_to,Path(row["observation_npz"]))
        return {k:out[k].detach().float().cpu() for k in ("pred_vertices","pred_cam_t")}

    def geometry(pred,row,coverage_pair=False):
        with np.load(row["observation_npz"]) as obs:
            pts=obs["points_b"].astype(np.float64)[index_map[row["id"]]]
            va=(pred["pred_vertices"]+pred["pred_cam_t"][:,None,:])[0].numpy()
            vb=world_to_camera(camera_to_world(va,obs["R_a"],obs["T_a"]),obs["R_b"],obs["T_b"])
            tri=point_to_triangle(pts,vb,faces)
            dep=rendered_depth(pts,vb,faces,obs["K_b"],obs["rgb_b"].shape[0],obs["rgb_b"].shape[1])
            if not coverage_pair:return {"id":row["id"],"subject_id":row["subject_id"],"point_to_triangle":tri,"rendered_depth":dep}
            z=render_depth(vb,faces,obs["K_b"],obs["rgb_b"].shape[0],obs["rgb_b"].shape[1])
            p=pts; u=np.rint(obs["K_b"][0,0]*p[:,0]/p[:,2]+obs["K_b"][0,2]).astype(int); v=np.rint(obs["K_b"][1,1]*p[:,1]/p[:,2]+obs["K_b"][1,2]).astype(int)
            inside=(p[:,2]>0)&(u>=0)&(u<z.shape[1])&(v>=0)&(v<z.shape[0]); hit=np.zeros(len(p),bool); residual=np.full(len(p),np.nan)
            hit[inside]=z[v[inside],u[inside]]>0; residual[hit]=np.abs(z[v[hit],u[hit]]-p[hit,2])*1000
            return hit,residual

    def set_official(): model.head_pose.proj.load_state_dict(official_pose); model.head_camera.proj.load_state_dict(official_camera)
    set_official(); official_val={r["id"]:predict(r) for r in val_rows}; official_sealed={r["id"]:predict(r) for r in sealed_rows}
    val_models=[]
    set_official(); val_models.append(("Official",None))
    for epoch in range(1,11): val_models.append((f"E{epoch}",args.checkpoints/f"official_pose_camera_epoch{epoch}.pt"))
    scored=[]
    for name,ckpt in val_models:
        if ckpt:
            state=torch.load(ckpt,map_location="cpu",weights_only=False); model.head_pose.proj.load_state_dict(state["heads"]["pose"]); model.head_camera.proj.load_state_dict(state["heads"]["camera"])
        else:set_official()
        rows=[geometry(official_val[r["id"]] if name=="Official" else predict(r),r) for r in val_rows]
        scored.append({"model":name,"checkpoint":None if ckpt is None else str(ckpt),"checkpoint_sha256":None if ckpt is None else sha256(ckpt),"aggregate":aggregate(rows),"rows":rows})
    primary="point_to_triangle_mean_of_subject_frame_medians_mm"; best=min(scored,key=lambda x:x["aggregate"][primary])
    fixed_result={"status":"COMPLETED_READ_ONLY_FIXED_POINT_RESCORE","historical_best":"E1","fixed_best":best["model"],
        "historical_best_confirmed":best["model"]=="E1","models":scored,"measurement_note":"14/15 VAL frames use all available points; only 1/15 triggered the 25,000-point cap."}
    (args.output/"FIXED_VAL_PER_EPOCH_METRICS_V1.json").write_text(json.dumps(fixed_result,indent=2),encoding="utf-8")
    with (args.output/"FIXED_VAL_PER_EPOCH_METRICS_V1.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["model","primary_mm","p90_subject_mm","p95_subject_mm","rendered_depth_mm","coverage"])
        for x in scored:
            a=x["aggregate"];w.writerow([x["model"],a[primary],a["point_to_triangle_p90_of_subject_frame_medians_mm"],a["point_to_triangle_p95_of_subject_frame_medians_mm"],a["rendered_depth_mean_of_subject_frame_medians_mm"],a["rendered_depth_median_coverage"]])

    e1=args.checkpoints/"official_pose_camera_epoch1.pt"; state=torch.load(e1,map_location="cpu",weights_only=False); model.head_pose.proj.load_state_dict(state["heads"]["pose"]);model.head_camera.proj.load_state_dict(state["heads"]["camera"])
    e1_sealed={r["id"]:predict(r) for r in sealed_rows}
    off_rows=[geometry(official_sealed[r["id"]],r) for r in sealed_rows]; e1_rows=[geometry(e1_sealed[r["id"]],r) for r in sealed_rows]
    consumed={"status":"CONSUMED_TEST_POSTHOC_ANALYSIS","checkpoint_selection":"historical frozen E1 only; E2-E10 not evaluated on consumed test","official":aggregate(off_rows),"historical_e1":aggregate(e1_rows),"historical_e1_minus_official_primary_mm":aggregate(e1_rows)[primary]-aggregate(off_rows)[primary],"rows":{"official":off_rows,"historical_e1":e1_rows}}
    (args.output/"CONSUMED_TEST_REEVALUATION_V1.json").write_text(json.dumps(consumed,indent=2),encoding="utf-8")

    coverage=[]
    for r in sealed_rows:
        oh,oe=geometry(official_sealed[r["id"]],r,True); eh,ee=geometry(e1_sealed[r["id"]],r,True); common=oh&eh
        coverage.append({"id":r["id"],"subject_id":r["subject_id"],"sensor_valid_points":int(len(oh)),
            "official_coverage":float(oh.mean()),"e1_coverage":float(eh.mean()),"intersection_coverage":float(common.mean()),
            "official_only_coverage":float((oh&~eh).mean()),"e1_only_coverage":float((eh&~oh).mean()),
            "common_official_error":summary(oe[common]),"common_e1_error":summary(ee[common])})
    cov={"status":"CONSUMED_TEST_POSTHOC_ANALYSIS","coverage_denominator":"fixed sensor-valid person points projected inside Camera B image",
         "warning":"Rendered-depth error on each model's own covered set is not directly paired; common coverage errors are paired.","rows":coverage}
    (args.output/"COVERAGE_AND_MISSING_REGION_AUDIT_V1.json").write_text(json.dumps(cov,indent=2),encoding="utf-8")
    print(json.dumps({"fixed_best":best["model"],"fixed_best_mm":best["aggregate"][primary],"consumed_official_mm":consumed["official"][primary],"consumed_e1_mm":consumed["historical_e1"][primary]},indent=2))

if __name__=="__main__":main()
