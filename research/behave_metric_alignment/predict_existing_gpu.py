"""Run one existing checkpoint without training, Txyz, or reference access."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0');os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np
import torch

def main():
    p=argparse.ArgumentParser()
    for n in ['root','r5-code']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--mode',choices=['rgb_only','g1','coarse','full'],required=True)
    p.add_argument('--seed',type=int,required=True);p.add_argument('--checkpoint',choices=['best','last'],required=True)
    a=p.parse_args()
    a.root=a.root.resolve()
    if not torch.cuda.is_available():raise RuntimeError('GPU_REQUIRED')
    torch.set_num_threads(2);torch.manual_seed(a.seed);torch.cuda.manual_seed_all(a.seed)
    sys.path[:0]=[str(a.r5_code),str(a.r5_code.parent)]
    from engine import Engine
    from data import batch
    from r3_common import sha
    from evaluate import BODY_KEYS
    manifest=json.loads((a.root/'cache'/f's{a.seed}'/'CACHE_MANIFEST.json').read_text())
    if manifest['status']!='COMPLETE_K0_ONLY':raise ValueError('Incomplete Official cache')
    freeze=json.loads((a.root/'reports'/'MODEL_ASSET_FREEZE.json').read_text())
    checkpoint=next(r for r in freeze['checkpoints'] if r['mode']==a.mode and r['seed']==a.seed and r['checkpoint']==a.checkpoint)
    if sha(checkpoint['path'])!=checkpoint['sha256']:raise ValueError('Frozen checkpoint changed')
    paths=json.loads((a.root/'PATHS.json').read_text());engine=Engine(a.mode,paths);engine.eval()
    state=torch.load(checkpoint['path'],map_location='cpu',weights_only=False)
    if state['identity']['mode']!=a.mode or state['identity']['seed']!=a.seed:raise ValueError('Wrong checkpoint cell')
    engine.load_checkpoint_state(state['model']);out=a.root/'predictions'/f'{a.mode}_s{a.seed}_{a.checkpoint}';out.mkdir(parents=True,exist_ok=True)
    results=[]
    with torch.no_grad():
        for i,row in enumerate(manifest['records']):
            if sha(row['cache_file'])!=row['cache_sha256']:raise ValueError('Official cache changed')
            x=batch([{'path':row['cache_file']}]);torch.cuda.synchronize();tick=time.perf_counter()
            o,trace=engine(x);torch.cuda.synchronize();seconds=time.perf_counter()-tick
            equality=all(torch.equal(o[k],x['official'][k]) for k in BODY_KEYS)
            if a.mode in ['coarse','full'] and not equality:raise ValueError('BODY_ISOLATION_BROKEN')
            values={k:o[k].cpu().numpy() for k in BODY_KEYS+['pred_cam_t']}
            values['vertices_camera_A']=(o['pred_vertices'][0]+o['pred_cam_t'][0]).float().cpu().numpy()
            for k,v in trace.items():
                if torch.is_tensor(v):values['trace_'+k]=v.cpu().numpy()
            target=out/(row['sequence']+'_'+row['frame']+'.npz');np.savez_compressed(target,**values)
            results.append(dict(row,prediction_file=str(target),prediction_sha256=sha(target),body_exact_equal_to_official=equality,
                                cached_head_seconds=seconds))
            if (i+1)%20==0:print('RAW_PREDICTIONS',a.mode,a.seed,a.checkpoint,i+1,len(manifest['records']),flush=True)
    engine.close()
    (out/'PREDICTION_MANIFEST.json').write_text(json.dumps({'status':'RAW_EXISTING_MODEL_COMPLETE','mode':a.mode,'seed':a.seed,
        'checkpoint':a.checkpoint,'checkpoint_sha256':checkpoint['sha256'],'records':results,'new_model_Txyz':False,
        'heldout_or_reference_read':False,'training':False,'timing_scope':'cached head only; not full RGB-D pipeline speed'},indent=2))

if __name__=='__main__':main()
