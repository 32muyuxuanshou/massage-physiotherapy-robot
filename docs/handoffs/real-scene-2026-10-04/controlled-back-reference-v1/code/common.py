import json,hashlib
from pathlib import Path
ROOT=Path('/raid5/xuhd/datasets/back_controlled_reference_v1_20261004')
PREV=Path('/raid5/xuhd/datasets/back_geometry_correspondence_v2_20261003')
BASE=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2')
METHODS=['INITIAL','RIGID','D_VECTOR','D_NORMAL']
CASES=['RIGID_ONLY','NORMAL_BUMP','TANGENTIAL_SHIFT']
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def summary(x):
    import numpy as np
    x=np.asarray(x)*1000
    return dict(n=len(x),median_mm=float(np.median(x)) if len(x) else None,p95_mm=float(np.percentile(x,95)) if len(x) else None)
