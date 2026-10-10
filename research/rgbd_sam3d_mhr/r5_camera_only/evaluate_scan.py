"""Frozen textured VAL surface diagnostics with original perspective renderer."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from camera_head import CameraHead
from scan_render import ScanTable
from train_camera import forward,sha


def metrics(d):
    return dict(median_mm=float(np.median(d)*1000),p95_mm=float(np.quantile(d,.95)*1000)) if len(d) else None


def group(records):
    metrics_keys=['full_mask_median_mm','full_mask_p95_mm','hit_rate','silhouette_iou']
    result={}
    for identity in sorted({r['identity'] for r in records}):
        rr=[r for r in records if r['identity']==identity]
        assets={}
        for asset in sorted({r['asset_id'] for r in rr}):
            aa=[r for r in rr if r['asset_id']==asset]
            groups={name:{k:float(np.mean([r[k] for r in aa if r['camera_group']==name])) for k in metrics_keys}
                    for name in sorted({r['camera_group'] for r in aa})}
            assets[asset]=dict(groups=groups,metrics={k:float(np.mean([v[k] for v in groups.values()])) for k in metrics_keys})
        result[identity]=dict(assets=assets,metrics={k:float(np.mean([v['metrics'][k] for v in assets.values()])) for k in metrics_keys})
    return dict(identity_equal={k:float(np.mean([v['metrics'][k] for v in result.values()])) for k in metrics_keys},per_identity=result)


def run(a):
    torch.set_num_threads(2)
    scan=ScanTable(a.root/'assets/compact_scan',a.root/'assets/scan_labels',roles=('VAL',))
    state=torch.load(a.checkpoint,map_location='cpu',weights_only=False)
    mode=state['execution_identity']['mode']
    if mode in ['mixed','native_only']:mode='metric_xyz'
    model=CameraHead(state['head']['metric_mean'],state['head']['metric_std'],mode).cuda()
    model.load_state_dict(state['head']);model.eval()
    records=[];baseline=[]
    with torch.no_grad():
        for b in range(0,len(scan.rows),4):
            index=np.arange(b,min(b+4,len(scan.rows)))
            camera=forward(model,scan.data,index,'cuda')
            body=scan.body[index].cuda();K=scan.data['K'][index].cuda()
            d,s=scan.renderer(body+camera[:,None],K)
            od,os=scan.renderer(body+scan.data['original_camera'][index].cuda()[:,None],K)
            for j,i in enumerate(index):
                row=scan.rows[i];mask=scan.mask[i].numpy();target=scan.depth[i].numpy()
                pred,predsil=d[j].cpu().numpy(),s[j].cpu().numpy()
                original,originalsil=od[j].cpu().numpy(),os[j].cpu().numpy()
                common=mask&(pred>0)&(original>0)
                for name,depth,sil,dest in [('Official',original,originalsil,baseline),('model',pred,predsil,records)]:
                    error=np.abs(depth[mask]-target[mask]);summary=metrics(error)
                    intersection=(sil*mask).sum();union=(sil+mask-sil*mask).sum()
                    dest.append(dict(sample_id=row['sample_id'],identity=row['identity'],asset_id=row['asset_id'],
                        camera_group=row['view']['group'],view=row['view'],truncated=row['image_truncated'],method=name,
                        full_mask_median_mm=summary['median_mm'],full_mask_p95_mm=summary['p95_mm'],
                        hit_rate=float(np.mean(depth[mask]>0)),silhouette_iou=float(intersection/max(1,union)),
                        common_hit=metrics(np.abs(depth[common]-target[common])),common_points=int(common.sum()),
                        total_person_points=int(mask.sum())))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(dict(status='COMPLETE',checkpoint_sha256=sha(a.checkpoint),
        model=group(records),Official=group(baseline),records=records,baseline_records=baseline,
        aggregation='camera configurations -> camera factor group -> source scan -> identity, each equal',
        TEST_read=False,camera_B_read=False,root_GT=False,
        interpretation='visible clothed scan render surface agreement; full mask counts missing hits as Z=0; pairwise common hits reported separately'),indent=2))
    print('SCAN_EVAL_COMPLETE',a.checkpoint,group(records)['identity_equal'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['root','checkpoint','out']:p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
