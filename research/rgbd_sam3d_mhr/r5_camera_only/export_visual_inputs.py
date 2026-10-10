"""Fixed VAL identities/cameras for complete cached geometry overlay panels."""
import argparse
import json
from pathlib import Path
import numpy as np
from train_camera import sha

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['source','compact','out']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    rows=json.loads((a.compact/'MANIFEST.json').read_text())['records']
    selected=[]
    for identity in sorted({r['identity'] for r in rows if r['role']=='VAL'}):
        asset=sorted({r['asset_id'] for r in rows if r['identity']==identity})[0]
        for cid in [8,24,40,56]:
            row=next(r for r in rows if r['asset_id']==asset and r['view']['camera_id']==cid)
            with np.load(a.source/row['file']) as z:
                observed=dict(image_rgb=z['rgb'],depth_clean_m=z['depth_clean_m'],mask=z['mask'])
            with np.load(a.compact/row['compact_file']) as z:
                cached={k:z[k] for k in z.files}
            np.savez_compressed(a.out/(row['sample_id']+'.npz'),**observed,**cached)
            selected.append(dict(sample_id=row['sample_id'],identity=identity,view=row['view'],
                                  source_sha256=row['sha256'],file_sha256=sha(a.out/(row['sample_id']+'.npz'))))
    (a.out/'MANIFEST.json').write_text(json.dumps(dict(selection='all three VAL identities, first asset, fixed cameras8/24/40/56; seed11 fixed',records=selected),indent=2))
