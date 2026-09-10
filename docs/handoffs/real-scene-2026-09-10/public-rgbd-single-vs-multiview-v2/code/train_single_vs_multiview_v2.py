"""Controlled S/M V2 trainer skeleton.

Dry-run is usable before selective extraction finishes. Smoke/train require a
materialized workset whose rows contain observation_npz files with rgb_a,
bbox_a, K_a, points_a, points_b, R_a/T_a and R_b/T_b.
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from scipy.spatial import cKDTree
from pose_camera_output_freeze import PoseCameraOutputFreeze
from surface_metrics import camera_to_world, world_to_camera, point_to_triangle, point_to_triangle_distances, rendered_depth

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""): h.update(b)
 return h.hexdigest()
def deterministic_update_order(rows,max_updates,seed):
 ids=[]; cycle=0
 while len(ids)<max_updates:
  rng=np.random.default_rng(int(hashlib.sha256(f"{seed}:update-order:{cycle}".encode()).hexdigest()[:16],16))
  ids.extend([rows[i]["id"] for i in rng.permutation(len(rows))]); cycle+=1
 return ids[:max_updates]

def validate_contract(protocol, split, pairs, anchors_meta, anchors_path, arm, mode):
 errors=[]
 if arm not in ("S","M"): errors.append("arm must be S or M")
 if anchors_meta.get("status")!="FROZEN_TOPOLOGY_BOUND_ANCHORS": errors.append("anchors not frozen")
 if sha(anchors_path)!=anchors_meta.get("binary_sha256"): errors.append("anchor hash mismatch")
 if protocol["surface_budget"]["total_predicted_anchors_per_update"]!=16384: errors.append("total anchors must be 16384")
 if protocol["surface_budget"]["total_observed_depth_points_per_update"]!=2048: errors.append("total observed points must be 2048")
 if protocol["arms"]["S"]["views"]!=["A"] or protocol["arms"]["M"]["views"]!=["A","B"]: errors.append("arm view contract invalid")
 if protocol["arms"]["S"]["anchor_counts"]!=[16384] or protocol["arms"]["M"]["anchor_counts"]!=[8192,8192]: errors.append("anchor split invalid")
 if protocol["arms"]["S"]["observed_point_caps"]!=[2048] or protocol["arms"]["M"]["observed_point_caps"]!=[1024,1024]: errors.append("observation split invalid")
 if protocol["input_contract"]!="Camera A RGB + Camera A K + identical dataset ROI": errors.append("input contract changed")
 groups=split.get("groups",{}); sets=[set(groups.get(k,[])) for k in ("TRAIN","VAL","V2_SEALED","FINAL_RESERVE")]
 if any(sets[i]&sets[j] for i in range(4) for j in range(i+1,4)): errors.append("subject leakage")
 if mode!="dry-run" and pairs.get("status") not in ("PASS_FROZEN_MULTIVIEW_PAIR_MANIFEST","FROZEN_GEOMETRY_QA_PASSED","PASS_MULTIVIEW_GEOMETRY_QA"):
  errors.append("pair geometry QA is not final PASS")
 return errors

def rows_from_workset(path):
 d=load(path); rows=d.get("samples",d.get("rows",d.get("pairs",[])))
 for r in rows:
  r["path"]=r.get("observation_npz",r.get("resolved_path"))
 return rows

def best_translation(obs,vertices,iterations=8):
 t=np.zeros(3)
 for _ in range(iterations):
  _,idx=cKDTree(vertices+t).query(obs,workers=-1); step=np.median(obs-(vertices[idx]+t),axis=0); t+=np.clip(step,-.10,.10)
  if np.linalg.norm(step)<1e-5: break
 return t

def aggregate_eval(rows):
 by={}
 for r in rows: by.setdefault(r["subject_id"],[]).append(r)
 subjects=[]
 for sid,v in sorted(by.items()):
  subjects.append({"subject_id":sid,"absolute_median_mm":float(np.median([x["absolute"]["median_mm"] for x in v])),
                   "absolute_p90_mm":float(np.median([x["absolute"]["p90_mm"] for x in v])),
                   "absolute_p95_mm":float(np.median([x["absolute"]["p95_mm"] for x in v])),
                   "translation_aligned_median_mm":float(np.median([x["translation_aligned_median_mm"] for x in v])),
                   "coverage":float(np.median([x["rendered_depth"]["mesh_coverage_of_observed_points"] for x in v]))})
 return {"subject_count":len(subjects),"primary_subject_equal_absolute_median_mm":float(np.mean([x["absolute_median_mm"] for x in subjects])),
         "subject_equal_absolute_p90_mm":float(np.mean([x["absolute_p90_mm"] for x in subjects])),
         "subject_equal_absolute_p95_mm":float(np.mean([x["absolute_p95_mm"] for x in subjects])),
         "diagnostic_translation_aligned_median_mm":float(np.mean([x["translation_aligned_median_mm"] for x in subjects])),
         "median_coverage":float(np.median([x["coverage"] for x in subjects])),"subjects":subjects}

def evaluate_fixed(model,est,ctl,rows,references,faces_np,prepare_batch,recursive_to,maximum=None):
 details=[]
 for r in rows[:maximum]:
  batch,obs=prepare_obs(r["path"],est,prepare_batch,recursive_to)
  refs=[x.cuda() for x in references[r["id"]]["references"]]
  with torch.no_grad(): out,_=model_forward(model,batch,ctl,reference=refs)
  invariant={k:{"tensor_exact_equal":bool(torch.equal(out[k].cpu(),references[r["id"]]["forbidden_outputs"][k])),
                "max_abs_delta":float((out[k].cpu()-references[r["id"]]["forbidden_outputs"][k]).abs().max())}
             for k in ("shape","scale","hand","face")}
  derived=(model.head_pose.scale_mean[None,:]+out["scale"]@model.head_pose.scale_comps).cpu()
  invariant["derived_mhr_scales"]={"tensor_exact_equal":bool(torch.equal(derived,references[r["id"]]["derived_mhr_scales"])),
                                   "max_abs_delta":float((derived-references[r["id"]]["derived_mhr_scales"]).abs().max())}
  va=(out["pred_vertices"]+out["pred_cam_t"][:,None])[0].float().cpu().numpy()
  vb=world_to_camera(camera_to_world(va,obs["R_a"],obs["T_a"]),obs["R_b"],obs["T_b"])
  idx=np.asarray(r.get("point_indices",np.arange(len(obs["points_b"]))),dtype=np.int64); points=obs["points_b"][idx]
  absolute=point_to_triangle(points,vb,faces_np); shift=best_translation(points,vb)
  aligned=float(np.median(point_to_triangle_distances(points,vb+shift,faces_np))*1000)
  depth=rendered_depth(points,vb,faces_np,obs["K_b"],obs["rgb_a"].shape[0],obs["rgb_a"].shape[1])
  details.append({"id":r["id"],"subject_id":r["subject_id"],"absolute":absolute,"forbidden_output_invariance":invariant,
                  "translation_aligned_median_mm":aligned,"oracle_translation_m":shift.tolist(),"rendered_depth":depth})
 return {"contract":"fixed manifest exact point-to-triangle; oracle XYZ-only alignment is diagnostic", "aggregation":aggregate_eval(details),"rows":details}

def prepare_obs(path, estimator, prepare_batch, recursive_to):
 with np.load(path) as z:
  obs={k:z[k].copy() for k in ("rgb_a","bbox_a","K_a","points_a","points_b","R_a","T_a","R_b","T_b","K_b")}
 b=prepare_batch(obs["rgb_a"],estimator.transform,obs["bbox_a"][None].astype(np.float32),None,None)
 b=recursive_to(b,"cuda"); b["cam_int"]=torch.as_tensor(obs["K_a"][None],device="cuda").to(b["img"])
 return b,obs

def model_forward(model,batch,controller,reference=None,capture=False):
 model._initialize_batch(batch)
 if capture: controller.begin_reference_capture()
 if reference is not None: controller.use_frozen_output_reference(reference)
 out=model.forward_step(batch,decoder_type="body")["mhr"]
 if reference is not None: controller.clear_frozen_output_reference()
 return out,(controller.end_reference_capture() if capture else None)

def surface_points(vertices,faces,ids,bary):
 return (vertices[:,faces[ids]]*bary[None,:,:,None]).sum(2)

def huber_nn(observed,predicted,delta=.03):
 d=torch.cdist(observed[None],predicted).amin(-1)[0]
 return torch.where(d<delta,.5*d.square()/delta,d-.5*delta).mean()

def transform_a_to_b(va,obs):
 q=lambda k:torch.as_tensor(obs[k],device=va.device,dtype=va.dtype)
 return (va-q("T_a"))@q("R_a")@q("R_b").T+q("T_b")

def arm_surface_loss(arm,verts_a,obs,faces,ids,bary,protocol,row_id,update):
 cfg=protocol["arms"][arm]; losses=[]; offset=0
 for view,n_anchor,n_obs in zip(cfg["views"],cfg["anchor_counts"],cfg["observed_point_caps"]):
  v=verts_a if view=="A" else transform_a_to_b(verts_a,obs)
  predicted=surface_points(v,faces,ids[offset:offset+n_anchor],bary[offset:offset+n_anchor]); offset+=n_anchor
  points=obs["points_a" if view=="A" else "points_b"]
  seed=int(hashlib.sha256(f"{protocol['seed']}:{row_id}:{update}:{view}".encode()).hexdigest()[:16],16)
  sel=np.random.default_rng(seed).choice(len(points),min(n_obs,len(points)),replace=False)
  observed=torch.as_tensor(points[sel],device=v.device,dtype=v.dtype)
  losses.append(huber_nn(observed,predicted,protocol["loss"]["huber_delta_m"]))
 return torch.stack(losses).mean()

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--mode",choices=("dry-run","smoke","train"),required=True); ap.add_argument("--arm",choices=("S","M"),required=True); ap.add_argument("--seed",type=int)
 for n in ("protocol","split","pairs","anchors-meta","anchors","workset","eval-manifest","sam-repo","checkpoint","mhr","output-dir","resume"): ap.add_argument("--"+n,type=Path,required=n not in ("workset","eval-manifest","sam-repo","checkpoint","mhr","output-dir","resume"))
 a=ap.parse_args(); protocol,split,pairs,am=map(load,(a.protocol,a.split,a.pairs,a.anchors_meta))
 errors=validate_contract(protocol,split,pairs,am,a.anchors,a.arm,a.mode)
 report={"status":"DRY_RUN_VALID" if not errors else "NOT_READY","arm":a.arm,"mode":a.mode,"errors":errors,
         "formal_training_started":False,"sealed_opened":False,"final_reserve_opened":False,
         "hashes":{k:sha(v) for k,v in {"protocol":a.protocol,"split":a.split,"pairs":a.pairs,"anchors":a.anchors}.items()}}
 if a.mode=="dry-run": print(json.dumps(report,indent=2)); return
 if errors: raise RuntimeError(errors)
 if any(x is None for x in (a.workset,a.eval_manifest,a.sam_repo,a.checkpoint,a.mhr,a.output_dir)): raise ValueError("runtime paths required")
 rows=[r for r in rows_from_workset(a.workset) if r.get("split","TRAIN")=="TRAIN"]
 if not rows: raise RuntimeError("no materialized TRAIN rows")
 val_rows=rows_from_workset(a.eval_manifest)
 if a.mode=="smoke": rows=rows[:min(2,len(rows))]; val_rows=val_rows[:1]
 elif protocol.get("readiness_gate")!="READY_FOR_SINGLE_MULTI_AB": raise RuntimeError("formal training requires readiness gate")
 sys.path.insert(0,str(a.sam_repo)); from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
 from sam_3d_body.data.utils.prepare_batch import prepare_batch
 from sam_3d_body.utils import recursive_to
 run_seed=protocol["seed"] if a.seed is None else a.seed
 if run_seed not in protocol.get("paired_seeds",[protocol["seed"]]): raise RuntimeError("seed is not pre-registered")
 torch.manual_seed(run_seed); np.random.seed(run_seed)
 model,cfg=load_sam_3d_body(str(a.checkpoint),device="cuda",mhr_path=str(a.mhr)); model.eval()
 ctl=PoseCameraOutputFreeze(model); est=SAM3DBodyEstimator(model,cfg); faces=model.head_pose.faces.long()
 initial_trainable={n:p.detach().clone() for n,p in model.named_parameters() if p.requires_grad}
 z=np.load(a.anchors); ids=torch.as_tensor(z["face_index"],device="cuda"); bary=torch.as_tensor(z["barycentric"],device="cuda")
 # Cache Official six-stage references and teacher outputs before any update.
 cache={}
 with torch.no_grad():
  for r in rows+val_rows:
   batch,obs=prepare_obs(r["path"],est,prepare_batch,recursive_to); out,refs=model_forward(model,batch,ctl,capture=True)
   cache[r["id"]]={"references":[x.cpu() for x in refs],"kp2":out["pred_keypoints_2d"].cpu(),"kp3":out["pred_keypoints_3d"].cpu(),
                    "forbidden_outputs":{k:out[k].cpu().clone() for k in ("shape","scale","hand","face")},
                    "derived_mhr_scales":(model.head_pose.scale_mean[None,:]+out["scale"]@model.head_pose.scale_comps).cpu().clone()}
 opt=torch.optim.AdamW(list(ctl.parameters()),lr=protocol["optimizer"]["lr"],weight_decay=protocol["optimizer"]["weight_decay"])
 max_updates=protocol["smoke_updates"] if a.mode=="smoke" else protocol["max_updates"]
 order_ids=deterministic_update_order(rows,max_updates,run_seed); row_by_id={r["id"]:r for r in rows}
 order_sha256=hashlib.sha256("\n".join(order_ids).encode()).hexdigest()
 start_update=1; history=[]; best=None; bad_validations=0
 if a.resume:
  saved=torch.load(a.resume,map_location="cuda",weights_only=False)
  if saved["protocol_sha256"]!=sha(a.protocol) or saved["workset_sha256"]!=sha(a.workset): raise RuntimeError("resume provenance mismatch")
  if saved.get("run_seed")!=run_seed or saved.get("update_order_sha256")!=order_sha256: raise RuntimeError("resume update order mismatch")
  for n,p in model.named_parameters():
   if n in saved["model_trainable"]: p.data.copy_(saved["model_trainable"][n].to(p))
  opt.load_state_dict(saved["optimizer"]); start_update=saved["updates"]+1; history=saved["history"]; best=saved.get("best"); bad_validations=saved.get("bad_validations",0)
 started=time.time(); validation_every=(max_updates if a.mode=="smoke" else protocol["validation_every_n_updates"]); patience=protocol.get("early_stop_patience_validations",0)
 a.output_dir.mkdir(parents=True,exist_ok=True)
 for update in range(start_update,max_updates+1):
  r=row_by_id[order_ids[update-1]]; batch,obs=prepare_obs(r["path"],est,prepare_batch,recursive_to)
  refs=[x.cuda() for x in cache[r["id"]]["references"]]; out,_=model_forward(model,batch,ctl,reference=refs)
  verts=out["pred_vertices"]+out["pred_cam_t"][:,None]
  surface=arm_surface_loss(a.arm,verts,obs,faces,ids,bary,protocol,r["id"],update)
  t=cache[r["id"]]; p2=out["pred_keypoints_2d"]; t2=t["kp2"].to(p2); p3=out["pred_keypoints_3d"]; t3=t["kp3"].to(p3)
  size=p2.new_tensor([obs["rgb_a"].shape[1],obs["rgb_a"].shape[0]])
  teacher2=F.smooth_l1_loss(p2/size,t2/size)
  pelvis=model.pelvis_idx; teacher3=F.smooth_l1_loss(p3-p3[:,pelvis].mean(1,keepdim=True),t3-t3[:,pelvis].mean(1,keepdim=True))
  anchor=torch.stack([F.mse_loss(p,initial_trainable[n]) for n,p in model.named_parameters() if p.requires_grad]).mean()
  w=protocol["loss"]["weights"]; loss=w["surface"]*surface+w["teacher_joint_2d"]*teacher2+w["teacher_relative_3d"]*teacher3+w["head_anchor"]*anchor
  opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(list(ctl.parameters()),protocol["optimizer"]["gradient_clip_norm"]); opt.step(); ctl.restore_after_step(opt)
  history.append({"update":update,"id":r["id"],"loss":float(loss),"surface":float(surface),"teacher2d":float(teacher2),"teacher3d":float(teacher3),"head_anchor":float(anchor)})
  if update%validation_every==0 or update==max_updates:
   ev=evaluate_fixed(model,est,ctl,val_rows,cache,faces.cpu().numpy(),prepare_batch,recursive_to,maximum=1 if a.mode=="smoke" else None)
   metric=ev["aggregation"]["primary_subject_equal_absolute_median_mm"]; history[-1]["fixed_val"]=ev
   improved=best is None or metric<best["metric"]
   if improved: best={"update":update,"metric":metric}; bad_validations=0
   else: bad_validations+=1
   ck={"status":"V2_RESEARCH_CHECKPOINT","arm":a.arm,"model_trainable":{n:p.detach().cpu() for n,p in model.named_parameters() if p.requires_grad},
       "optimizer":opt.state_dict(),"protocol_sha256":sha(a.protocol),"workset_sha256":sha(a.workset),"eval_manifest_sha256":sha(a.eval_manifest),
       "updates":update,"history":history,"best":best,"bad_validations":bad_validations,"run_seed":run_seed,"update_order_sha256":order_sha256}
   torch.save(ck,a.output_dir/f"checkpoint_update_{update:06d}.pt")
   if a.mode=="train" and patience and bad_validations>=patience: break
 payload={"status":"SMOKE_COMPLETED_NO_FORMAL_TRAINING" if a.mode=="smoke" else "TRAINING_COMPLETED",
          "arm":a.arm,"run_seed":run_seed,"optimizer_updates":history[-1]["update"],"history":history,"seconds":time.time()-started,
          "update_order_sha256":order_sha256,"update_order_preview":order_ids[:10],
          "exact_freeze_rows":ctl.forbidden_parameter_rows_exact(),"official_reference_passes_cached":len(cache),
          "total_predicted_anchors_per_update":16384,"total_observed_points_per_update":2048,
          "input_contract":protocol["input_contract"],"sealed_opened":False,"final_reserve_opened":False}
 (a.output_dir/"run_report.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
 torch.save({"status":"V2_RESEARCH_CHECKPOINT","arm":a.arm,"model_trainable":{n:p.detach().cpu() for n,p in model.named_parameters() if p.requires_grad},
             "optimizer":opt.state_dict(),"protocol_sha256":sha(a.protocol),"workset_sha256":sha(a.workset),"updates":history[-1]["update"],"history":history,"best":best,"bad_validations":bad_validations,"run_seed":run_seed,"update_order_sha256":order_sha256},a.output_dir/"checkpoint.pt")
 print(json.dumps({k:payload[k] for k in ("status","arm","optimizer_updates","seconds")},indent=2))
if __name__=="__main__": main()



