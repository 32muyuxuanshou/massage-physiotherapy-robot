"""Camera-label regressions versus clean visible-surface changes, no fitting."""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np


def main(root):
    out=root/'reports'
    labels=json.loads((out/'UPDATE_CLASSIFICATION.json').read_text())['records']
    labels={(r['seed'],r['key']):r for r in labels if r['dataset']=='native'}
    rows=[];groups=[]
    for seed in [11,23,37]:
        d=json.loads((root/'native_surface_tradeoff'/('s%d.json'%seed)).read_text())
        assert d['status']=='COMPLETE' and len(d['records'])==400
        selected=[]
        for r in d['records']:
            q=labels[seed,r['key']];c=r['stages']['coarse'];f=r['stages']['final']
            row=dict(seed=seed,key=r['key'],identity=r['identity'],camera_worse=q['worse'],
                camera_coarse_mm=q['coarse'],camera_final_mm=q['final'],
                full_mask_median_change_mm=f['full_mask']['median_mm']-c['full_mask']['median_mm'],
                full_mask_p95_change_mm=f['full_mask']['p95_mm']-c['full_mask']['p95_mm'],
                common_median_change_mm=f['common_hit']['median_mm']-c['common_hit']['median_mm'],
                common_p95_change_mm=f['common_hit']['p95_mm']-c['common_hit']['p95_mm'],
                hit_rate_change=f['hit_rate']-c['hit_rate'],iou_change=f['silhouette_iou']-c['silhouette_iou'],
                stages=r['stages'])
            rows.append(row);selected.append(row)
        groups.append(dict(seed=seed,total=400,
            camera_worse=sum(r['camera_worse'] for r in selected),
            camera_worse_full_mask_median_improves=sum(r['camera_worse'] and r['full_mask_median_change_mm']<0 for r in selected),
            camera_worse_common_median_improves=sum(r['camera_worse'] and r['common_median_change_mm']<0 for r in selected),
            camera_worse_both_medians_improve=sum(r['camera_worse'] and r['common_median_change_mm']<0 and r['full_mask_median_change_mm']<0 for r in selected),
            camera_worse_both_medians_and_hit_iou_nonworse=sum(r['camera_worse'] and r['common_median_change_mm']<0 and r['full_mask_median_change_mm']<0 and r['hit_rate_change']>=0 and r['iou_change']>=0 for r in selected),
            camera_surface_signs=dict(Counter(('camera_worse' if r['camera_worse'] else 'camera_not_worse')+'/'+('full_mask_worse' if r['full_mask_median_change_mm']>0 else 'full_mask_not_worse') for r in selected)),
            stage_frame_mean={stage:{
                'full_mask_median_mm':float(np.mean([r['stages'][stage]['full_mask']['median_mm'] for r in selected])),
                'full_mask_p95_mm':float(np.mean([r['stages'][stage]['full_mask']['p95_mm'] for r in selected])),
                'common_median_mm':float(np.mean([r['stages'][stage]['common_hit']['median_mm'] for r in selected])),
                'common_p95_mm':float(np.mean([r['stages'][stage]['common_hit']['p95_mm'] for r in selected])),
                'hit_rate':float(np.mean([r['stages'][stage]['hit_rate'] for r in selected])),
                'silhouette_iou':float(np.mean([r['stages'][stage]['silhouette_iou'] for r in selected]))
            } for stage in ['coarse','final']}))
    report=dict(status='COMPLETE',groups=groups,records=rows,
        aggregation='Descriptive mean over the same 400 fixed Native VAL frames per seed; no pooled metric across datasets.',
        interpretation='New clean Native visible-surface axial-Z diagnostic, not historical primary score, not prone-back/acupoint accuracy. Full-mask misses retain zero render and are penalized by target Z, so full-mask P95 includes coverage penalties and is not pure hit-surface precision.',
        training=False,camera_B_used=False,original_scores_unchanged=True)
    (out/'NATIVE_CAMERA_SURFACE_TRADEOFF.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(groups,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
