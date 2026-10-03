"""Paths and small I/O helpers for the independent V2 experiment."""
import hashlib,json
from pathlib import Path
import numpy as np

ROOT=Path('/raid5/xuhd/datasets/back_geometry_correspondence_v2_20261003')
OLD=Path('/raid5/xuhd/datasets/prone_back_point_validation_20261003')
BASE=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2')
BEHAVE=Path('/raid5/xuhd/behave_rgbd_mesh_v1')
METHODS=['Official','Official+Rigid','Official+Rigid+D','Official+Rigid+D_normal']

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def token(m):return m.replace('+','_')
def surface_summary(d):
    d=np.asarray(d)*1000
    return dict(count=len(d),median_mm=float(np.median(d)) if len(d) else None,
        p95_mm=float(np.percentile(d,95)) if len(d) else None,
        coverage_50mm=float(np.mean(d<=50)) if len(d) else None)
