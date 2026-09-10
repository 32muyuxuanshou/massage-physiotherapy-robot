"""One-pass evaluation of frozen O/A/G-exact/G-gpu/B/C systems on a frozen split."""
import argparse, collections, hashlib, json, sys, time
from pathlib import Path
import numpy as np, torch
from scipy.spatial import cKDTree
from audit_cheap_depth_translation import robust_translation, surface_anchors
from evaluate_gpu_runtime_residual import gpu_depth_residual

def load(p):return json.loads(Path(p).read_text())
def idx(n,key,cap=5000):
 if n<=cap:return np.arange(n)
 return np.sort(np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:16],16)).choice(n,cap,False))
def agg(rows,system,key):
 g=collections.defaultdict(list)
 for r in rows:g[r['subject_id']].append(r['systems'][system][key])
 vals={s:float(np.median(v)) for s,v in g.items()};return {'mean_of_subject_frame_medians':float(np.mean(list(vals.values()))),'per_subject':vals}
def best_translation(obs,vertices,iterations=8):
 t=np.zeros(3)
 for _ in range(iterations):
  _,nearest=cKDTree(vertices+t).query(obs,workers=-1);step=np.median(obs-(vertices[nearest]+t),axis=0);t+=np.clip(step,-.10,.10)
  if np.linalg.norm(step)<1e-5:break
 return t
def main():
 p=argparse.ArgumentParser()
 for n in ('sam-repo','selector-code','official','mhr','winner','rows','anchors','constant-baseline','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();sys.path[:0]=[str(a.sam_repo),str(a.selector_code)]
 from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
 from sam_3d_body.data.utils.prepare_batch import prepare_batch
 from sam_3d_body.utils import recursive_to
 from pose_camera_output_freeze import PoseCameraOutputFreeze
 from surface_metrics import camera_to_world,world_to_camera,point_to_triangle,rendered_depth,point_to_triangle_distances
 rows=load(a.rows)['rows'];model,cfg=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr));model.eval();est=SAM3DBodyEstimator(model,cfg);ctl=PoseCameraOutputFreeze(model);faces=model.head_pose.faces.cpu().numpy().astype(np.int64);faces_gpu=torch.as_tensor(faces,device='cuda')
 refs={};O={};lat_o=[]
 with torch.inference_mode():
  for r in rows:
   with np.load(r['path']) as z:rgb=z['rgb_a'].copy();bb=z['bbox_a'].copy();K=z['K_a'].copy()
   torch.cuda.synchronize();t=time.perf_counter();b=recursive_to(prepare_batch(rgb,est.transform,bb[None].astype(np.float32),None,None),'cuda');b['cam_int']=torch.as_tensor(K[None],device='cuda').to(b['img']);model._initialize_batch(b);ctl.begin_reference_capture();o=model.forward_step(b,decoder_type='body')['mhr'];refs[r['id']]=[x.cpu() for x in ctl.end_reference_capture()];O[r['id']]=(o['pred_vertices']+o['pred_cam_t'][:,None])[0].detach();torch.cuda.synchronize();lat_o.append(time.perf_counter()-t)
 ck=torch.load(a.winner,map_location='cpu',weights_only=False);named=dict(model.named_parameters())
 with torch.no_grad():
  for n,v in ck['model_trainable'].items():named[n].copy_(v.to(named[n]))
 A={};lat_a=[]
 with torch.inference_mode():
  for r in rows:
   with np.load(r['path']) as z:rgb=z['rgb_a'].copy();bb=z['bbox_a'].copy();K=z['K_a'].copy()
   torch.cuda.synchronize();t=time.perf_counter();b=recursive_to(prepare_batch(rgb,est.transform,bb[None].astype(np.float32),None,None),'cuda');b['cam_int']=torch.as_tensor(K[None],device='cuda').to(b['img']);model._initialize_batch(b);ctl.use_frozen_output_reference([x.cuda() for x in refs[r['id']]]);o=model.forward_step(b,decoder_type='body')['mhr'];ctl.clear_frozen_output_reference();A[r['id']]=(o['pred_vertices']+o['pred_cam_t'][:,None])[0].detach();torch.cuda.synchronize();lat_a.append(time.perf_counter()-t)
 spec=np.load(a.anchors);anchor_spec=(spec['face_index'],spec['barycentric'].astype(float));bias=np.asarray(load(a.constant_baseline)['constant_bias_camera_a_m']);bound=.17788820176363325;out=[];lat_c=[];lat_gpu=[]
 for r in rows:
  with np.load(r['path']) as z:
   pa=z['points_a'][idx(len(z['points_a']),r['id']+':A')].astype(float);pb=z['points_b'][idx(len(z['points_b']),r['id']+':B')].astype(float);vo=O[r['id']].cpu().numpy();va=A[r['id']].cpu().numpy()
   ro=point_to_triangle(pa,vo,faces);ra=point_to_triangle(pa,va,faces);dao=rendered_depth(pa,vo,faces,z['K_a'],z['rgb_a'].shape[0],z['rgb_a'].shape[1]);daa=rendered_depth(pa,va,faces,z['K_a'],z['rgb_a'].shape[0],z['rgb_a'].shape[1]);exact='A' if ro['median_mm']-ra['median_mm']>15 and daa['mesh_coverage_of_observed_points']>=dao['mesh_coverage_of_observed_points']-.02 else 'O'
   torch.cuda.synchronize();t=time.perf_counter();fast=gpu_depth_residual(z['points_a'],torch.stack((O[r['id']],A[r['id']])),faces_gpu,z['K_a'],*z['rgb_a'].shape[:2]);torch.cuda.synchronize();lat_gpu.append(time.perf_counter()-t);gpu='A' if fast[0][0]-fast[1][0]>15 and fast[1][1]>=fast[0][1]-.02 else 'O'
   anchors=surface_anchors(vo,faces,*anchor_spec);t=time.perf_counter();raw=robust_translation(z['points_a'].astype(float),anchors,'txyz');corr=np.zeros(3) if np.linalg.norm(raw)>bound else raw;lat_c.append(time.perf_counter()-t)
   candidates={'O':vo,'A':va,'G_exact':va if exact=='A' else vo,'G_gpu':va if gpu=='A' else vo,'B':vo+bias,'C':vo+corr};systems={}
   for n,v in candidates.items():
    vb=world_to_camera(camera_to_world(v,z['R_a'],z['T_a']),z['R_b'],z['T_b']);m=point_to_triangle(pb,vb,faces);dep=rendered_depth(pb,vb,faces,z['K_b'],z['rgb_b'].shape[0],z['rgb_b'].shape[1]);shift=best_translation(pb,vb);aligned=float(np.median(point_to_triangle_distances(pb,vb+shift,faces))*1000);systems[n]={'median_mm':m['median_mm'],'mean_mm':m['mean_mm'],'p90_mm':m['p90_mm'],'p95_mm':m['p95_mm'],'max_mm':m['max_mm'],'aligned_mm':aligned,'coverage':dep['mesh_coverage_of_observed_points']}
   out.append({'id':r['id'],'subject_id':r['subject_id'],'action':r.get('action'),'exact_choice':exact,'gpu_choice':gpu,'camera_a':{'exact_o_mm':ro['median_mm'],'exact_a_mm':ra['median_mm'],'gpu_o_mm':fast[0][0],'gpu_a_mm':fast[1][0]},'correction_m':raw.tolist(),'correction_out_of_range':bool(np.linalg.norm(raw)>bound),'systems':systems})
 summary={n:{k:agg(out,n,k) for k in ('median_mm','mean_mm','p90_mm','p95_mm','max_mm','aligned_mm','coverage')} for n in candidates}
 result={'status':'FROZEN_SYSTEM_SPLIT_EVALUATED','frames':len(out),'subjects':len(set(r['subject_id'] for r in out)),'systems':summary,'choices':{'exact_adapted':sum(r['exact_choice']=='A' for r in out),'gpu_adapted':sum(r['gpu_choice']=='A' for r in out),'exact_gpu_agreement':float(np.mean([r['exact_choice']==r['gpu_choice'] for r in out]))},'runtime':{'official_p50_ms':float(np.median(lat_o)*1000),'adapted_second_p50_ms':float(np.median(lat_a)*1000),'cheap_correction_p50_ms':float(np.median(lat_c)*1000),'gpu_residual_p50_ms':float(np.median(lat_gpu)*1000),'peak_vram_mb':float(torch.cuda.max_memory_allocated()/1024**2)},'rows':out}
 a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'summary':{n:v['median_mm']['mean_of_subject_frame_medians'] for n,v in summary.items()},'choices':result['choices'],'runtime':result['runtime']},indent=2))
if __name__=='__main__':main()
