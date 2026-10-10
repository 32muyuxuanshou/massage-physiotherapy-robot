"""Package unchanged clean scan Z/mask for the original GPU raster loss."""
import argparse
import json
from pathlib import Path
import numpy as np
from train_camera import sha


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    rows=json.loads((a.data/'MANIFEST.json').read_text())['samples']
    assert len(rows)==3072 and all(r['role'] in ['TRAIN','VAL'] for r in rows)
    a.out.mkdir(exist_ok=False,parents=True)
    report=[]
    for r in rows:
        source=a.data/r['file']
        assert sha(source)==r['sha256']
        with np.load(source) as z:
            target=a.out/(r['sample_id']+'.npz')
            np.savez_compressed(target,depth_clean_m=z['depth_clean_m'],mask=z['mask'])
        report.append(dict(sample_id=r['sample_id'],role=r['role'],source_sha256=r['sha256'],
                           labels_sha256=sha(target),operation='lossless key packaging, no resize or depth unit change'))
    (a.out/'MANIFEST.json').write_text(json.dumps(dict(records=report,TEST_read=False),indent=2))
