"""Read-only local gradient probes for the four V1 loss components."""
import argparse,json,sys
from pathlib import Path
import numpy as np, torch

ap=argparse.ArgumentParser(); ap.add_argument('--sam-repo',type=Path,required=True); ap.add_argument('--historical-code',type=Path,required=True)
ap.add_argument('--official',type=Path,required=True); ap.add_argument('--mhr',type=Path,required=True); ap.add_argument('--e1',type=Path,required=True); ap.add_argument('--e10',type=Path,required=True); ap.add_argument('--dev-dir',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
sys.path[:0]=[str(a.sam_repo),str(a.historical_code)]
from sam_3d_body import SAM3DBodyEstimator,load_sam_3d_body
from sam_3d_body.data.utils.prepare_batch import prepare_batch
from sam_3d_body.utils import recursive_to
from train_rgbd_surface import forward_observation,robust_surface_loss,stability_loss,head_initialization_loss
model,cfg=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr)); model.eval().requires_grad_(False)
heads={'pose':model.head_pose.proj,'camera':model.head_camera.proj}; [h.requires_grad_(True) for h in heads.values()]
params=[p for h in heads.values() for p in h.parameters()]; initial={f'{hn}.{n}':p.detach().clone() for hn,h in heads.items() for n,p in h.named_parameters()}
est=SAM3DBodyEstimator(model,cfg); faces=model.head_pose.faces.detach().long(); paths=sorted(a.dev_dir.glob('*.npz'))[:3]
with torch.inference_mode():
 teacher={}
 for p in paths:
  o,_=forward_observation(model,est,prepare_batch,recursive_to,p); teacher[p.name]={'keypoints_2d':o['pred_keypoints_2d'].detach().clone(),'keypoints_3d':o['pred_keypoints_3d'].detach().clone()}
def load(tag):
 if tag=='official':
  # Recreate exact Official projection heads because later probes mutate them.
  fresh,_=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr))
  model.head_pose.proj.load_state_dict(fresh.head_pose.proj.state_dict()); model.head_camera.proj.load_state_dict(fresh.head_camera.proj.state_dict()); del fresh
 else:
  c=torch.load(a.e1 if tag=='e1' else a.e10,map_location='cpu',weights_only=False)
  model.head_pose.proj.load_state_dict(c['heads']['pose']); model.head_camera.proj.load_state_dict(c['heads']['camera'])
def grad(loss):
 for p in params: p.grad=None
 loss.backward(retain_graph=True)
 return torch.cat([(p.grad if p.grad is not None else torch.zeros_like(p)).reshape(-1) for p in params]).detach()
rows=[]
for tag in ('official','e1','e10'):
 load(tag)
 for path in paths:
  o,z=forward_observation(model,est,prepare_batch,recursive_to,path); t=teacher[path.name]
  verts=o['pred_vertices']+o['pred_cam_t'][:,None,:]
  losses={}; losses['surface']=robust_surface_loss(verts,faces,z['points_a'],{'observed_samples':2048,'triangle_samples':4096,'huber_delta_m':.03},20260910)
  losses['teacher2d'],losses['teacher3d']=stability_loss(o,t,model.pelvis_idx,z['rgb_a'].shape[:2]); losses['anchor']=head_initialization_loss(heads,initial)
  gs={k:grad(v) for k,v in losses.items()}; norms={k:float(torch.linalg.vector_norm(v)) for k,v in gs.items()}
  cos={}
  for k in ('teacher2d','teacher3d','anchor'):
   den=norms['surface']*norms[k]; cos['surface_vs_'+k]=None if den==0 else float(torch.dot(gs['surface'],gs[k])/den)
  rows.append({'checkpoint':tag,'sample':path.name,'loss_values':{k:float(v.detach()) for k,v in losses.items()},'gradient_norms':norms,'gradient_cosines':cos})
result={'status':'COMPLETED_LOCAL_GRADIENT_PROBE','samples':[p.name for p in paths],'rows':rows,
 'interpretation':'Negative cosine means local gradient conflict only. Zero teacher/anchor gradient at Official makes cosine undefined and does not justify deleting a loss.',
 'optimizer_constructed':False,'optimizer_steps':0}
a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,indent=2))
