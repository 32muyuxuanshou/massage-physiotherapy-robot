"""Cache frozen backbone only; never load TEST pixels or test targets."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse
import copy
import json
from pathlib import Path
import time
import numpy as np
import torch
from geometry import crop_registered_depth
from r3_common import TRUTH_KEYS,load_official,cached_forward,sha
from fusion import RGBDBodyAdapter


def prepare(root,data,out,real=False,limit=None,parameter_tolerance=2e-6):
    out.mkdir(parents=True,exist_ok=False)
    official,estimator=load_official(root)
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    source_manifest=data/('FRAME_MANIFEST_V1.json' if real else 'MANIFEST.json')
    manifest=json.loads(source_manifest.read_text())
    rows=[r for r in manifest['records' if real else 'samples'] if r['role'] in ['TRAIN','VAL']]
    if limit:rows=rows[:limit]
    captured=[]
    hook=official.backbone.register_forward_hook(lambda module,args,output:captured.append((output[-1] if isinstance(output,tuple) else output).detach().cpu()))
    results=[];start=time.monotonic();qa=None
    for i,row in enumerate(rows):
        name=(row['sequence']+f"_{row['frame']:06d}" if real else Path(row['file']).stem)
        file=(row['views']['kinect_000']['file'] if real else row['file'])
        expected_sha=row['views']['kinect_000']['sha256'] if real else row['sha256']
        assert sha(data/file)==expected_sha,'SOURCE_NPZ_HASH_MISMATCH'
        with np.load(data/file) as z:
            rgb=z['rgb'];K=z['K'];bbox=z['bbox'];mask=z['mask_rgb'] if real else z['mask']
            depth=z['depth_rgb_z_m'] if real else z['depth_m']
            truth={k:torch.from_numpy(z[k]) for k in TRUTH_KEYS} if not real else {}
            target=z['depth_clean_m'] if not real else None
        b=prepare_batch(rgb,estimator.transform,bbox[None],masks=mask.astype(np.uint8)[None],cam_int=torch.from_numpy(K[None]).float())
        # img_ori contains an unused non-tensor wrapper; no forward_pose_branch use.
        b={k:v for k,v in b.items() if torch.is_tensor(v)}
        d,valid,rays=crop_registered_depth(torch.from_numpy(depth[None,None]),b)
        bg=recursive_to(copy.deepcopy(b),'cuda');official._initialize_batch(bg);captured.clear()
        with torch.no_grad():baseline=official.forward_step(bg,decoder_type='body')['mhr']
        feature=captured[-1];assert feature.shape==(1,1280,32,24)
        rec=dict(batch=b,backbone=feature,depth=d,valid=valid,rays=rays,truth=truth,
            identity=row['identity'],role=row['role'],sample=name,file=file,
            official={k:v.cpu() for k,v in baseline.items() if torch.is_tensor(v)})
        if not real:
            rec.update(target_depth=torch.from_numpy(target[None]),target_mask=torch.from_numpy(mask[None]).float(),K=torch.from_numpy(K[None]))
        else:
            rec.update(sequence=row['sequence'],frame=row['frame'],heldout_file=row['views']['kinect_001']['file'])
        if i==0:
            hook.remove()
            adapter=RGBDBodyAdapter(official,mode='residual').cuda()
            with torch.no_grad():again=cached_forward(adapter,recursive_to(copy.deepcopy(b),'cuda'),feature.cuda(),d.cuda(),valid.cuda(),rays.cuda())
            diffs={k:float((again[k]-baseline[k]).abs().max()) for k in ['pred_vertices','pred_cam_t','global_rot','body_pose','shape','scale']}
            print('CACHE_EQUIVALENCE',json.dumps(diffs),flush=True)
            assert diffs['pred_vertices']<=1e-6 and diffs['pred_cam_t']<=2e-6 and all(v<=parameter_tolerance for v in diffs.values()),'CACHE_FORWARD_NOT_EQUIVALENT'
            qa=dict(status='PASS',dtype=str(feature.dtype),cache_forward_max_abs=diffs,
                    numerical_tolerance=parameter_tolerance,geometry_tolerance_mm=.001,camera_tolerance_mm=.002,
                    note='Native dtype preserved; CUDA/layout floating point roundoff, not bitwise output equality')
            adapter._hook.remove();del adapter
            hook=official.backbone.register_forward_hook(lambda module,args,output:captured.append((output[-1] if isinstance(output,tuple) else output).detach().cpu()))
        torch.save(rec,out/(name+'.pt'))
        results.append(dict(**row,cache_file=name+'.pt'))
        if i%40==0:print('CACHED',i+1,'/',len(rows),'seconds',round(time.monotonic()-start,1),flush=True)
    hook.remove()
    report=dict(status='CACHE_COMPLETE_NO_TEST_LOADED',real=real,records=results,source_manifest_sha256=sha(source_manifest),
        cache_qa=qa,seconds=time.monotonic()-start,storage_bytes=sum(f.stat().st_size for f in out.glob('*.pt')))
    (out/'CACHE_MANIFEST.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--real',action='store_true');p.add_argument('--limit',type=int)
    a=p.parse_args();prepare(a.root,a.data,a.out,a.real,a.limit)
