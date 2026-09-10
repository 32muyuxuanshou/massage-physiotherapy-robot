"""Read-only synchronized HuMMan Camera-A/B point-cloud consistency diagnostic."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

def world(p,R,T): return (p-T)@R
def stat(x):
 x=np.asarray(x)*1000
 return {"count":int(len(x)),"median_mm":float(np.median(x)),"p90_mm":float(np.percentile(x,90)),"p95_mm":float(np.percentile(x,95))}
ap=argparse.ArgumentParser(); ap.add_argument('--manifest',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
rows=[]
for i,r in enumerate(json.loads(a.manifest.read_text())['samples']):
 if r['split'].upper()!='VAL': continue
 with np.load(r['observation_npz']) as z:
  rng=np.random.default_rng(20260910+i)
  pa=z['points_a']; pb=z['points_b']; pa=pa[rng.choice(len(pa),min(10000,len(pa)),False)]; pb=pb[rng.choice(len(pb),min(10000,len(pb)),False)]
  wa=world(pa,z['R_a'],z['T_a']); wb=world(pb,z['R_b'],z['T_b'])
  da=cKDTree(wb).query(wa,workers=-1)[0]; db=cKDTree(wa).query(wb,workers=-1)[0]
  # Symmetric nearest-neighbour consistency includes view-dependent clothing/occlusion,
  # so it is descriptive and never called a sensor error floor.
  d=np.r_[da,db]
  rows.append({'id':r['id'],'subject_id':r['subject_id'],'symmetric_nearest_neighbor':stat(d),'a_to_b':stat(da),'b_to_a':stat(db)})
by={}
for r in rows: by.setdefault(r['subject_id'],[]).append(r['symmetric_nearest_neighbor'])
subject=[]
for s,v in sorted(by.items()): subject.append({'subject_id':s,**{k:float(np.median([x[k] for x in v])) for k in ('median_mm','p90_mm','p95_mm')}})
result={'status':'SENSOR_GEOMETRY_CONSISTENCY_DESCRIPTIVE','name':'SENSOR_GEOMETRY_CONSISTENCY','not_true_sensor_error_floor':True,
 'method':'symmetric nearest-neighbour distance after calibrated camera-to-world transform; person-mask points; no visibility correspondence',
 'subject_macro':{k:float(np.mean([x[k] for x in subject])) for k in ('median_mm','p90_mm','p95_mm')},'subjects':subject,'rows':rows,
 'limitations':['Nearest-neighbour distance mixes calibration, depth noise, view-dependent visibility and clothing surface.','It must not be subtracted from model error.']}
a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,indent=2))
