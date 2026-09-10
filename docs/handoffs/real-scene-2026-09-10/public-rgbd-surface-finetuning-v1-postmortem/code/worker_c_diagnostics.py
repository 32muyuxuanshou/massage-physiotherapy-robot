"""Read-only Worker-C diagnostics for the V1 RGB-D surface pilot.

No optimizer is constructed and no checkpoint is modified.  Translation fitting is
used only as a post-hoc diagnostic; it consumes evaluation geometry and is not a
deployable inference operation.
"""
from __future__ import annotations

import argparse, json, math, sys
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from scipy.spatial import cKDTree


def dump(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def summary(x):
    x=np.asarray(x,float)
    return {"count":int(x.size),"mean":float(x.mean()),"median":float(np.median(x)),
            "p90":float(np.percentile(x,90)),"p95":float(np.percentile(x,95)),"max":float(x.max())}


def sample_surface(v, f, n, rng, area_weighted=False):
    tri=v[f]
    if area_weighted:
        area=torch.linalg.vector_norm(torch.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0],dim=-1),dim=-1)/2
        ids=torch.multinomial(area/area.sum(),n,replacement=True,generator=rng)
    else:
        ids=torch.randperm(len(f),generator=rng,device=v.device)[:min(n,len(f))]
    u=torch.rand(len(ids),generator=rng,device=v.device,dtype=v.dtype)
    w=torch.rand(len(ids),generator=rng,device=v.device,dtype=v.dtype)
    flip=u+w>1; u=torch.where(flip,1-u,u); w=torch.where(flip,1-w,w)
    t=tri[ids]
    return t[:,0]+u[:,None]*(t[:,1]-t[:,0])+w[:,None]*(t[:,2]-t[:,0])


def approx_loss(v,f,obs,n,seed,area=False,delta=.03):
    g=torch.Generator(device=v.device); g.manual_seed(seed)
    surf=sample_surface(v,f,n,g,area)
    d=torch.cdist(obs[None],surf[None]).amin(-1)[0]
    return torch.where(d<delta,.5*d.square()/delta,d-.5*delta).mean()


def toy_audits(out: Path):
    # A non-uniform 100x100 planar grid has >16k unequal-area triangles and
    # exposes face-index-uniform sampling bias without hitting the V1 no-replacement cap.
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    q=torch.linspace(0,1,100,dtype=torch.float32,device=device); xx,yy=torch.meshgrid(q.square(),q,indexing='xy')
    v0=torch.stack((xx.reshape(-1),yy.reshape(-1),torch.zeros(10000,device=device)),1)
    ff=[]
    for y in range(99):
      for x in range(99):
       i=y*100+x; ff.extend(((i,i+1,i+100),(i+1,i+101,i+100)))
    f=torch.tensor(ff,dtype=torch.long,device=device)
    counts=[4096,8192,16384]; seeds=list(range(5)); perfect=[]; stability=[]
    for area in (False,True):
      label="area_weighted" if area else "face_uniform"
      for n in counts:
        losses=[]; grads=[]
        for seed in seeds:
          g=torch.Generator(device=device); g.manual_seed(991+seed)
          obs=sample_surface(v0,f,1024,g,True).detach()
          v=v0.clone().requires_grad_(True); loss=approx_loss(v,f,obs,n,seed,area); loss.backward()
          losses.append(float(loss)*1000); grads.append(v.grad.flatten().cpu().numpy())
        cos=[]
        for a,b in zip(grads[:-1],grads[1:]): cos.append(float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)+1e-15)))
        row={"sampler":label,"samples":n,"loss_mm_equivalent":summary(losses),
             "gradient_norm":summary([np.linalg.norm(x) for x in grads]),"adjacent_seed_gradient_cosine":summary(cos)}
        perfect.append(row)
        # Repeat on a fixed +30 mm Z perturbation, where a meaningful nonzero
        # gradient exists and cosine stability is interpretable.
        losses=[]; grads=[]
        fixed_g=torch.Generator(device=device); fixed_g.manual_seed(4242)
        fixed_obs=sample_surface(v0,f,1024,fixed_g,True).detach()
        for seed in seeds:
          v=(v0+v0.new_tensor([0,0,.03])).clone().requires_grad_(True)
          loss=approx_loss(v,f,fixed_obs,n,seed,area); loss.backward()
          losses.append(float(loss)*1000); grads.append(v.grad.flatten().cpu().numpy())
        cos=[float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)+1e-15)) for a,b in zip(grads[:-1],grads[1:])]
        stability.append({"sampler":label,"samples":n,"fixed_perturbation":"+30mm Z",
          "loss_mm_equivalent":summary(losses),"gradient_norm":summary([np.linalg.norm(x) for x in grads]),
          "adjacent_seed_gradient_cosine":summary(cos)})
    # Direction test: derivative wrt translation must point in perturbation direction,
    # so gradient descent points back to zero.
    directions=[]
    g=torch.Generator(device=device); g.manual_seed(7); obs=sample_surface(v0,f,2048,g,True).detach()
    for axis in range(3):
      for sign in (-1,1):
        t=torch.zeros(3,dtype=torch.float32,device=device,requires_grad=True); t.data[axis]=sign*.05
        loss=approx_loss(v0+t,f,obs,16384,77,True); loss.backward()
        expected=sign
        directions.append({"axis":"XYZ"[axis],"perturbation_mm":sign*50,
          "loss":float(loss),"gradient":t.grad.tolist(),"correct_return_direction":bool(sign*float(t.grad[axis])>0)})
    center=v0.mean(0)
    for axis in range(3):
      for sign in (-1,1):
        angle=torch.tensor(sign*math.radians(3),dtype=torch.float32,device=device,requires_grad=True)
        z=torch.zeros((),device=device); o=torch.ones((),device=device); c=torch.cos(angle); s=torch.sin(angle)
        if axis==0: R=torch.stack((o,z,z,z,c,-s,z,s,c)).reshape(3,3)
        elif axis==1: R=torch.stack((c,z,s,z,o,z,-s,z,c)).reshape(3,3)
        else: R=torch.stack((c,-s,z,s,c,z,z,z,o)).reshape(3,3)
        vr=(v0-center)@R.T+center; loss=approx_loss(vr,f,obs,16384,77,True); loss.backward()
        directions.append({"axis":"rotation_"+"XYZ"[axis],"perturbation_degrees":sign*3,
          "loss":float(loss),"gradient_dloss_dangle":float(angle.grad),"correct_return_direction":bool(sign*float(angle.grad)>0)})
    dump(out/"SURFACE_LOSS_PERFECT_GEOMETRY_TEST_V1.json",{"status":"COMPLETED","note":"Approximate sampled-to-sampled loss; nonzero value is the approximation floor, not geometry error.","rows":perfect})
    dump(out/"SURFACE_LOSS_SAMPLING_STABILITY_V1.json",{"status":"COMPLETED","perfect_geometry_rows":perfect,"perturbed_geometry_rows":stability})
    dump(out/"SURFACE_LOSS_DIRECTIONAL_GRADIENT_TEST_V1.json",{"status":"COMPLETED","rows":directions,
      "all_translation_directions_correct":all(x["correct_return_direction"] for x in directions),
      "pose_parameter_test":"NOT_APPLICABLE_TO_THIS_TOY_MESH_WITHOUT_A_KINEMATIC_BODY_MODEL"})
    dump(out/"AREA_WEIGHTED_SAMPLING_COMPARISON_V1.json",{"status":"COMPLETED_TOY_AUDIT_ONLY","rows":perfect,
      "decision_rule":"DEV/model-gradient evidence is required before changing the training loss."})


def best_translation(obs, vertices, iterations=8):
    t=np.zeros(3)
    for _ in range(iterations):
        tree=cKDTree(vertices+t); _,idx=tree.query(obs,workers=-1)
        residual=obs-(vertices[idx]+t)
        step=np.median(residual,axis=0)
        t+=np.clip(step,-.10,.10)
        if np.linalg.norm(step)<1e-5: break
    return t


def exact_median(obs,vertices,faces,ptdist):
    return float(np.median(ptdist(obs,vertices,faces))*1000)


def load_rows(manifest):
    d=json.loads(Path(manifest).read_text()); return d["samples"]


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--historical-code",type=Path)
    ap.add_argument("--sam-repo",type=Path); ap.add_argument("--official",type=Path); ap.add_argument("--mhr",type=Path)
    ap.add_argument("--e1",type=Path); ap.add_argument("--train-val-manifest",type=Path); ap.add_argument("--sealed-manifest",type=Path)
    args=ap.parse_args(); toy_audits(args.out)
    if not args.sam_repo: return
    old=args.historical_code or (Path(__file__).resolve().parents[2]/"real-scene-2026-09-09"/"public-rgbd-surface-finetuning-pilot-v1"/"code")
    sys.path.insert(0,str(old)); sys.path.insert(0,str(args.sam_repo))
    from sam_3d_body import SAM3DBodyEstimator,load_sam_3d_body
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    from train_rgbd_surface import forward_observation
    from surface_metrics import camera_to_world,world_to_camera,point_to_triangle_distances
    rows=load_rows(args.train_val_manifest)+load_rows(args.sealed_manifest)
    model,cfg=load_sam_3d_body(str(args.official),device="cuda",mhr_path=str(args.mhr)); model.eval().requires_grad_(False)
    est=SAM3DBodyEstimator(model,cfg); faces=model.head_pose.faces.detach().cpu().numpy().astype(np.int64)
    preds={}
    def run(tag):
      with torch.inference_mode():
       for r in rows:
        out,_=forward_observation(model,est,prepare_batch,recursive_to,Path(r["observation_npz"]))
        preds[(tag,r["id"])]=(out["pred_vertices"]+out["pred_cam_t"][:,None,:])[0].cpu().numpy(),out["pred_cam_t"][0].cpu().numpy()
    run("official")
    ck=torch.load(args.e1,map_location="cpu",weights_only=False); model.head_pose.proj.load_state_dict(ck["heads"]["pose"]); model.head_camera.proj.load_state_dict(ck["heads"]["camera"]); run("e1")
    # Fit constant Camera-A translation bias only on TRAIN observations.
    train_bias=[]; per=[]
    for r in rows:
      with np.load(r["observation_npz"]) as z:
       va,cam=preds[("official",r["id"])]; va1,cam1=preds[("e1",r["id"])]
       if r["split"].upper()=="TRAIN": train_bias.append(best_translation(z["points_a"],va))
    bias=np.median(np.stack(train_bias),axis=0)
    for r in rows:
      split=r["split"].upper()
      with np.load(r["observation_npz"]) as z:
       va,cam=preds[("official",r["id"])]; ve,ecam=preds[("e1",r["id"])]
       # All reported evaluation geometry is Camera B for VAL/CONSUMED SEALED; TRAIN uses A only to fit b.
       if split=="TRAIN": continue
       obs=z["points_b"].astype(float); rng=np.random.default_rng(20260910); obs=obs[rng.choice(len(obs),min(10000,len(obs)),False)]
       vo=world_to_camera(camera_to_world(va,z["R_a"],z["T_a"]),z["R_b"],z["T_b"])
       vv=world_to_camera(camera_to_world(ve,z["R_a"],z["T_a"]),z["R_b"],z["T_b"])
       vb=world_to_camera(camera_to_world(va+bias,z["R_a"],z["T_a"]),z["R_b"],z["T_b"])
       to=best_translation(obs,vo); te=best_translation(obs,vv)
       per.append({"id":r["id"],"subject_id":r["subject_id"],"split":split,
        "official_absolute_mm":exact_median(obs,vo,faces,point_to_triangle_distances),
        "e1_absolute_mm":exact_median(obs,vv,faces,point_to_triangle_distances),
        "official_translation_aligned_mm":exact_median(obs,vo+to,faces,point_to_triangle_distances),
        "e1_translation_aligned_mm":exact_median(obs,vv+te,faces,point_to_triangle_distances),
        "train_constant_bias_mm":exact_median(obs,vb,faces,point_to_triangle_distances),
        "oracle_translation_official_m":to.tolist(),"oracle_translation_e1_m":te.tolist(),
        "pred_cam_t_official_m":cam.tolist(),"pred_cam_t_e1_m":ecam.tolist()})
    def aggregate(split,key):
      by={}
      for x in per:
       if x["split"]==split: by.setdefault(x["subject_id"],[]).append(x[key])
      return float(np.mean([np.median(v) for v in by.values()]))
    table={s:{k:aggregate(s,k) for k in ("official_absolute_mm","e1_absolute_mm","official_translation_aligned_mm","e1_translation_aligned_mm","train_constant_bias_mm")} for s in ("VAL","SEALED")}
    dump(args.out/"ABSOLUTE_VS_TRANSLATION_ALIGNED_V1.json",{"status":"CONSUMED_TEST_POSTHOC_ANALYSIS","method":"robust translation-only ICP diagnostic; evaluation geometry is consumed; no rotation/scale","subject_macro_mm":table,"rows":per})
    dump(args.out/"SIMPLE_TRANSLATION_BASELINE_V1.json",{"status":"CONSUMED_TEST_POSTHOC_ANALYSIS","fit_split":"TRAIN Camera A only","constant_bias_camera_a_m":bias.tolist(),"subject_macro_mm":table,"rows":per})
    # Root/camera correlation, explicitly non-causal.
    for x in per:
      x["camera_delta_norm_m"]=float(np.linalg.norm(np.asarray(x["pred_cam_t_e1_m"])-x["pred_cam_t_official_m"]))
      x["absolute_improvement_mm"]=x["official_absolute_mm"]-x["e1_absolute_mm"]
    corr=float(np.corrcoef([x["camera_delta_norm_m"] for x in per],[x["absolute_improvement_mm"] for x in per])[0,1])
    dump(args.out/"ROOT_CAMERA_CORRECTION_ANALYSIS_V1.json",{"status":"POSTHOC_CORRELATION_NOT_CAUSATION","pearson_camera_delta_norm_vs_surface_improvement":corr,"rows":per})

if __name__=="__main__": main()
