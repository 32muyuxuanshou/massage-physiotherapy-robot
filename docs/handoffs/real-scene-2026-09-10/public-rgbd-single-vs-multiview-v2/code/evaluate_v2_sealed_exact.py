"""One-shot same-ruler V2 SEALED evaluation after the VAL winner is frozen."""
import argparse, json, sys, hashlib
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree
from surface_metrics import camera_to_world,world_to_camera,point_to_triangle,point_to_triangle_distances,rendered_depth

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sh(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def best_t(obs,v,it=8):
 t=np.zeros(3)
 for _ in range(it):
  _,idx=cKDTree(v+t).query(obs,workers=-1); s=np.median(obs-(v[idx]+t),0); t+=np.clip(s,-.1,.1)
  if np.linalg.norm(s)<1e-5:break
 return t
def agg(rows,key):
 by={}
 for r in rows: by.setdefault(r['subject_id'],[]).append(r[key])
 s={k:float(np.median(v)) for k,v in by.items()}; vals=np.array(list(s.values()))
 return {'subject_count':len(s),'mean_of_subject_frame_medians':float(vals.mean()),'median':float(np.median(vals)),'p90':float(np.percentile(vals,90)),'p95':float(np.percentile(vals,95)),'max':float(vals.max()),'subjects':s}

def main():
 p=argparse.ArgumentParser();
 for n in ('sam-repo','official','mhr','v1-e1','winner','winner-freeze','eval-manifest','eval-indices','txyz','out'): p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args(); sys.path[:0]=[str(a.sam_repo)]
 from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
 from sam_3d_body.data.utils.prepare_batch import prepare_batch
 from sam_3d_body.utils import recursive_to
 from prepare_v2_sealed_after_winner import require_winner
 winner_freeze=require_winner(a.winner_freeze)
 if sh(a.winner)!=winner_freeze['checkpoint_sha256']: raise RuntimeError('winner hash mismatch')
 model,cfg=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr)); model.eval().requires_grad_(False); est=SAM3DBodyEstimator(model,cfg)
 faces=model.head_pose.faces.cpu().numpy().astype(np.int64); manifest=load(a.eval_manifest); rows=manifest['rows']; indices=np.load(a.eval_indices); bias=np.asarray(load(a.txyz)['constant_bias_camera_a_m'])
 if manifest['indices_npz_sha256']!=sh(a.eval_indices): raise RuntimeError('fixed indices hash mismatch')
 def infer():
  ans={}
  with torch.no_grad():
   for r in rows:
    with np.load(r['qa_cache_path']) as z:
     rgb=z['rgb_a'].copy();bbox=z['bbox_a'].copy();K=z['K_a'].copy()
    b=prepare_batch(rgb,est.transform,bbox[None].astype(np.float32),None,None);b=recursive_to(b,'cuda');b['cam_int']=torch.as_tensor(K[None],device='cuda').to(b['img']);model._initialize_batch(b)
    o=model.forward_step(b,decoder_type='body')['mhr'];ans[r['id']]={'v':(o['pred_vertices']+o['pred_cam_t'][:,None])[0].cpu().numpy(),'cam':o['pred_cam_t'][0].cpu().numpy()}
  return ans
 official_state={n:p.detach().cpu().clone() for n,p in model.named_parameters()}
 official=infer();ck=torch.load(a.v1_e1,map_location='cpu',weights_only=False);model.head_pose.proj.load_state_dict(ck['heads']['pose']);model.head_camera.proj.load_state_dict(ck['heads']['camera']);e1=infer()
 with torch.no_grad():
  for n,p in model.named_parameters(): p.copy_(official_state[n].to(p))
 wck=torch.load(a.winner,map_location='cpu',weights_only=False); named=dict(model.named_parameters())
 for n,value in wck['model_trainable'].items(): named[n].data.copy_(value.to(named[n]))
 winner=infer()
 per=[]
 for r in rows:
  with np.load(r['qa_cache_path']) as z:
   idx=indices[r['index_array_key']].astype(np.int64);obs=z['points_b'][idx].astype(np.float64)
   variants={'official':official[r['id']]['v'],'train_txyz':official[r['id']]['v']+bias,'historical_v1_e1':e1[r['id']]['v'],'v2_winner_model_s':winner[r['id']]['v']}
   row={'id':r['id'],'subject_id':r['subject_id'],'fixed_point_count':len(obs),'models':{}}
   for name,va in variants.items():
    vb=world_to_camera(camera_to_world(va,z['R_a'],z['T_a']),z['R_b'],z['T_b']);ab=point_to_triangle(obs,vb,faces);t=best_t(obs,vb)
    al=point_to_triangle_distances(obs,vb+t,faces)*1000;dep=rendered_depth(obs,vb,faces,z['K_b'],z['rgb_b'].shape[0],z['rgb_b'].shape[1])
    aligned_stats={'median_mm':float(np.median(al)),'p90_mm':float(np.percentile(al,90)),'p95_mm':float(np.percentile(al,95))}; aligned_stats=dict(row['models']['official']['translation_aligned']) if name=='train_txyz' else aligned_stats
    source=e1 if name=='historical_v1_e1' else winner if name=='v2_winner_model_s' else official
    row['models'][name]={'absolute':ab,'translation_aligned':aligned_stats,'coverage':dep.get('mesh_coverage_of_observed_points'),'pred_cam_t_a_m':source[r['id']]['cam'].tolist(),'oracle_translation_b_m':t.tolist()}
   per.append(row)
 summary={}
 for name in ('official','train_txyz','historical_v1_e1','v2_winner_model_s'):
  flat=[]
  for r in per:
   m=r['models'][name]; flat.append({'subject_id':r['subject_id'],'abs_med':m['absolute']['median_mm'],'abs_p90':m['absolute']['p90_mm'],'abs_p95':m['absolute']['p95_mm'],'aligned':m['translation_aligned']['median_mm'],'coverage':m['coverage']})
  summary[name]={k:agg(flat,k) for k in ('abs_med','abs_p90','abs_p95','aligned','coverage')}
 out={'status':'PASS_ONE_SHOT_EXACT_FIXED_V2_SEALED','scope':'V2 SEALED opened only after winner freeze; Final Reserve unopened','metric_contract':'identical fixed Camera-B points; exact point-to-triangle; XYZ-only aligned diagnostic; rendered-depth coverage','hashes':{'winner_freeze':sh(a.winner_freeze),'eval_manifest':sh(a.eval_manifest),'eval_indices':sh(a.eval_indices),'official':sh(a.official),'v1_e1':sh(a.v1_e1),'winner':sh(a.winner),'txyz':sh(a.txyz)},'summary':summary,'rows':per,'sealed_opened_after_winner_freeze':True,'final_reserve_opened':False}
 a.out.write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps({'status':out['status'],'summary':{k:{'absolute':v['abs_med']['mean_of_subject_frame_medians'],'aligned':v['aligned']['mean_of_subject_frame_medians'],'p90':v['abs_p90']['mean_of_subject_frame_medians'],'p95':v['abs_p95']['mean_of_subject_frame_medians'],'coverage':v['coverage']['mean_of_subject_frame_medians']} for k,v in summary.items()}},indent=2))
if __name__=='__main__':main()
