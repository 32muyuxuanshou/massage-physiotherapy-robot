"""Export only preregistered development review RGB; no GPU or model inference."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--selection',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);receipts=[]
    for r in json.loads(a.selection.read_text())['records']:
        assert r['role'] in ['TRAIN','VAL']
        for camera,label in [('kinect_000','A'),('kinect_001','B')]:
            view=r['views'][camera];source=a.root/'datasets/registered_v1'/view['file']
            digest=hashlib.sha256(source.read_bytes()).hexdigest();assert digest==view['sha256']
            with np.load(source) as z:
                out=a.out/(r['key']+'_'+label+'.png');Image.fromarray(z['rgb']).save(out)
            receipts.append(dict(key=r['key'],camera=camera,source_sha256=digest,filename=out.name,
                                 rgb_sha256=hashlib.sha256(out.read_bytes()).hexdigest()))
        print('RGB_EXPORTED',r['key'],flush=True)
    (a.out/'SOURCE_RGB_RECEIPT.json').write_text(json.dumps(receipts,indent=2))
