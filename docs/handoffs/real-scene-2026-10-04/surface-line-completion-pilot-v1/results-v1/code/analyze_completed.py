"""Read cached predictions: input sensitivity, initialization sensitivity and source integrity."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def comparable_curves(rows, ys):
    if any(row['status'] != 'COMPLETE' for row in rows):
        return None
    curves=[]
    for row in rows:
        with np.load(row['path']) as z:
            curves.append(z['query_xy_m'])
    keep=(ys >= max(c[:, 1].min() for c in curves)) & (ys <= min(c[:, 1].max() for c in curves))
    positions=np.stack([np.interp(ys[keep], c[:, 1], c[:, 0]) for c in curves])*1000
    return positions, int(keep.sum()), float(keep.mean())


def main(root):
    rows=read(root/'PREDICTION_MANIFEST.json')
    cases={r['candidate_id']:r for r in read(root/'DATA_MANIFEST.json')}
    results=read(root/'RESULTS.json')
    freeze=read(root/'PREDICTION_FREEZE.json')
    assert sha(root/'PREDICTION_MANIFEST.json') == freeze['manifest_sha256']
    assets={**freeze['input_sha256'], **freeze['prediction_sha256']}
    assert all(sha(path) == digest for path,digest in assets.items())
    sensitivity=[]
    initializations=[]
    for candidate in sorted({r['candidate_id'] for r in rows}):
        with np.load(cases[candidate]['path']) as z:
            ys=z['ys_m']
        for method in sorted({r['method'] for r in rows}):
            subset=[r for r in rows if r['candidate_id']==candidate and r['method']==method]
            for seed in sorted({r['seed'] for r in subset}, key=lambda x:-1 if x is None else x):
                group=[next(r for r in subset if r['condition']==condition and r['seed']==seed)
                       for condition in ['FULL','MISSING_0','MISSING_1','MISSING_2']]
                comparison=comparable_curves(group, ys)
                row=dict(candidate_id=candidate,method=method,seed=seed,
                         complete=comparison is not None,failed_conditions=[r['condition'] for r in group if r['status']!='COMPLETE'])
                if comparison is not None:
                    p,n,coverage=comparison
                    shift=np.abs(p[1:]-p[0])
                    span=np.ptp(p[1:],axis=0)
                    row.update(common_rows=n,common_row_fraction=coverage,
                               missing_vs_full_median_mm=float(np.median(shift)),
                               missing_vs_full_p95_mm=float(np.quantile(shift,.95)),
                               missing_pairwise_span_median_mm=float(np.median(span)),
                               missing_pairwise_span_p95_mm=float(np.quantile(span,.95)))
                sensitivity.append(row)
            if method in ['NO_BLOCK_AUG','BLOCK_AUG']:
                for condition in ['FULL','MISSING_0','MISSING_1','MISSING_2']:
                    group=[next(r for r in subset if r['condition']==condition and r['seed']==seed) for seed in [0,1,2]]
                    p,n,coverage=comparable_curves(group,ys)
                    span=np.ptp(p,axis=0)
                    initializations.append(dict(candidate_id=candidate,method=method,condition=condition,
                        common_rows=n,common_row_fraction=coverage,initialization_span_median_mm=float(np.median(span)),
                        initialization_span_p95_mm=float(np.quantile(span,.95))))
    per_scan=[]
    for candidate in sorted({r['candidate_id'] for r in sensitivity}):
        for method in sorted({r['method'] for r in sensitivity}):
            group=[r for r in sensitivity if r['candidate_id']==candidate and r['method']==method]
            entry=dict(candidate_id=candidate,method=method,complete=all(r['complete'] for r in group))
            if entry['complete']:
                for metric in ['missing_vs_full_median_mm','missing_vs_full_p95_mm',
                               'missing_pairwise_span_median_mm','missing_pairwise_span_p95_mm']:
                    entry[metric]=float(np.mean([r[metric] for r in group]))
            per_scan.append(entry)
    aggregation=[]
    for method in sorted({r['method'] for r in sensitivity}):
        complete=[r for r in per_scan if r['method']==method and r['complete']]
        entry=dict(method=method,scans=6,complete_scans=len(complete))
        for metric in ['missing_vs_full_median_mm','missing_vs_full_p95_mm',
                       'missing_pairwise_span_median_mm','missing_pairwise_span_p95_mm']:
            entry[metric]=float(np.median([r[metric] for r in complete])) if complete else None
        aggregation.append(entry)
    write(root/'STABILITY_ANALYSIS.json',dict(scope='native X curve sensitivity; not 3D/acupoint accuracy',
        evaluation_role='6 previously consumed source groups; patient independence not verified',
        aggregation='model initialization mean within scan, then median across complete scans',
        per_model=sensitivity,per_scan=per_scan,aggregate=aggregation,initialization=initializations))
    sources=read(root/'SOURCE_FREEZE.json')
    integrity=[dict(path=r['path'],expected_sha256=r['sha256'],actual_sha256=sha(r['path'])) for r in sources]
    assert all(r['expected_sha256']==r['actual_sha256'] for r in integrity)
    write(root/'POST_EXECUTION_INTEGRITY.json',dict(status='PASS',source_assets=len(integrity),
        frozen_prediction_assets=len(assets),prediction_records=len(rows),sources=integrity))
    figures=root/'figures'
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for trained in read(root/'TRAINING_LEDGER.json'):
        history=read(trained['history_path'])
        label=f"{trained['strategy']} / {trained['seed']}"
        for ax,key in zip(axes,['training_loss','dev_lateral_mean_mm']):
            ax.plot([r['epoch'] for r in history],[r[key] for r in history],label=label)
            ax.set_xlabel('Epoch'); ax.set_ylabel(key); ax.grid(alpha=.2)
    axes[1].legend(fontsize=7)
    fig.tight_layout();fig.savefig(figures/'training_history.png',dpi=140);plt.close(fig)
    methods=['BOUNDARY_CENTER','SYMMETRY_DP','GROOVE_DP','NO_BLOCK_AUG','BLOCK_AUG']
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    x=np.arange(len(methods))
    for condition,offset,color in [('FULL',-.18,'steelblue'),('MISSING',.18,'darkorange')]:
        selected=[next(r for r in results['aggregate'] if r['method']==m and r['condition']==condition) for m in methods]
        values=[r['median_of_scan_lateral_median_mm'] for r in selected]
        axes[0].bar(x+offset,[np.nan if v is None else v for v in values],width=.36,label=condition,color=color)
        for position,value,row in zip(x+offset,values,selected):
            axes[0].text(position,0 if value is None else value,f"{row['complete_scans']}/6",ha='center',va='bottom',fontsize=8)
    axes[0].set_ylabel('Author-line lateral error / mm'); axes[0].legend()
    stability=[next(r for r in aggregation if r['method']==m) for m in methods]
    values=[r['missing_pairwise_span_median_mm'] for r in stability]
    axes[1].bar(x,[np.nan if v is None else v for v in values],color='seagreen')
    for position,value,row in zip(x,values,stability):
        axes[1].text(position,0 if value is None else value,f"{row['complete_scans']}/6",ha='center',va='bottom',fontsize=8)
    axes[1].set_ylabel('Missing-input curve span / mm')
    for ax in axes:
        ax.set_xticks(x,methods,rotation=25,ha='right');ax.grid(axis='y',alpha=.2)
    fig.suptitle('Different complete cohorts: see paired common-position results; NOT acupoint accuracy')
    fig.tight_layout();fig.savefig(figures/'accuracy_and_stability.png',dpi=140);plt.close(fig)
    print('ANALYSIS_COMPLETE',json.dumps(aggregation),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args().root)
