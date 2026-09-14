import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from .hashing import array_record
from .execution_guard import require_master_authorization
ITER=6;TRIM=.20;STEP=.05;TOTAL=.17788820176363325
def fit(points,anchors,workers=-1):
 points=np.asarray(points);anchors=np.asarray(anchors);t=np.zeros(3,dtype=np.float64);trace=[];raw_initial=None
 for i in range(ITER):
  dist,near=cKDTree(anchors+t).query(points,workers=workers)
  if raw_initial is None:raw_initial=dist.copy()
  threshold=np.quantile(dist,1-TRIM);keep=dist<=threshold;res=points[keep]-(anchors+t)[near[keep]];res_norm=np.linalg.norm(res,axis=1);res_med=float(np.median(res_norm));step=np.clip(np.median(res,axis=0),-STEP,STEP);t+=step;trace.append({'iteration':i+1,'nearest':array_record(near),'distances':array_record(dist),'keep':array_record(keep),'retained_residual':array_record(res),'step':array_record(step),'step_values':step.tolist(),'step_norm_m':float(np.linalg.norm(step)),'trim_threshold_raw':float(threshold),'retained_residual_median_m':res_med,'residual_mad_m':float(np.median(np.abs(res_norm-res_med))),'residual_p90_m':float(np.percentile(res_norm,90)),'residual_p95_m':float(np.percentile(res_norm,95)),'retained_count':int(keep.sum()),'raw_correspondence_count':int(len(dist))})
 steps=np.asarray([row['step_values'] for row in trace],float);norms=np.linalg.norm(steps,axis=1);dots=np.sum(steps[:-1]*steps[1:],axis=1);den=np.linalg.norm(steps[:-1],axis=1)*np.linalg.norm(steps[1:],axis=1)+1e-12;last=trace[-1]
 features={'convergence_ratio':float(norms[-1]/max(norms[0],1e-12)),'direction_consistency':float(np.mean(dots/den)),'oscillation':bool(np.any(dots<0)),'raw_residual_median_mm':float(np.median(raw_initial)*1000),'residual_mad_mm':last['residual_mad_m']*1000,'residual_p90_mm':last['residual_p90_m']*1000,'residual_p95_mm':last['residual_p95_m']*1000}
 return {'translation':array_record(t),'translation_values':t.tolist(),'fallback':bool(np.linalg.norm(t)>TOTAL),'trace':trace,'features':features,'numpy':np.__version__,'scipy':__import__('scipy').__version__,'workers':workers,'threads':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS')}}
def run_fresh(points_npz,anchors_npz,runs,workers,output):
 rows=[]
 for i in range(runs):
  target=Path(output).with_suffix(f'.run{i}.json');subprocess.run([sys.executable,'-m','repro_fix.txyz_fresh_process_runner','--worker','--points',str(points_npz),'--anchors',str(anchors_npz),'--workers',str(workers),'--output',str(target)],check=True);rows.append(json.loads(target.read_text()));target.unlink()
 payload={'process_isolation':'one new Python process per row','runs':rows,'workers':workers};Path(output).write_text(json.dumps(payload,indent=2)+'\n');return payload
def main():
 p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--authorized-formal',action='store_true');p.add_argument('--points',type=Path,required=True);p.add_argument('--anchors',type=Path,required=True);p.add_argument('--workers',type=int,default=-1);p.add_argument('--runs',type=int,default=20);p.add_argument('--output',type=Path,required=True);a=p.parse_args();points=np.load(a.points)['points'];anchors=np.load(a.anchors)['anchors']
 if a.worker:a.output.write_text(json.dumps(fit(points,anchors,a.workers),indent=2)+'\n')
 else:
  if a.runs>=20:
   if not a.authorized_formal:raise RuntimeError('FORMAL_RUN_REQUIRES_POST_REVIEW_GO')
   require_master_authorization()
  run_fresh(a.points,a.anchors,a.runs,a.workers,a.output)
if __name__=='__main__':main()
