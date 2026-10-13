"""Explicit GPU stage: three repeat seeds, frozen K0 only, native Official caches."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0');os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import numpy as np
import torch

def main():
    p=argparse.ArgumentParser()
    for n in ['root','r5-code','inputs']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--seed',type=int,required=True);a=p.parse_args()
    a.root=a.root.resolve();a.inputs=a.inputs.resolve()
    if not torch.cuda.is_available():raise RuntimeError('GPU_REQUIRED; no CPU model inference fallback')
    torch.set_num_threads(2);torch.manual_seed(a.seed);torch.cuda.manual_seed_all(a.seed);random.seed(a.seed);np.random.seed(a.seed)
    sys.path[:0]=[str(a.r5_code),str(a.r5_code.parent)]
    from r3_common import load_official,sha
    from geometry import crop_registered_depth
    paths=json.loads((a.root/'PATHS.json').read_text())
    official,est=load_official(Path(paths['official_root']))
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    rows=json.loads((a.inputs/'INPUT_MANIFEST.json').read_text())['records']
    out=a.root/'cache'/f's{a.seed}';out.mkdir(parents=True,exist_ok=True)
    captured=[];hook=official.backbone.register_forward_hook(lambda m,args,v:captured.append((v[-1] if isinstance(v,tuple) else v).detach().cpu()))
    records=[]
    for i,row in enumerate(rows):
        key=row['sequence']+'_'+row['frame'];source=Path(row['input_file'])
        if sha(source)!=row['input_sha256']:raise ValueError('Actual K0 input hash mismatch')
        with np.load(source) as z:
            b=prepare_batch(z['rgb'],est.transform,z['bbox'][None],masks=z['mask'].astype(np.uint8)[None],
                            cam_int=torch.from_numpy(z['K'][None]).float())
            b={k:v for k,v in b.items() if torch.is_tensor(v)}
            d,valid,rays=crop_registered_depth(torch.from_numpy(z['depth_m'][None,None]),b)
        bg=recursive_to(copy.deepcopy(b),'cuda');official._initialize_batch(bg);captured.clear()
        torch.cuda.synchronize();tick=time.perf_counter()
        with torch.no_grad():o=official.forward_step(bg,decoder_type='body')['mhr']
        torch.cuda.synchronize();elapsed=time.perf_counter()-tick
        cpu={k:v.detach().cpu() for k,v in o.items() if torch.is_tensor(v)}
        if cpu['pred_vertices'].shape[-2:]!=(18439,3):raise ValueError('Native MHR layout mismatch')
        target=out/(key+'.pt')
        torch.save(dict(batch=b,backbone=captured[-1],depth=d,valid=valid,rays=rays,official=cpu,truth={},
                        K=b['cam_int'],sample=key,identity=row['subject'],role='BEHAVE_OFFICIAL_TEST_SUBSAMPLE',
                        source_sha256=row['input_sha256']),target)
        npz=out/(key+'.npz');body=cpu['pred_vertices'][0].float().numpy();t=cpu['pred_cam_t'][0].float().numpy()
        np.savez_compressed(npz,**{k:v.numpy() for k,v in cpu.items()},vertices_camera_A=body+t)
        records.append(dict(row,cache_file=str(target),cache_sha256=sha(target),prediction_file=str(npz),
                            prediction_sha256=sha(npz),official_seconds=elapsed))
        (out/'CACHE_MANIFEST.json').write_text(json.dumps({'seed':a.seed,'status':'PREPARING_K0_ONLY','records':records},indent=2))
        if (i+1)%10==0:print('OFFICIAL_CACHE',a.seed,i+1,len(rows),flush=True)
    hook.remove()
    (out/'CACHE_MANIFEST.json').write_text(json.dumps({'seed':a.seed,'status':'COMPLETE_K0_ONLY','records':records,
         'BEHAVE_official_TEST_loaded':True,'HuMMan_sealed_TEST_loaded':False,'heldout_or_reference_model_input':False,
         'input_manifest_sha256':sha(a.inputs/'INPUT_MANIFEST.json')},indent=2))

if __name__=='__main__':main()
