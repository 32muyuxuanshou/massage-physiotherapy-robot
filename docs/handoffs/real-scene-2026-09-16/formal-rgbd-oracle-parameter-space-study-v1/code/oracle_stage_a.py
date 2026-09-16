import argparse,hashlib,json,sys,time
from pathlib import Path
import cv2,numpy as np,torch

GROUPS={'O2':('global_rot','body_pose'),'O3':('shape','scale'),'O4':('global_rot','body_pose','shape','scale')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def depth_points(depth,mask,table):
 good=(depth>0)&(mask>127);r=np.dstack([table,np.ones(table.shape[:2],table.dtype)])
 return r[good].astype(np.float32)*depth[good,None].astype(np.float32)/1000
def percentile(x,q):return float(np.percentile(np.asarray(x),q))
def stats(x):x=np.asarray(x);return {'mean':float(x.mean()),'median':float(np.median(x)),'p90':percentile(x,90),'max':float(x.max())}
def main():
 p=argparse.ArgumentParser()
 for n in ('config','manifest','pointcloud-manifest','o1-results','oracle-config','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--max-frames',type=int)
 a=p.parse_args();cfg=json.loads(a.config.read_text());oc=json.loads(a.oracle_config.read_text());paths=cfg['paths'];sys.path[:0]=[paths['sam3d_repo']]
 from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
 from sam_3d_body.data.utils.prepare_batch import prepare_batch
 from sam_3d_body.utils import recursive_to
 rows=json.loads(a.manifest.read_text())['rows'];rows=rows[:a.max_frames] if a.max_frames else rows;pc={x['frame_id']:x for x in json.loads(a.pointcloud_manifest.read_text())['rows']};o1={f"{x['spec']['subject']}/{x['spec']['sequence']}/{x['spec']['frame']}":x for x in json.loads(a.o1_results.read_text())}
 model,mcfg=load_sam_3d_body(paths['official_checkpoint'],device='cuda',mhr_path=paths['mhr_model']);model.eval();est=SAM3DBodyEstimator(model,mcfg);head=model.head_pose;faces=head.faces.long();az=np.load(paths['surface_anchors']);fi=torch.as_tensor(az['face_index'],device='cuda').long();bc=torch.as_tensor(az['barycentric'],device='cuda',dtype=torch.float32);anchor_pick=torch.arange(0,len(fi),oc['anchor_stride'],device='cuda')
 out_rows=[];a.out.mkdir(parents=True,exist_ok=True)
 for spec in rows:
  fid=f"{spec['subject']}/{spec['sequence']}/{spec['frame']}";q=pc[fid];frame=Path(paths['sequences'])/spec['sequence']/spec['frame'];rgb=cv2.cvtColor(cv2.imread(str(frame/'k0.color.jpg')),cv2.COLOR_BGR2RGB);mask=cv2.imread(q['mask'],0);dep=cv2.imread(q['depth'],-1);pts=depth_points(dep,mask,np.load(q['pointcloud_table']));rng=np.random.default_rng(int(hashlib.sha256(fid.encode()).hexdigest()[:16],16));pts=pts[np.sort(rng.choice(len(pts),min(oc['observed_points'],len(pts)),False))];obs=torch.as_tensor(pts,device='cuda')
  y,x=np.where(mask>127);bbox=np.array([[max(0,x.min()-25),max(0,y.min()-25),min(rgb.shape[1]-1,x.max()+25),min(rgb.shape[0]-1,y.max()+25)]],np.float32);batch=recursive_to(prepare_batch(rgb,est.transform,bbox,None,None),'cuda');cal=json.load(open(q['calibration']))['color'];K=np.array([[cal['fx'],0,cal['cx']],[0,cal['fy'],cal['cy']],[0,0,1]],np.float32);batch['cam_int']=torch.as_tensor(K[None],device='cuda').to(batch['img']);model._initialize_batch(batch)
  with torch.inference_mode():pred=model.forward_step(batch,decoder_type='body')['mhr']
  base={k:pred[k].detach().clone() for k in ('global_rot','body_pose','shape','scale','hand','face','pred_cam_t')};base['pred_cam_t']=base['pred_cam_t']+torch.as_tensor(o1[fid]['applied_Txyz_m'],device='cuda')[None]
  def forward(d):
   v=head.mhr_forward(global_trans=torch.zeros_like(d['global_rot']),global_rot=d['global_rot'],body_pose_params=d['body_pose'],hand_pose_params=d['hand'],scale_params=d['scale'],shape_params=d['shape'],expr_params=d['face'])[0];v=v.clone();v[...,1:3]*=-1;return v+d['pred_cam_t'][:,None]
  official=(pred['pred_vertices']+pred['pred_cam_t'][:,None]).detach();o1v=forward(base).detach();fdir=a.out/'stage_a'/spec['subject']/spec['sequence']/spec['frame'];fdir.mkdir(parents=True,exist_ok=True);frame_rec={'frame_id':fid,'methods':{}}
  for group,names in GROUPS.items():
   d={k:v.clone().detach() for k,v in base.items()};learn=('pred_cam_t',)+names
   for k in learn:d[k].requires_grad_(True)
   optim=torch.optim.Adam([{'params':[d['pred_cam_t']],'lr':oc['lr_translation']},{'params':[d[k] for k in names if k in ('global_rot','body_pose')],'lr':oc['lr_pose']},{'params':[d[k] for k in names if k in ('shape','scale')],'lr':oc['lr_shape']}]);history=[];t0=time.time()
   for it in range(oc['iterations']):
    optim.zero_grad();v=forward(d);anc=(v[0][faces[fi]]*bc[:,:,None]).sum(1)[anchor_pick]
    with torch.no_grad():near=torch.cdist(obs,anc).argmin(1);dist=torch.linalg.norm(obs-anc[near],dim=1);cut=torch.quantile(dist,1-oc['trim'])
    res=torch.linalg.norm(obs-anc[near],dim=1);sensor=torch.nn.functional.smooth_l1_loss(res[res<=cut],torch.zeros_like(res[res<=cut]),beta=oc['huber_beta_m']);pose_prior=sum((d[k]-base[k]).square().mean() for k in names if k in ('global_rot','body_pose'));shape_prior=sum((d[k]-base[k]).square().mean() for k in names if k in ('shape','scale'));trans_prior=(d['pred_cam_t']-base['pred_cam_t']).square().mean();loss=sensor+oc['lambda_pose']*pose_prior+oc['lambda_shape']*shape_prior+oc['lambda_translation']*trans_prior;loss.backward();optim.step();history.append({'iteration':it+1,'total':float(loss),'sensor':float(sensor),'pose_prior':float(pose_prior),'shape_prior':float(shape_prior)})
   refined=forward(d).detach();delta=(refined-o1v).norm(dim=-1)[0].cpu().numpy()*1000;path=fdir/f'{group}.npz';np.savez_compressed(path,vertices=refined[0].cpu().numpy(),official_vertices=official[0].cpu().numpy(),o1_vertices=o1v[0].cpu().numpy(),faces=faces.cpu().numpy(),global_rot=d['global_rot'].detach().cpu().numpy(),body_pose=d['body_pose'].detach().cpu().numpy(),shape=d['shape'].detach().cpu().numpy(),scale=d['scale'].detach().cpu().numpy(),hand=d['hand'].detach().cpu().numpy(),face=d['face'].detach().cpu().numpy(),cam_t=d['pred_cam_t'].detach().cpu().numpy())
   pose_terms=[(d[k]-base[k]).square().sum() for k in names if k in ('global_rot','body_pose')];shape_terms=[(d[k]-base[k]).square().sum() for k in names if k in ('shape','scale')]
   changes={'translation_delta_mm':((d['pred_cam_t']-base['pred_cam_t'])[0].detach().cpu().numpy()*1000).tolist(),'translation_norm_mm':float((d['pred_cam_t']-base['pred_cam_t']).norm()*1000),'pose_l2':float(torch.stack(pose_terms).sum().sqrt()) if pose_terms else 0.0,'shape_l2':float(torch.stack(shape_terms).sum().sqrt()) if shape_terms else 0.0,'vertex_displacement_mm':stats(delta)}
   meta={'method':group,'asset':str(path),'sha256':sha(path),'config_sha256':sha(a.oracle_config),'loss_history':history,'initial_sensor':history[0]['sensor'],'final_sensor':history[-1]['sensor'],'changes':changes,'runtime_s':time.time()-t0,'converged':history[-1]['sensor']<=history[0]['sensor'],'numerical_failure':not np.isfinite(history[-1]['sensor'])};mp=fdir/f'{group}.json';mp.write_text(json.dumps(meta,indent=2)+'\n');frame_rec['methods'][group]={**meta,'metadata':str(mp)}
  out_rows.append(frame_rec);print(fid,flush=True)
 manifest={'status':'PASS_STAGE_A_FROZEN','scope':'K0_ONLY_DATASET_MASK_ASSISTED','config':oc,'config_sha256':sha(a.oracle_config),'frames':len(out_rows),'methods':['O2','O3','O4'],'rows':out_rows};(a.out/'STAGE_A_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()
