"""Run MHR-parameter-to-DMD37 sensitivity on previously consumed real-image states.

Execute on the SAM3D server environment. This is not an image-network benchmark.
"""
from __future__ import annotations

import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
import torch


def stats(x):
    a=np.asarray(x,float)
    return {"mean":float(a.mean()),"median":float(np.median(a)),"p90":float(np.quantile(a,.9)),"p95":float(np.quantile(a,.95)),"max":float(a.max())}


def anchors(vertices, face_ids, bary, faces):
    return (vertices[:,faces[face_ids]]*bary[None,:,:,None]).sum(2)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mhr',required=True);ap.add_argument('--atlas',required=True);ap.add_argument('--seeds',nargs='+',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    atlas=json.loads(Path(a.atlas).read_text())
    face_ids=np.array([p['mhr_face_index'] for p in atlas['points']],np.int64)
    bary=np.array([p['barycentric'] for p in atlas['points']],np.float32)
    point_ids=[p['engineering_point_id'] for p in atlas['points']]
    model=torch.jit.load(a.mhr,map_location='cuda').eval()
    faces=model.character_torch.mesh.faces.cpu().numpy().astype(np.int64)
    names=list(model.get_parameter_names())[:204]
    seeds=[]
    for path in a.seeds:
        z=np.load(path)
        needed=['shape_params','mhr_model_params','expr_params','pred_cam_t','focal_length']
        if not all(k in z.files for k in needed): continue
        seeds.append({"id":Path(path).parent.name,"path":path,"shape":z['shape_params'].astype(np.float32),"params":z['mhr_model_params'].astype(np.float32),"expr":z['expr_params'].astype(np.float32),"cam":z['pred_cam_t'].astype(np.float32),"focal":float(z['focal_length'])})
    assert len(seeds)>=6
    records=[]
    parameter_contract={"translation":"applied as exact output-space metric displacement; no MHR parameter-unit assumption",
      "global_rotation":{"indices":[0,1,2],"model_parameter_indices":[3,4,5],"names":names[3:6],"units":"radians"},
      "spine_pose":{"indices":list(range(6,24)),"names":names[6:24],"units":"radians; one parameter at a time"},
      "shoulder_pose":{"indices":list(range(30,46)),"names":names[30:46],"units":"radians; one parameter at a time"},
      "hip_pelvis_pose":{"indices":[50,51,52,59,60,61],"names":[names[i] for i in [50,51,52,59,60,61]],"units":"radians; one parameter at a time"},
      "shape":{"indices":list(range(5)),"units":"identity PCA coefficient; one coefficient at a time"},
      "scale":{"indices":list(range(139,151)),"names":names[139:151],"units":"direct model scale parameter additive delta; one parameter at a time"}}
    for seed in seeds:
        shape=torch.from_numpy(seed['shape'])[None].cuda(); params=torch.from_numpy(seed['params'])[None].cuda(); expr=torch.from_numpy(seed['expr'])[None].cuda()
        with torch.inference_mode(): base_v=model(shape,params,expr)[0][0].float().cpu().numpy()/100.0
        base=anchors(base_v[None],face_ids,bary,faces)[0]
        tri=base_v[faces[face_ids]]
        normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-12)
        variants=[]
        for magnitude in [10,20,50,100]:
            if magnitude==100: axes=[2]
            else: axes=range(3)
            for axis in axes:
                for sign in [-1,1]:
                    q=base.copy();q[:,axis]+=sign*magnitude/1000
                    variants.append(("TRANSLATION",magnitude,f"axis{axis}_{sign:+d}",q))
        specs=[("GLOBAL_ROTATION",[3,4,5],[1,3,5],math.pi/180),
               ("SPINE_POSE",list(range(6,24)),[1,3,5],math.pi/180),
               ("SHOULDER_POSE",list(range(30,46)),[1,3,5],math.pi/180),
               ("HIP_PELVIS_POSE",[50,51,52,59,60,61],[1,3,5],math.pi/180)]
        for cat,indices,mags,factor in specs:
            pp=[];meta=[]
            for mag in mags:
                for idx in indices:
                    for sign in [-1,1]:
                        x=seed['params'].copy();x[idx]+=sign*mag*factor;pp.append(x);meta.append((cat,mag,f"{names[idx]}_{sign:+d}"))
            with torch.inference_mode(): vv=model(shape.repeat(len(pp),1),torch.from_numpy(np.stack(pp)).cuda(),expr.repeat(len(pp),1))[0].float().cpu().numpy()/100
            aa=anchors(vv,face_ids,bary,faces)
            variants.extend((m[0],m[1],m[2],q) for m,q in zip(meta,aa))
        for cat,indices,mags in [("SHAPE",range(5),[.25,.5,1.0])]:
            ss=[];meta=[]
            for mag in mags:
                for idx in indices:
                    for sign in [-1,1]:
                        x=seed['shape'].copy();x[idx]+=sign*mag;ss.append(x);meta.append((cat,mag,f"shape_pc{idx}_{sign:+d}"))
            with torch.inference_mode(): vv=model(torch.from_numpy(np.stack(ss)).cuda(),params.repeat(len(ss),1),expr.repeat(len(ss),1))[0].float().cpu().numpy()/100
            aa=anchors(vv,face_ids,bary,faces);variants.extend((m[0],m[1],m[2],q) for m,q in zip(meta,aa))
        pp=[];meta=[]
        for mag in [.01,.03,.05]:
            for idx in range(139,151):
                for sign in [-1,1]:
                    x=seed['params'].copy();x[idx]+=sign*mag;pp.append(x);meta.append(("SCALE",mag,f"{names[idx]}_{sign:+d}"))
        with torch.inference_mode(): vv=model(shape.repeat(len(pp),1),torch.from_numpy(np.stack(pp)).cuda(),expr.repeat(len(pp),1))[0].float().cpu().numpy()/100
        aa=anchors(vv,face_ids,bary,faces);variants.extend((m[0],m[1],m[2],q) for m,q in zip(meta,aa))
        for cat,mag,label,q in variants:
            d=q-base;aligned=d-d.mean(0,keepdims=True);normal_mm=np.abs((d*normal).sum(1))*1000;tangent_mm=np.sqrt(np.maximum(np.sum(d*d,1)*1e6-normal_mm**2,0))
            cam=seed['cam']; f=seed['focal']; bcam=base+cam; qcam=q+cam
            uv0=bcam[:,:2]/bcam[:,2:3]*f+np.array([960,540]);uv=qcam[:,:2]/qcam[:,2:3]*f+np.array([960,540])
            for i,pid in enumerate(point_ids):
                records.append({"seed":seed['id'],"category":cat,"magnitude":mag,"variant":label,"point_id":pid,"error_3d_mm":float(np.linalg.norm(d[i])*1000),"aligned_3d_mm":float(np.linalg.norm(aligned[i])*1000),"normal_mm":float(normal_mm[i]),"tangential_mm":float(tangent_mm[i]),"projection_px":float(np.linalg.norm(uv[i]-uv0[i]))})
    summaries=[]
    cats=sorted(set(r['category'] for r in records))
    for cat in cats:
      mags=sorted(set(r['magnitude'] for r in records if r['category']==cat))
      for mag in mags:
       rr=[r for r in records if r['category']==cat and r['magnitude']==mag]
       summaries.append({"category":cat,"magnitude":mag,"count":len(rr),"error_3d_mm":stats([r['error_3d_mm'] for r in rr]),"aligned_3d_mm":stats([r['aligned_3d_mm'] for r in rr]),"normal_mm":stats([r['normal_mm'] for r in rr]),"tangential_mm":stats([r['tangential_mm'] for r in rr]),"projection_px":stats([r['projection_px'] for r in rr])})
    seed_doc={"schema":"DMD37_SENSITIVITY_SEED_SET_V1","status":"FROZEN","count":len(seeds),"source":"Previously consumed/reviewed real-image SAM MHR states; not medical or HuMMan GT","seeds":[{"id":s['id'],"path":s['path']} for s in seeds]}
    result={"schema":"DMD37_PARAMETER_SENSITIVITY_V1","status":"COMPLETED_ENGINEERING_DIAGNOSTIC","seed_count":len(seeds),"point_count":37,"parameter_contract":parameter_contract,"summary":summaries,"per_observation":records,"medical_truth":False}
    nt={"schema":"DMD37_NORMAL_TANGENTIAL_SENSITIVITY_V1","status":"COMPLETED","normal_contract":"baseline MHR anchor triangle unit normal; absolute signed projection reported","tangential_contract":"Euclidean residual after removing local-normal component","summary":summaries,"limitations":["MHR triangle normals are geometric normals, not tissue normals.","Projection assumes the stored 1920x1080 camera convention of these reviewed inputs."]}
    for n,x in [('DMD37_SENSITIVITY_SEED_SET_V1.json',seed_doc),('DMD37_PARAMETER_SENSITIVITY_V1.json',result),('DMD37_NORMAL_TANGENTIAL_SENSITIVITY_V1.json',nt)]: (out/n).write_text(json.dumps(x,indent=2),encoding='utf8')
    print(json.dumps({"seeds":len(seeds),"records":len(records),"summaries":len(summaries)}))

if __name__=='__main__': main()
