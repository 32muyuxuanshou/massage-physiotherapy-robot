"""Cache replay and source-complete metric plots; no raw scan geometry in public figs."""
import json,csv,time
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiment import ROOT,read,write,sha


def main():
    start=time.monotonic();result=read(ROOT/'RESULTS.json');errors=[]
    for r in result['raw_evaluation']:
        assert sha(Path(r['prediction_path']))==r['prediction_sha256']
        with np.load(r['prediction_path']) as z:
            e=np.linalg.norm(z['predicted_canonical']-z['canonical_gt'],axis=1)*100
            qe=z['query_canonical_errors_percent'];se=z['query_surface_errors_percent']
            values=dict(canonical_median_percent=np.median(e),canonical_p95_percent=np.quantile(e,.95),
                visible_query_median_percent=np.median(qe),visible_query_p95_percent=np.quantile(qe,.95),
                visible_surface_query_median_percent=np.median(se))
            errors.extend(abs(float(v)-r[k]) for k,v in values.items())
    assert max(errors)<1e-6
    (ROOT/'figures').mkdir(exist_ok=True)
    for name in sorted({r['name'] for r in result['per_source']}):
        fig,axes=plt.subplots(1,3,figsize=(13,4))
        modes=['TEMPLATE_NN','POINT_GLOBAL','PRIOR_GLOBAL','PRIOR_LOCAL']
        for ax,condition in zip(axes,['FULL','PARTIAL_BAND','NOISY_PARTIAL']):
            rows=[next(r for r in result['per_source'] if (r['name'],r['condition'],r['mode'])==(name,condition,m)) for m in modes]
            ax.bar(np.arange(4)-.15,[r['visible_query_median_percent'] for r in rows],.3,label='median')
            ax.bar(np.arange(4)+.15,[r['visible_query_p95_percent'] for r in rows],.3,label='P95')
            ax.set_xticks(range(4),['NN','Global','Prior','PriorLocal']);ax.set_title(condition);ax.set_ylabel('Template sqrt-area / %');ax.legend()
        fig.suptitle(name+' / visible engineering query identity errors; NOT acupoint mm');fig.tight_layout();fig.savefig(ROOT/'figures'/(name+'.png'),dpi=100);plt.close(fig)
    with (ROOT/'PER_SOURCE_RESULTS.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=result['per_source'][0].keys());w.writeheader();w.writerows(result['per_source'])
    for r in read(ROOT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    write(ROOT/'CACHE_VERIFICATION.json',dict(status='PASS',reopened_predictions=len(result['raw_evaluation']),numeric_checks=len(errors),maximum_difference_percent=max(errors),source_unchanged=True,
        clinical_validated=False,seconds=time.monotonic()-start,scope='Actual cached fields and metric replay; registered reference is not clinical GT'))
    print('ANALYSIS_COMPLETE',len(errors),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':main()
