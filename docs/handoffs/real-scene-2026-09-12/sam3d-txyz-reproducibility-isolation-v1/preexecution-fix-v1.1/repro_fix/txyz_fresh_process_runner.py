import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from .hashing import array_record
ITER=6;TRIM=.20;STEP=.05;TOTAL=.17788820176363325
def fit(points,anchors,workers=-1):
 points=np.asarray(points);anchors=np.asarray(anchors);t=np.zeros(3,dtype=np.float64);trace=[]
 for i in range(ITER):
  dist,near=cKDTree(anchors+t).query(points,workers=workers);threshold=np.quantile(dist,1-TRIM);keep=dist<=threshold;res=points[keep]-(anchors+t)[near[keep]];step=np.clip(np.median(res,axis=0),-STEP,STEP);t+=step;trace.append({'iteration':i+1,'nearest':array_record(near),'distances':array_record(dist),'keep':array_record(keep),'retained_residual':array_record(res),'step':array_record(step),'step_values':step.tolist(),'trim_threshold_raw':float(threshold),'retained_count':int(keep.sum()),'raw_correspondence_count':int(len(dist))})
 return {'translation':array_record(t),'translation_values':t.tolist(),'fallback':bool(np.linalg.norm(t)>TOTAL),'trace':trace,'numpy':np.__version__,'scipy':__import__('scipy').__version__,'workers':workers,'threads':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS')}}
def run_fresh(points_npz,anchors_npz,runs,workers,output):
 rows=[]
 for i in range(runs):
  target=Path(output).with_suffix(f'.run{i}.json');subprocess.run([sys.executable,'-m','repro_fix.txyz_fresh_process_runner','--worker','--points',str(points_npz),'--anchors',str(anchors_npz),'--workers',str(workers),'--output',str(target)],check=True);rows.append(json.loads(target.read_text()));target.unlink()
 payload={'process_isolation':'one new Python process per row','runs':rows,'workers':workers};Path(output).write_text(json.dumps(payload,indent=2)+'\n');return payload
def main():
 p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--points',type=Path,required=True);p.add_argument('--anchors',type=Path,required=True);p.add_argument('--workers',type=int,default=-1);p.add_argument('--runs',type=int,default=20);p.add_argument('--output',type=Path,required=True);a=p.parse_args();points=np.load(a.points)['points'];anchors=np.load(a.anchors)['anchors']
 if a.worker:a.output.write_text(json.dumps(fit(points,anchors,a.workers),indent=2)+'\n')
 else:run_fresh(a.points,a.anchors,a.runs,a.workers,a.output)
if __name__=='__main__':main()
