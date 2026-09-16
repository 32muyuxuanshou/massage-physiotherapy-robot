import argparse,csv,json,sys
from collections import defaultdict
from pathlib import Path
import cv2,numpy as np
from scipy.spatial import cKDTree

METHODS=('O0','O1','O2','O3','O4')
def depth_points(depth,mask,table):
 good=(depth>0)&(mask>127);r=np.dstack([table,np.ones(table.shape[:2],table.dtype)])
 return r[good].astype(float)*depth[good,None].astype(float)/1000
def sample(x,key,n=5000):
 if len(x)<=n:return x
 import hashlib;r=np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:16],16));return x[np.sort(r.choice(len(x),n,False))]
def fit_translation(points,vertices,faces,iterations=6,trim=.2,step=.05):
 anchors=vertices[faces].mean(1);t=np.zeros(3)
 for _ in range(iterations):
  dist,near=cKDTree(anchors+t).query(points,workers=-1);keep=dist<=np.quantile(dist,1-trim);t+=np.clip(np.median(points[keep]-(anchors+t)[near[keep]],0),-step,step)
 return t
def summarize(x):
 x=np.asarray(x)*1000;return {'median_mm':float(np.median(x)),'mean_mm':float(x.mean()),'p90_mm':float(np.percentile(x,90)),'p95_mm':float(np.percentile(x,95)),'coverage_50mm':float(np.mean(x<50))}
def median(v):return float(np.median(list(v)))
def main():
 p=argparse.ArgumentParser()
 for n in ('config','formal-manifest','stage-a-manifest','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();cfg=json.loads(a.config.read_text());paths=cfg['paths'];sys.path[:0]=[str(Path(paths['v23_code'])),str(Path(paths['surface_metrics']).parent)]
 from behave_v2_io import read_camera,transform_between
 from surface_metrics import point_to_triangle_distances
 formal=json.loads(a.formal_manifest.read_text())['rows'];stage=json.loads(a.stage_a_manifest.read_text());by={x['frame_id']:x for x in stage['rows']};rows=[];a.out.mkdir(parents=True,exist_ok=True)
 for spec in formal:
  fid=f"{spec['subject']}/{spec['sequence']}/{spec['frame']}";src=by[fid];assets={g:np.load(src['methods'][g]['asset']) for g in ('O2','O3','O4')};faces=assets['O2']['faces'];meshes={'O0':assets['O2']['official_vertices'],'O1':assets['O2']['o1_vertices'],**{g:assets[g]['vertices'] for g in ('O2','O3','O4')}};frame=Path(paths['sequences'])/spec['sequence']/spec['frame'];cams=[read_camera(Path(paths['calibs']),spec['sequence'],k) for k in range(4)]
  for k in range(4):
   dep=cv2.imread(str(frame/f'k{k}.depth.png'),-1);mask=cv2.imread(str(frame/f'k{k}.person_mask.jpg'),0);points=sample(depth_points(dep,mask,cams[k]['pointcloud_table']),fid+f'/K{k}')
   for method,v0 in meshes.items():
    v=v0 if k==0 else transform_between(v0,cams[0],cams[k]);absolute=summarize(point_to_triangle_distances(points,v,faces));ta=fit_translation(points,v,faces);aligned=summarize(point_to_triangle_distances(points,v+ta,faces));rows.append({'subject':spec['subject'],'sequence':spec['sequence'],'frame':spec['frame'],'frame_id':fid,'camera':f'K{k}','role':'K0_DIAGNOSTIC' if k==0 else 'HELD_OUT','method':method,**{f'absolute_{q}':z for q,z in absolute.items()},**{f'aligned_{q}':z for q,z in aligned.items()},'aligned_translation_mm':float(np.linalg.norm(ta)*1000)})
  print(fid,flush=True)
 fields=list(rows[0]);csv.writer
 with (a.out/'per_frame_camera_metrics.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 held=[x for x in rows if x['role']=='HELD_OUT'];index={(x['frame_id'],x['camera'],x['method']):x for x in rows};frame_summary=[]
 for fid in sorted({x['frame_id'] for x in held}):
  subject,sequence,_=fid.split('/',2)
  for m in METHODS:
   z=[index[(fid,f'K{k}',m)] for k in (1,2,3)];frame_summary.append({'subject':subject,'sequence':sequence,'frame_id':fid,'method':m,**{q:median(x[q] for x in z) for q in ('absolute_median_mm','absolute_mean_mm','absolute_p90_mm','absolute_p95_mm','absolute_coverage_50mm','aligned_median_mm')}})
 def write(name,data): 
  with (a.out/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 write('per_frame_summary.csv',frame_summary)
 def aggregate(level):
  out=[];keys=sorted({tuple(x[k] for k in level) for x in frame_summary})
  for key in keys:
   subset=[x for x in frame_summary if tuple(x[k] for k in level)==key]
   for m in METHODS:
    z=[x for x in subset if x['method']==m];out.append({**dict(zip(level,key)),'method':m,'frames':len(z),**{q:median(x[q] for x in z) for q in ('absolute_median_mm','absolute_p90_mm','absolute_p95_mm','absolute_coverage_50mm','aligned_median_mm')}})
  return out
 seq=aggregate(('subject','sequence'));sub=aggregate(('subject',));write('per_sequence_summary.csv',seq);write('per_subject_summary.csv',sub)
 overall=[]
 for m in METHODS:
  z=[x for x in sub if x['method']==m];overall.append({'method':m,'subjects':len(z),**{q:median(x[q] for x in z) for q in ('absolute_median_mm','absolute_p90_mm','absolute_p95_mm','absolute_coverage_50mm','aligned_median_mm')}})
 write('overall_summary.csv',overall);ov={x['method']:x for x in overall};comparisons={}
 for m in ('O2','O3','O4'):
  subject_wins=sum(next(x for x in sub if x['subject']==s and x['method']==m)['absolute_median_mm']<next(x for x in sub if x['subject']==s and x['method']=='O1')['absolute_median_mm'] for s in sorted({x['subject'] for x in sub}))
  raw=(ov['O1']['absolute_median_mm']-ov[m]['absolute_median_mm'])/ov['O1']['absolute_median_mm']*100;aligned=(ov['O1']['aligned_median_mm']-ov[m]['aligned_median_mm'])/ov['O1']['aligned_median_mm']*100;comparisons[m]={'vs_O1_absolute_relative_improvement_pct':raw,'vs_O1_absolute_delta_mm':ov[m]['absolute_median_mm']-ov['O1']['absolute_median_mm'],'vs_O1_aligned_relative_improvement_pct':aligned,'subjects_improved':subject_wins}
 go=[m for m,x in comparisons.items() if x['vs_O1_absolute_relative_improvement_pct']>=5 and x['vs_O1_aligned_relative_improvement_pct']>=3 and x['subjects_improved']>=4];amb=[m for m,x in comparisons.items() if x['vs_O1_absolute_relative_improvement_pct']>=1]
 decision='STRONG_GO' if go else 'AMBIGUOUS' if amb else 'NO_GO'
 deltas=[]
 for x in frame_summary:
  if x['method']=='O1':continue
  b=next(y for y in frame_summary if y['frame_id']==x['frame_id'] and y['method']=='O1');k0=next(y for y in rows if y['frame_id']==x['frame_id'] and y['camera']=='K0' and y['method']==x['method']);k0b=next(y for y in rows if y['frame_id']==x['frame_id'] and y['camera']=='K0' and y['method']=='O1');deltas.append({**x,'heldout_delta_mm':x['absolute_median_mm']-b['absolute_median_mm'],'aligned_delta_mm':x['aligned_median_mm']-b['aligned_median_mm'],'k0_delta_mm':k0['absolute_median_mm']-k0b['absolute_median_mm']})
 (a.out/'top_improvements.json').write_text(json.dumps(sorted(deltas,key=lambda x:x['heldout_delta_mm'])[:10],indent=2)+'\n');(a.out/'top_degradations.json').write_text(json.dumps(sorted(deltas,key=lambda x:x['heldout_delta_mm'],reverse=True)[:10],indent=2)+'\n');(a.out/'k0_overfit_cases.json').write_text(json.dumps(sorted([x for x in deltas if x['k0_delta_mm']<0 and x['heldout_delta_mm']>0],key=lambda x:x['heldout_delta_mm'],reverse=True)[:10],indent=2)+'\n')
 final={'status':'PASS_STAGE_B_HELDOUT_EVALUATION','decision':decision,'strong_go_methods':go,'overall':overall,'comparisons':comparisons,'scope':'dataset-mask-assisted BEHAVE; K1/K2/K3 read only after Stage A manifest existed','regional_metrics':'NOT_YET_AVAILABLE'};(a.out/'FINAL_CHARACTERIZATION.json').write_text(json.dumps(final,indent=2)+'\n');print(json.dumps(final,indent=2))
if __name__=='__main__':main()
