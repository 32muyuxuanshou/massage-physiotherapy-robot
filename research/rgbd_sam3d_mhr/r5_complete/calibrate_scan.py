"""One TRAIN-only output-gradient calibration, shared by every architecture."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0');os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from data import rows,batch
from engine import Engine

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main(a):
    torch.set_num_threads(2);paths=json.loads(a.paths.read_text());rng=np.random.default_rng(20261011)
    native=[r for r in rows(paths['native_cache'],'native') if r['role']=='TRAIN']
    scan=[r for r in rows(paths['scan_cache'],'scan') if r['role']=='TRAIN']
    ni=rng.choice(len(native),32,replace=False);selected=[]
    groups={}
    for i,r in enumerate(scan):groups.setdefault(r['identity'],{}).setdefault(r['asset_id'],{}).setdefault(r['view']['group'],[]).append(i)
    for k in range(32):
        assets=groups[rng.choice(sorted(groups))];gg=assets[rng.choice(sorted(assets))]
        selected.append(int(rng.choice(gg[rng.choice(sorted(gg))])))
    engine=Engine('coarse',paths);values={'native':[],'rendered_depth':[],'silhouette':[]};hits=[]
    for source,index in [(native,ni),(scan,selected)]:
        for start in range(0,32,8):
            rr=[source[i] for i in index[start:start+8]];x=batch(rr)
            camera=x['official']['pred_cam_t'].float().detach().clone().requires_grad_(True)
            if source is native:
                objective=2*F.smooth_l1_loss(camera,x['truth']['pred_cam_t'].float(),beta=.05,reduction='none').mean(1)
                values['native'].extend(torch.autograd.grad(objective.sum(),camera)[0].norm(dim=1).tolist())
            else:
                depth,sil=engine.renderer(x['official']['pred_vertices'].float()+camera[:,None],x['K'])
                mask=x['target_mask'].bool();target=x['target_depth'].float()
                dz=(F.smooth_l1_loss(depth,target,beta=.02,reduction='none')*mask).sum((1,2))/mask.sum((1,2))
                inter=(sil*mask).sum((1,2));union=(sil+mask-sil*mask).sum((1,2));iou=1-inter/union.clamp_min(1)
                for name,objective in [('rendered_depth',dz),('silhouette',iou)]:
                    values[name].extend(torch.autograd.grad(objective.sum(),camera,retain_graph=True)[0].norm(dim=1).tolist())
                hits.extend(((depth>0)&mask).sum((1,2)).div(mask.sum((1,2))).tolist())
    median={k:float(np.median(v)) for k,v in values.items()}
    weights={k:median['native']/median[k] for k in ['rendered_depth','silhouette']}
    assert all(np.isfinite(v) and v>0 for v in weights.values()),'SCAN_OUTPUT_GRADIENT_CALIBRATION_FAILED'
    result=dict(status='PASS',weights=weights,gradient_norms=values,median_gradient_norms=median,
        scan_hit_rates=hits,native_rows=[native[i]['cache_file'] for i in ni],scan_rows=[scan[i]['sample_id'] for i in selected],
        formula='median per-image gradient of 2*Camera SmoothL1 / median per-image geometric gradient at frozen Official initialization',
        reduction='calibration unweighted per-image; mixed training camera-group weights independently normalized to mean1',
        seed=20261011,VAL_read=False,TEST_read=False,camera_B_read=False,
        native_manifest_sha256=sha(Path(paths['native_cache'])/'CACHE_MANIFEST.json'),
        scan_manifest_sha256=sha(Path(paths['scan_cache'])/'CACHE_MANIFEST.json'),code_sha256=sha(__file__))
    a.out.write_text(json.dumps(result,indent=2));engine.close();print('SCAN_LOSS_FROZEN',weights,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--paths',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    main(p.parse_args())
