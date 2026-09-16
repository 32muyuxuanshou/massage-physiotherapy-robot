import argparse,json,sys
from pathlib import Path
import cv2,numpy as np,torch

def depth_points(depth,mask,table):
 good=(depth>0)&(mask>127); rays=np.dstack([table,np.ones(table.shape[:2],table.dtype)])
 return rays[good].astype(np.float32)*depth[good,None].astype(np.float32)/1000

def main():
 p=argparse.ArgumentParser()
 for n in ('config','formal-manifest','pointcloud-manifest','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();c=json.loads(a.config.read_text());paths=c['paths'];sys.path[:0]=[paths['sam3d_repo']]
 from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
 from sam_3d_body.data.utils.prepare_batch import prepare_batch
 from sam_3d_body.utils import recursive_to
 spec=json.loads(a.formal_manifest.read_text())['rows'][0];pc=json.loads(a.pointcloud_manifest.read_text())['rows'][0]
 frame=Path(paths['sequences'])/spec['sequence']/spec['frame'];rgb=cv2.cvtColor(cv2.imread(str(frame/'k0.color.jpg')),cv2.COLOR_BGR2RGB);mask=cv2.imread(str(pc['mask']),0);depth=cv2.imread(str(pc['depth']),-1);table=np.load(pc['pointcloud_table']);points=depth_points(depth,mask,table)
 y,x=np.where(mask>127);bbox=np.array([[max(0,x.min()-25),max(0,y.min()-25),min(rgb.shape[1]-1,x.max()+25),min(rgb.shape[0]-1,y.max()+25)]],np.float32)
 model,cfg=load_sam_3d_body(paths['official_checkpoint'],device='cuda',mhr_path=paths['mhr_model']);model.eval();est=SAM3DBodyEstimator(model,cfg);batch=recursive_to(prepare_batch(rgb,est.transform,bbox,None,None),'cuda')
 import json as _j
 cal=_j.load(open(pc['calibration']));cc=cal['color'];K=np.array([[cc['fx'],0,cc['cx']],[0,cc['fy'],cc['cy']],[0,0,1]],np.float32)
 batch['cam_int']=torch.as_tensor(K[None],device='cuda').to(batch['img']);model._initialize_batch(batch)
 with torch.inference_mode(): pred=model.forward_step(batch,decoder_type='body')['mhr']
 head=model.head_pose;faces=head.faces.long();z=np.load(paths['surface_anchors']);fi=torch.as_tensor(z['face_index'],device='cuda').long();bc=torch.as_tensor(z['barycentric'],device='cuda',dtype=torch.float32)
 initial={k:pred[k].detach().clone() for k in ('global_rot','body_pose','shape','scale','hand','face','pred_cam_t','pred_vertices')}
 def forward(params):
  v=head.mhr_forward(global_trans=torch.zeros_like(params['global_rot']),global_rot=params['global_rot'],body_pose_params=params['body_pose'],hand_pose_params=params['hand'],scale_params=params['scale'],shape_params=params['shape'],expr_params=params['face'])[0]
  v=v.clone();v[...,1:3]*=-1
  return v+params['pred_cam_t'][:,None]
 base={k:v.clone() for k,v in initial.items() if k!='pred_vertices'};recon=forward(base);official=initial['pred_vertices']+initial['pred_cam_t'][:,None];recon_max=float((recon-official).abs().max())
 rng=np.random.default_rng(20260916);obs=torch.as_tensor(points[np.sort(rng.choice(len(points),min(2048,len(points)),False))],device='cuda')
 def loss_and_grads(group):
  params={k:v.clone().detach() for k,v in base.items()}
  learn=['pred_cam_t']+({'O2':['global_rot','body_pose'],'O3':['shape','scale'],'O4':['global_rot','body_pose','shape','scale']}[group])
  for k in learn:params[k].requires_grad_(True)
  v=forward(params);anc=(v[0][faces[fi]]*bc[:,:,None]).sum(1);sub=anc[::4];near=torch.cdist(obs,sub).argmin(1);res=obs-sub[near];sensor=torch.sqrt((res*res).sum(1)+1e-10).median();prior=sum((params[k]-base[k]).square().mean() for k in learn if k!='pred_cam_t');loss=sensor+0.01*prior;loss.backward()
  return {'sensor_loss_m':float(sensor),'gradient_norms':{k:float(params[k].grad.norm()) for k in learn},'all_nonzero':all(float(params[k].grad.norm())>0 for k in learn)}
 result={'status':'PASS_MHR_ORACLE_AUDIT','frame':spec,'parameter_shapes':{k:list(v.shape) for k,v in base.items()},'pose_definition':['global_rot','body_pose'],'shape_definition':['shape','scale'],'translation_definition':'pred_cam_t in K0 camera metres','reconstruction_max_abs_m':recon_max,'groups':{g:loss_and_grads(g) for g in ('O2','O3','O4')}}
 if recon_max>1e-5 or not all(x['all_nonzero'] for x in result['groups'].values()):result['status']='FAIL_MHR_ORACLE_AUDIT'
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
