"""Actual A-query trajectories; no causal labels from association alone."""
from collections import defaultdict
import json
import numpy as np
from common import W,dump


def main():
    groups=defaultdict(list);rows=[]
    for p in sorted((W/'fits').glob('*.json')):
        r=json.loads(p.read_text());t=r['task']
        for name,m in r['methods'].items():
            if not name.startswith('proj_'):continue
            for a in m['trace']:
                row=dict(dataset=t['dataset'],role=t['role'],seed=t['seed'],key=t['key'],method=name,**a)
                rows.append(row);groups[t['dataset'],t['role'],t['seed'],name,a['iteration']].append(a)
    summary=[]
    for (d,r,s,m,i),rr in sorted(groups.items()):
        ev=np.array([a.get('normal_eigenvalues',[0,0,0]) for a in rr]);count=np.array([a.get('observed',len(a['visible_anchor_ids'])) for a in rr])
        condition=ev[:,2]/np.maximum(ev[:,0],1e-12)
        summary.append(dict(dataset=d,role=r,seed=s,method=m,iteration=i,frames=len(rr),visible_median=float(np.median(count)),visible_min=int(count.min()),zero_visible=int((count==0).sum()),
            rank_deficient_frames=sum(a['rank']<3 for a in rr),eigenvalue_medians=np.median(ev,axis=0).tolist(),
            normal_condition_median=float(np.median(condition)),normal_condition_p95=float(np.quantile(condition,.95)),normal_condition_max=float(condition.max()),
            clipped_steps=sum(a.get('step_clipped',False) for a in rr)))
    dump(W/'reports/QUERY_DIAGNOSTICS.json',summary)
    # Full anchor lists already retained in per-frame fit JSON inside private archive.
    print('QUERY_SUMMARY',len(summary),flush=True)


if __name__=='__main__':main()
