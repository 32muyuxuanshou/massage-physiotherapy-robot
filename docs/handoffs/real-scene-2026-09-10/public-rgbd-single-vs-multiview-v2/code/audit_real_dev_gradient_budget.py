import argparse, json, sys
from pathlib import Path
import numpy as np
import torch

ap=argparse.ArgumentParser(); ap.add_argument('--sam-repo',type=Path,required=True); ap.add_argument('--official',type=Path,required=True); ap.add_argument('--mhr',type=Path,required=True); ap.add_argument('--trainer',type=Path,required=True); ap.add_argument('--anchors',type=Path,required=True); ap.add_argument('--dev-dir',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
sys.path[:0]=[str(a.sam_repo),str(a.trainer.parent)]
from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
from sam_3d_body.utils import recursive_to
from sam_3d_body.data.utils.prepare_batch import prepare_batch
from train_rgbd_surface import forward_observation

model,cfg=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr)); model.eval().requires_grad_(False)
model.head_pose.proj.requires_grad_(True); model.head_camera.proj.requires_grad_(True)
est=SAM3DBodyEstimator(model,cfg); f=model.head_pose.faces.detach().long()
an=np.load(a.anchors); ids=an['face_index']; bary=an['barycentric']
rows=[]
for path in sorted(a.dev_dir.glob('*.npz'))[:3]:
 z=np.load(path); out,obs=forward_observation(model,est,prepare_batch,recursive_to,path)
 va=out['pred_vertices']+out['pred_cam_t'][:,None]
 Ra=torch.as_tensor(z['R_a'],device='cuda',dtype=va.dtype); Ta=torch.as_tensor(z['T_a'],device='cuda',dtype=va.dtype)
 Rb=torch.as_tensor(z['R_b'],device='cuda',dtype=va.dtype); Tb=torch.as_tensor(z['T_b'],device='cuda',dtype=va.dtype)
 vw=(va-Ta)@Ra; vb=vw@Rb.T+Tb
 arm={}
 for name, specs in [('single',[(va,z['points_a'],0,16384,2048)]),('multi',[(va,z['points_a'],0,8192,1024),(vb,z['points_b'],8192,8192,1024)])]:
  losses=[]
  for vv,oo,off,n,no in specs:
   fid=torch.as_tensor(ids[off:off+n],device='cuda'); bw=torch.as_tensor(bary[off:off+n],device='cuda',dtype=vv.dtype)
   surf=(vv[:,f[fid]]*bw[None,:,:,None]).sum(2)
   rng=np.random.default_rng(20260910+off); sel=rng.choice(len(oo),min(no,len(oo)),replace=False)
   pts=torch.as_tensor(oo[sel],device='cuda',dtype=vv.dtype)
   d=torch.cdist(pts[None],surf).amin(-1)[0]; losses.append(torch.where(d<.03,.5*d.square()/.03,d-.015).mean())
  loss=torch.stack(losses).mean()
  pp=list(model.head_pose.proj.parameters()); cp=list(model.head_camera.proj.parameters())
  gg=torch.autograd.grad(loss,pp+cp,retain_graph=True); gp=gg[:len(pp)]; gc=gg[len(pp):]
  pnorm=torch.sqrt(sum(g.square().sum() for g in gp)); cnorm=torch.sqrt(sum(g.square().sum() for g in gc)); jnorm=torch.sqrt(pnorm.square()+cnorm.square())
  arm[name]={'loss':float(loss),'pose_projection_gradient_norm':float(pnorm),'camera_projection_gradient_norm':float(cnorm),'joint_gradient_norm':float(jnorm)}
 rows.append({'id':path.stem,'arms':arm,'ratios_multi_over_single':{k:arm['multi'][k]/arm['single'][k] for k in ['pose_projection_gradient_norm','camera_projection_gradient_norm','joint_gradient_norm']}})
ratios={k:[r['ratios_multi_over_single'][k] for r in rows] for k in rows[0]['ratios_multi_over_single']}
result={'status':'PASS_REAL_DEV_GRADIENT_SAME_ORDER' if all(.25<=np.median(v)<=4 for v in ratios.values()) else 'FAIL_GRADIENT_SCALE','samples':rows,'median_ratios_multi_over_single':{k:float(np.median(v)) for k,v in ratios.items()},'contracts':{'single':'2048 observations A, 16384 anchors A','multi':'1024 observations A + 1024 observations B; 8192 anchors A + 8192 anchors B; view mean','same_RGB_input':'Camera A only'},'boundary':'Uses historical non-SEALED DEV solely for readiness diagnostics; no training or model update.'}
a.out.write_text(json.dumps(result,indent=2)+'\n')
