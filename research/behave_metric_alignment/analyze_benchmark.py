"""Read completed raw records; report paired failures without changing any evaluation."""
import argparse,json
from collections import defaultdict
from pathlib import Path
import numpy as np
from summarize_benchmark import aggregate


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
    official_summary=json.loads((root/'reports/AGGREGATED.json').read_text());by=defaultdict(list)
    for f in sorted((root/'evaluation').glob('*/RESULTS.json')):
        for r in json.loads(f.read_text())['records']:by[r['cell']].append(r)
    if len(by)!=30 or sum(map(len,by.values()))!=8100:raise ValueError('Require all 8100 formal records')
    if not all(aggregate(rows)==official_summary['cells'][cell] for cell,rows in by.items()):raise ValueError('Reaggregation differs from actual formal aggregate')
    lookup={(r['cell'],r['sequence'],r['frame']):r for rows in by.values() for r in rows}
    paired=[];fallback=[]
    for seed in [11,23,37]:
        for mode in ['rgb_only','g1','coarse','full']:
            for ck in ['best','last']:
                cell=f'{mode}_s{seed}_{ck}';delta=[];camera_change=[]
                for r in by[cell]:
                    off=lookup[f'official_s{seed}',r['sequence'],r['frame']]
                    tx=lookup[f'official_s{seed}_txyz',r['sequence'],r['frame']]
                    delta.append(dict(sequence=r['sequence'],frame=r['frame'],subject=r['subject'],
                        pve_delta_mm=r['pve']['pve_absolute_mm']-tx['pve']['pve_absolute_mm'],
                        p95_delta_mm=r['frame_surface_camera_equal_mean']['p95_mm']-tx['frame_surface_camera_equal_mean']['p95_mm']))
                    camera_change.append(np.asarray(r['pve']['centroid_delta_xyz_mm'])-off['pve']['centroid_delta_xyz_mm'])
                paired.append(dict(cell=cell,frames=270,pve_improved_vs_official_txyz=sum(r['pve_delta_mm']<0 for r in delta),
                    p95_improved_vs_official_txyz=sum(r['p95_delta_mm']<0 for r in delta),
                    p95_worse_vs_official_txyz=sum(r['p95_delta_mm']>0 for r in delta),
                    median_centroid_change_from_official_xyz_mm=np.median(camera_change,axis=0).tolist(),
                    worst_p95=sorted(delta,key=lambda r:r['p95_delta_mm'],reverse=True)[:10],
                    worst_pve=sorted(delta,key=lambda r:r['pve_delta_mm'],reverse=True)[:10]))
        for r in by[f'official_s{seed}_txyz']:
            if r['txyz']['fallback']:
                cases={cell:dict(pve=lookup[cell,r['sequence'],r['frame']]['pve']['pve_absolute_mm'],
                                surface=lookup[cell,r['sequence'],r['frame']]['frame_surface_camera_equal_mean'])
                       for cell in [f'official_s{seed}',f'full_s{seed}_best',f'full_s{seed}_last']}
                fallback.append(dict(seed=seed,sequence=r['sequence'],frame=r['frame'],
                    raw_translation_m=r['txyz']['raw_m'],cases=cases))
    result=dict(status='READ_ONLY_RAW_REAGGREGATION_EXACT_PASS',actual_records=8100,cells=30,
        paired=paired,fallback=fallback,centroid_change_interpretation='Exactly Camera change for preserved-Body branches; combined body/location centroid change for G1/RGB-only',
        inference='No p-values: only3 previously consumed identities; paired frame counts are descriptive, not independent subject replications')
    (root/'reports/INTERPRETATION.json').write_text(json.dumps(result,indent=2))
    for row in paired:
        if row['cell'].startswith('full_') and row['cell'].endswith('_last'):
            print(row['cell'],'PVE_improved',row['pve_improved_vs_official_txyz'],'P95_worse',row['p95_worse_vs_official_txyz'],'dCamera',row['median_centroid_change_from_official_xyz_mm'])
    print('FALLBACK_CASES',json.dumps(fallback),flush=True)


if __name__=='__main__':main()
