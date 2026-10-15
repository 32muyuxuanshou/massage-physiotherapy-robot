"""Fixed Native VAL visible-surface diagnosis; historical scores unchanged."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from frozen_render_losses import MeshRenderer

WORK=Path('/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1')
G=WORK/'previous/geometry'


def stats(d,mask):
    a=d[mask]*1000
    return dict(median_mm=float(a.median()),p95_mm=float(torch.quantile(a,.95)),points=len(a)) if len(a) else None


def main(seed):
    torch.set_num_threads(4)
    faces=torch.from_numpy(np.load(G/'assets/faces.npy')).cuda();renderer=MeshRenderer(faces)
    tasks=[t for t in json.loads((G/'MANIFEST.json').read_text())['tasks'] if t['dataset']=='native' and t['seed']==seed]
    assert len(tasks)==400
    rows=[]
    with torch.no_grad():
        for i,t in enumerate(tasks):
            rec=torch.load(WORK/'cache/native_scale_v2'/(t['key']+'.pt'),map_location='cpu',weights_only=False)
            with np.load(G/t['prediction']) as z:
                body=torch.from_numpy(z['body_m'].reshape(1,-1,3)).cuda()
                cameras=[torch.from_numpy(z[k].reshape(1,3)).cuda() for k in ['coarse_camera','camera_m']]
            K=rec['K'].cuda();target=rec['target_depth'].cuda().float();mask=rec['target_mask'].cuda().bool()
            # Original native K and physical 640x480 target; no crop resizing.
            assert target.shape[-2:]==(480,640)
            depth=[];sil=[]
            for camera in cameras:
                d,s=renderer(body+camera[:,None],K);depth.append(d);sil.append(s)
            common=mask&(depth[0]>0)&(depth[1]>0);stages={}
            for j,name in enumerate(['coarse','final']):
                error=(depth[j]-target).abs();hit=mask&(depth[j]>0)
                pred=sil[j]>.5;intersection=(pred&mask).sum();union=(pred|mask).sum()
                stages[name]=dict(full_mask=stats(error,mask),common_hit=stats(error,common),
                    hit_rate=float(hit.sum()/mask.sum()),silhouette_iou=float(intersection/union))
            rows.append(dict(key=t['key'],identity=t['identity'],seed=seed,stages=stages,
                common_points=int(common.sum()),target_points=int(mask.sum())))
            if (i+1)%100==0:print('NATIVE_SURFACE',seed,i+1,400,flush=True)
    out=WORK/'native_surface_tradeoff';out.mkdir(exist_ok=True)
    (out/('s%d.json'%seed)).write_text(json.dumps(dict(status='COMPLETE',records=rows,
        metric='New diagnostic axial-Z error over fixed Native clean GT person mask; misses render zero and remain in full_mask; both hit rates and common support also reported',
        training=False,real_camera_B_read=False,original_scores_unchanged=True),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);main(p.parse_args().seed)
