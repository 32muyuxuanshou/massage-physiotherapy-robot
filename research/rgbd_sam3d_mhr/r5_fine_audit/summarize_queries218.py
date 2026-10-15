"""Describe replayed A-only observations against unchanged historical outcomes."""
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr

WORK=Path('/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1')


def main():
    old=json.loads((WORK/'previous/reports/Q1_RECORDS.json').read_text())
    original={(r['dataset'],r['seed'],r['key']):r for r in old}
    frames=[];mismatches=[];runtime=[]
    for seed in [11,23,37]:
        d=json.loads((WORK/'query_replay_frozen_coarse'/('s'+str(seed))/'RESULTS.json').read_text())
        assert d['status']=='QUERY_REPLAY_COMPLETE' and len(d['records'])==902
        runtime.append(dict(seed=seed,**{k:v for k,v in d.items() if k!='records'}))
        for r in d['records']:
            source=original[r['dataset'],r['seed'],r['key']]
            metric='camera_mm' if r['dataset']=='native' else 'median_mm' if r['dataset']=='real' else 'pve_mm'
            with np.load(r['output_file']) as z:
                geo=z['geometry'];obs=z['observed'];spread=z['neighborhood_range_m']
            f={k:r[k] for k in ['dataset','seed','key','identity','role','trace_eligible','observed_queries']}
            coarse=source['stages']['coarse'][metric];final=source['stages']['final'][metric]
            f.update(metric=metric,coarse_error=coarse,final_error=final,gain_mm=coarse-final,worse=final>coarse,
                abs_z_median_mm=float(np.median(abs(geo[obs,14]))*1000) if obs.any() else None,
                signed_z_mad_mm=r['signed_z_mm']['mad'] if r['signed_z_mm'] else None,
                signed_z_std_mm=r['signed_z_mm']['std'] if r['signed_z_mm'] else None,
                local_depth_range_median_mm=float(np.median(spread[obs & np.isfinite(spread)])*1000) if obs.any() else None,
                top1_max_pool_channel_fraction=r['top1_max_pool_channel_fraction'],
                top5_max_pool_channel_fraction=r['top5_max_pool_channel_fraction'],
                fine_norm_mm=source['fine_norm_mm'])
            frames.append(f)
            if not r['trace_eligible']:mismatches.append(r)
    assert len(frames)==len(original)==2706
    features=['abs_z_median_mm','signed_z_mad_mm','signed_z_std_mm',
        'local_depth_range_median_mm','top1_max_pool_channel_fraction','top5_max_pool_channel_fraction','observed_queries']
    groups=[]
    for dataset in ['native','real','behave']:
        for role in sorted({r['role'] for r in frames if r['dataset']==dataset}):
            for seed in [11,23,37]:
                allrows=[r for r in frames if r['dataset']==dataset and r['role']==role and r['seed']==seed]
                valid=[r for r in allrows if r['trace_eligible']]
                result=dict(dataset=dataset,role=role,seed=seed,total=len(allrows),eligible=len(valid),
                    excluded_total=len(allrows)-len(valid),total_worse=sum(r['worse'] for r in allrows),
                    eligible_worse=sum(r['worse'] for r in valid),features={})
                for name in features:
                    rr=[r for r in valid if r[name] is not None]
                    bad=[r[name] for r in rr if r['worse']];good=[r[name] for r in rr if not r['worse']]
                    rho=float(spearmanr([r[name] for r in rr],[r['gain_mm'] for r in rr]).statistic) if len(set(r[name] for r in rr))>1 else None
                    result['features'][name]=dict(worse_median=float(np.median(bad)) if bad else None,
                        not_worse_median=float(np.median(good)) if good else None,spearman_with_gain=rho,
                        worse_count=len(bad),not_worse_count=len(good))
                groups.append(result)
    report=dict(status='QUERY_AUDIT_COMPLETE',groups=groups,records=frames,runtime=runtime,
        excluded_records=mismatches,trace_eligible=sum(r['trace_eligible'] for r in frames),
        original_primary_errors_unchanged=True,training=False,
        interpretation='Descriptive only; no threshold selected, no object/clothing/edge artifact GT, no Camera B fit. Historical per-query masks absent; counts/eigens/numerics checked, not independent identity proof.')
    out=WORK/'reports';out.mkdir(exist_ok=True)
    (out/'QUERY_AUDIT.json').write_text(json.dumps(report,indent=2))
    (out/'ALL_REPLAY_MISMATCHES.json').write_text(json.dumps(mismatches,indent=2))
    print('QUERY_AUDIT_COMPLETE',len(frames),report['trace_eligible'],'mismatches',len(mismatches),flush=True)


if __name__=='__main__':main()
