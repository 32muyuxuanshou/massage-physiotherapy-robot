"""Full scan spatial cache, unaltered source RGB/K; no native MHR pseudo GT."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,copy,json,sys,time
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from r3_common import load_official,sha
from geometry import crop_registered_depth


def main(a):
    torch.set_num_threads(2)
    official,estimator=load_official(a.official_root)
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    source=json.loads((a.data/'MANIFEST.json').read_text())
    rows=source['samples'];assert len(rows)==3072 and all(r['role'] in ['TRAIN','VAL'] for r in rows)
    a.out.mkdir(parents=True,exist_ok=True)
    captured=[]
    hook=official.backbone.register_forward_hook(lambda m,i,o:captured.append((o[-1] if isinstance(o,tuple) else o).detach().cpu()))
    receipts=[];started=time.monotonic()
    for i,r in enumerate(rows[a.shard::a.shards]):
        name=r['sample_id'];target=a.out/(name+'.pt')
        if not target.exists():
            path=a.data/r['file'];assert sha(path)==r['sha256']
            with np.load(path) as z:
                rgb,K,bbox,mask=z['rgb'],z['K'],z['bbox'],z['mask']
                depth=z['depth_m']*mask;clean=z['depth_clean_m']
            b=prepare_batch(rgb,estimator.transform,bbox[None],masks=mask.astype(np.uint8)[None],
                            cam_int=torch.from_numpy(K[None]).float())
            b={k:v for k,v in b.items() if torch.is_tensor(v)}
            d,valid,rays=crop_registered_depth(torch.from_numpy(depth[None,None]),b)
            bg=recursive_to(copy.deepcopy(b),'cuda');official._initialize_batch(bg);captured.clear()
            with torch.no_grad():o=official.forward_step(bg,decoder_type='body')['mhr']
            torch.save(dict(batch=b,backbone=captured[-1],depth=d,valid=valid,rays=rays,
                official={k:v.detach().cpu() for k,v in o.items() if torch.is_tensor(v)},truth={},
                target_depth=torch.from_numpy(clean[None]),target_mask=torch.from_numpy(mask[None]).float(),
                K=torch.from_numpy(K[None]),identity=r['identity'],role=r['role'],sample=name,
                domain='scan',source_sha256=r['sha256']),target)
        receipts.append(dict(r,cache_file=target.name,cache_sha256=sha(target)))
        if i%40==0:print('SPATIAL_SCAN',a.shard,i+1,round(time.monotonic()-started),flush=True)
    hook.remove()
    np.save(a.out/'faces.npy',official.head_pose.faces.detach().cpu().numpy())
    (a.out/f'SHARD_{a.shard:02d}.json').write_text(json.dumps(dict(status='COMPLETE',records=receipts,
        source_manifest_sha256=sha(a.data/'MANIFEST.json'),test_read=False,camera_B_read=False),indent=2))
    print('SPATIAL_SCAN_COMPLETE',a.shard,len(receipts),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['official-root','data','out']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--shard',type=int,default=0);p.add_argument('--shards',type=int,default=1)
    main(p.parse_args())
