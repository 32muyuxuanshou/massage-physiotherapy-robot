"""Frozen 18-frame attribution benchmark using the corrected V3 input contract."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
import cv2,numpy as np,torch
from scipy.spatial import cKDTree
from run_formal_evaluation import read_camera,crop_boxes as roi_boxes,historical_bbox,mask_rgb,depth_points,transform,deterministic_sample,stats

ITERS=25; OBS=1024; STRIDE=2; BETA=.02; LR_T=.003; LR_P=.001; L_T=.01; L_P=.01
GROUPS={'T_only':('translation',),'T_globalrot':('translation','global_rot'),'T_bodypose':('translation','body_pose'),'T+Pose':('translation','global_rot','body_pose')}

def main():
 p=argparse.ArgumentParser()
 for n in ('manifest','sequences','calibs','sam-repo','checkpoint','mhr','anchors','surface-metrics','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);sys.path[:0]=[str(a.sam_repo),str(a.surface_metrics.parent)]
 from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
 from sam_3d_body.data.utils.prepare_batch import prepare_batch
 from sam_3d_body.utils import recursive_to
 from surface_metrics import point_to_triangle_distances
 manifest=json.loads(a.manifest.read_text()); specs=manifest.get('rows',manifest.get('behave',[]));model,cfg=load_sam_3d_body(str(a.checkpoint),device='cuda',mhr_path=str(a.mhr));model.eval();est=SAM3DBodyEstimator(model,cfg);head=model.head_pose;faces=head.faces.cpu().numpy().astype(np.int64);az=np.load(a.anchors);fi=az['face_index'];bc=az['barycentric'].astype(float);rows=[]
 for si,spec in enumerate(specs):
  sid=f"{spec['subject']}/{spec['sequence']}/{spec['frame']}";frame=a.sequences/spec['sequence']/spec['frame'];cams=[read_camera(a.calibs,spec['sequence'],k) for k in range(4)];rgb=cv2.cvtColor(cv2.imread(str(frame/'k0.color.jpg')),cv2.COLOR_BGR2RGB);mask=cv2.imread(str(frame/'k0.person_mask.jpg'),0);dep=cv2.imread(str(frame/'k0.depth.png'),-1);table=np.load(a.calibs/'intrinsics'/'0'/'pointcloud_table.npy');
  refv=np.asarray(__import__('trimesh').load(frame/'person'/'fit02'/'person_fit.ply',process=False).vertices,float); ref_local=[(refv-c['t'])@c['R'] for c in cams]; obs_all=[]
  for cond,box in roi_boxes(mask).items():
   x0,y0,x1,y1=box;im=rgb if cond=='FULL' else mask_rgb(rgb,mask,box);pts=depth_points(dep,mask,table,box);rng=np.random.default_rng(int(hashlib.sha256((sid+'observed').encode()).hexdigest()[:16],16));pts=pts[np.sort(rng.choice(len(pts),min(OBS,len(pts)),replace=False))];bbox=np.array([historical_bbox(mask)],np.float32);batch=recursive_to(prepare_batch(im,est.transform,bbox,None,None),'cuda');batch['cam_int']=torch.as_tensor(cams[0]['K'][None],device='cuda').to(batch['img']);model._initialize_batch(batch)
   with torch.inference_mode():pred=model.forward_step(batch,decoder_type='body')['mhr']
   base={k:pred[k].detach().clone() for k in ('global_rot','body_pose','shape','scale','hand','face','pred_cam_t')};vo=(pred['pred_vertices']+pred['pred_cam_t'][:,None])[0].cpu().numpy();anc=(vo[faces[fi]]*bc[:,:,None]).sum(1);t=np.zeros(3)
   for _ in range(6):
    dist,near=cKDTree(anc+t).query(pts,workers=-1);keep=dist<=np.quantile(dist,.8);t+=np.clip(np.median(pts[keep]-(anc+t)[near[keep]],axis=0),-.05,.05)
   applied=t if np.linalg.norm(t)<=.17788820176363325 else np.zeros(3);base['pred_cam_t']=base['pred_cam_t']+torch.as_tensor(applied,device='cuda')[None];obs=torch.as_tensor(pts,device='cuda');anchor_pick=torch.arange(0,len(fi),STRIDE,device='cuda');faces_t=torch.as_tensor(faces[fi],device='cuda').long();bc_t=torch.as_tensor(bc,device='cuda',dtype=pred['pred_vertices'].dtype)
   def forward(d):
    v=head.mhr_forward(global_trans=torch.zeros_like(d['global_rot']),global_rot=d['global_rot'],body_pose_params=d['body_pose'],hand_pose_params=d['hand'],scale_params=d['scale'],shape_params=d['shape'],expr_params=d['face'])[0];v=v.clone();v[...,1:3]*=-1;return v+d['pred_cam_t'][:,None]
   methods={'Official':vo,'Txyz':vo+applied}; param_records={}
   for name,learn in GROUPS.items():
    d={k:v.clone() for k,v in base.items()};d['pred_cam_t'].requires_grad_('translation' in learn);d['global_rot'].requires_grad_('global_rot' in learn);d['body_pose'].requires_grad_('body_pose' in learn);params=[]
    if 'translation' in learn:params.append({'params':[d['pred_cam_t']],'lr':LR_T})
    if 'global_rot' in learn or 'body_pose' in learn:params.append({'params':[x for x in (d['global_rot'],d['body_pose']) if x.requires_grad],'lr':LR_P})
    opt=torch.optim.Adam(params);hist=[]
    for _ in range(ITERS):
     opt.zero_grad();vv=forward(d);aa=(vv[0][faces_t]*bc_t[:,:,None]).sum(1)[anchor_pick];_,near_np=cKDTree(aa.detach().float().cpu().numpy()).query(obs.detach().float().cpu().numpy(),workers=-1);near=torch.as_tensor(near_np,device='cuda');res=torch.linalg.norm(obs.float()-aa[near].float(),dim=1);keep=res<=torch.quantile(res,.8);loss=torch.nn.functional.smooth_l1_loss(res[keep],torch.zeros_like(res[keep]),beta=BETA)+L_T*(d['pred_cam_t']-base['pred_cam_t']).square().mean()+L_P*((d['global_rot']-base['global_rot']).square().mean()+(d['body_pose']-base['body_pose']).square().mean());loss.backward();opt.step();hist.append(float(loss.detach()))
    methods[name]=forward(d).detach()[0].cpu().numpy();param_records[name]={'translation_delta_m':(d['pred_cam_t']-base['pred_cam_t'])[0].detach().cpu().numpy().tolist(),'global_rot':d['global_rot'][0].detach().cpu().numpy().tolist(),'body_pose':d['body_pose'][0].detach().cpu().numpy().tolist()}
   evals={}
   for name,v in methods.items():
    ce={}
    for k in (1,2,3):
     pk=depth_points(cv2.imread(str(frame/f'k{k}.depth.png'),-1),cv2.imread(str(frame/f'k{k}.person_mask.jpg'),0),np.load(a.calibs/'intrinsics'/str(k)/'pointcloud_table.npy'));pk=deterministic_sample(pk,5000,sid+'sensor'+str(k));vk=transform(v,cams[0],cams[k]);q=point_to_triangle_distances(pk,vk,faces)*1000;ce[f'K{k}']={'sensor':stats(q/1000)}
    evals[name]=ce
   rows.append({'spec':spec,'condition':cond,'txyz_m':t.tolist(),'txyz_fallback':bool(np.linalg.norm(t)>.17788820176363325),'methods':evals,'parameters':param_records});print(si+1,len(specs),sid,cond,flush=True)
 (a.out/'ATTRIBUTION_RESULTS.json').write_text(json.dumps({'status':'COMPLETE','methods':['Official','Txyz']+list(GROUPS),'rows':rows},indent=2)+'\n')
if __name__=='__main__':main()
