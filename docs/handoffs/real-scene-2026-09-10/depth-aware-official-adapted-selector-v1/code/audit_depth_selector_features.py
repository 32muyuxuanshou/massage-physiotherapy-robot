"""Camera-A-only residual features with Camera-B labels on consumed data."""
import argparse,json,hashlib,sys,time
from pathlib import Path
import numpy as np, torch
from scipy.spatial import cKDTree
from surface_metrics import camera_to_world,world_to_camera,point_to_triangle,point_to_triangle_distances,render_depth
from pose_camera_output_freeze import PoseCameraOutputFreeze

def load(p): return json.loads(Path(p).read_text())
def fixed_idx(n,key,cap=25000):
 if n<=cap:return np.arange(n)
 rng=np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:16],16));return np.sort(rng.choice(n,cap,False))
def best_translation(obs,vertices,iterations=8):
 t=np.zeros(3)
 for _ in range(iterations):
  _,idx=cKDTree(vertices+t).query(obs,workers=-1);step=np.median(obs-(vertices[idx]+t),axis=0);t+=np.clip(step,-.10,.10)
  if np.linalg.norm(step)<1e-5:break
 return t
def depth_stats(obs,v,faces,K,h,w):
 d=render_depth(v,faces,K,h,w);u=np.rint(K[0,0]*obs[:,0]/obs[:,2]+K[0,2]).astype(int);y=np.rint(K[1,1]*obs[:,1]/obs[:,2]+K[1,2]).astype(int)
 inside=(obs[:,2]>0)&(u>=0)&(u<w)&(y>=0)&(y<h); pred=np.zeros(len(obs));pred[inside]=d[y[inside],u[inside]];covered=inside&(pred>0)
 e=np.abs(pred[covered]-obs[covered,2])*1000
 return pred,covered,{'median_mm':float(np.median(e)) if covered.any() else None,'p90_mm':float(np.quantile(e,.90)) if covered.any() else None,'p95_mm':float(np.quantile(e,.95)) if covered.any() else None,'coverage':float(covered.sum()/max(inside.sum(),1)),'valid':int(inside.sum()),'covered':int(covered.sum())}
def main():
 ap=argparse.ArgumentParser();
 for n in ('sam-repo','official','mhr','winner','rows','out'):ap.add_argument('--'+n,type=Path,required=True)
 a=ap.parse_args();sys.path[:0]=[str(a.sam_repo)];from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator;from sam_3d_body.data.utils.prepare_batch import prepare_batch;from sam_3d_body.utils import recursive_to
 rows=load(a.rows)['rows'];model,cfg=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr));model.eval();est=SAM3DBodyEstimator(model,cfg);ctl=PoseCameraOutputFreeze(model);faces=model.head_pose.faces.cpu().numpy().astype(np.int64)
 official={};refs={};timing={'official_s':[],'adapted_s':[],'metrics_s':[]}
 with torch.no_grad():
  for r in rows:
   with np.load(r['path']) as z:rgb=z['rgb_a'].copy();bb=z['bbox_a'].copy();K=z['K_a'].copy()
   torch.cuda.synchronize();t=time.perf_counter();b=recursive_to(prepare_batch(rgb,est.transform,bb[None].astype(np.float32),None,None),'cuda');b['cam_int']=torch.as_tensor(K[None],device='cuda').to(b['img']);model._initialize_batch(b);ctl.begin_reference_capture();o=model.forward_step(b,decoder_type='body')['mhr'];refs[r['id']]=[x.cpu() for x in ctl.end_reference_capture()];official[r['id']]=(o['pred_vertices']+o['pred_cam_t'][:,None])[0].cpu().numpy();torch.cuda.synchronize();timing['official_s'].append(time.perf_counter()-t)
 ck=torch.load(a.winner,map_location='cpu',weights_only=False);named=dict(model.named_parameters());
 with torch.no_grad():
  for n,v in ck['model_trainable'].items():named[n].copy_(v.to(named[n]))
 adapted={}
 with torch.no_grad():
  for r in rows:
   with np.load(r['path']) as z:rgb=z['rgb_a'].copy();bb=z['bbox_a'].copy();K=z['K_a'].copy()
   torch.cuda.synchronize();t=time.perf_counter();b=recursive_to(prepare_batch(rgb,est.transform,bb[None].astype(np.float32),None,None),'cuda');b['cam_int']=torch.as_tensor(K[None],device='cuda').to(b['img']);model._initialize_batch(b);ctl.use_frozen_output_reference([x.cuda() for x in refs[r['id']]]);o=model.forward_step(b,decoder_type='body')['mhr'];ctl.clear_frozen_output_reference();adapted[r['id']]=(o['pred_vertices']+o['pred_cam_t'][:,None])[0].cpu().numpy();torch.cuda.synchronize();timing['adapted_s'].append(time.perf_counter()-t)
 out=[]
 for r in rows:
  t=time.perf_counter()
  with np.load(r['path']) as z:
   ia=fixed_idx(len(z['points_a']),r['id']+':A');ib=np.asarray(r.get('b_indices',fixed_idx(len(z['points_b']),r['id']+':B')),int);pa=z['points_a'][ia].astype(float);pb=z['points_b'][ib].astype(float);vo=official[r['id']];va=adapted[r['id']];h,w=z['rgb_a'].shape[:2]
   ro=point_to_triangle(pa,vo,faces);ra=point_to_triangle(pa,va,faces);do,co,dso=depth_stats(pa,vo,faces,z['K_a'],h,w);da,ca,dsa=depth_stats(pa,va,faces,z['K_a'],h,w);common=co&ca
   common_o=float(np.median(np.abs(do[common]-pa[common,2]))*1000) if common.any() else None;common_a=float(np.median(np.abs(da[common]-pa[common,2]))*1000) if common.any() else None
   vob=world_to_camera(camera_to_world(vo,z['R_a'],z['T_a']),z['R_b'],z['T_b']);vab=world_to_camera(camera_to_world(va,z['R_a'],z['T_a']),z['R_b'],z['T_b']);bo=point_to_triangle(pb,vob,faces);ba=point_to_triangle(pb,vab,faces);to=best_translation(pb,vob);ta=best_translation(pb,vab);alo=float(np.median(point_to_triangle_distances(pb,vob+to,faces))*1000);ala=float(np.median(point_to_triangle_distances(pb,vab+ta,faces))*1000);_,_,dbso=depth_stats(pb,vob,faces,z['K_b'],z['rgb_b'].shape[0],z['rgb_b'].shape[1]);_,_,dbsa=depth_stats(pb,vab,faces,z['K_b'],z['rgb_b'].shape[0],z['rgb_b'].shape[1])
   out.append({'id':r['id'],'subject_id':r['subject_id'],'a_point_o':ro['median_mm'],'a_point_a':ra['median_mm'],'a_render_o':dso['median_mm'],'a_render_a':dsa['median_mm'],'a_common_o':common_o,'a_common_a':common_a,'coverage_o':dso['coverage'],'coverage_a':dsa['coverage'],'common_count':int(common.sum()),'b_error_o':bo['median_mm'],'b_error_a':ba['median_mm'],'b_p90_o':bo['p90_mm'],'b_p90_a':ba['p90_mm'],'b_p95_o':bo['p95_mm'],'b_p95_a':ba['p95_mm'],'b_aligned_o':alo,'b_aligned_a':ala,'b_coverage_o':dbso['coverage'],'b_coverage_a':dbsa['coverage'],'b_render_o':dbso['median_mm'],'b_render_a':dbsa['median_mm'],'b_winner':'A' if ba['median_mm']<bo['median_mm'] else 'O'});timing['metrics_s'].append(time.perf_counter()-t)
 summary={k:{'median_s':float(np.median(v)),'p90_s':float(np.quantile(v,.9))} for k,v in timing.items()}
 Path(a.out).write_text(json.dumps({'status':'SEALED_SELECTOR_FEATURE_EVALUATION','rows':out,'camera_a_features_only':True,'camera_b_labels_only':True,'timing':summary,'gpu_peak_memory_mb':float(torch.cuda.max_memory_allocated()/1024**2)},indent=2)+chr(10));print(len(out))
if __name__=='__main__':main()
