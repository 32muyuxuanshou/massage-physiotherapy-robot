import hashlib,json
from pathlib import Path
import numpy as np

BASE=Path('/raid5/xuhd/rgbd_sam3d')
W=BASE/'r52_solver_factor_diagnostic_v1'
OLD=BASE/'r5_fine_negative_update_audit_v1'
G=OLD/'previous/geometry'
CFG=json.loads((W/'EXPERIMENT.json').read_text())


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    return h.hexdigest()


def load(p):
    with np.load(p) as z:return {k:z[k] for k in z.files}


def tasks():return json.loads((G/'MANIFEST.json').read_text())['tasks']


def key(t):return '%s_s%d_%s'%(t['dataset'],t['seed'],t['key'])


def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2))
