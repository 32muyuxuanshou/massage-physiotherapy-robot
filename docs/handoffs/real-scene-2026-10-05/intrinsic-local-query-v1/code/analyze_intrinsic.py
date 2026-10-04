"""Actual-cache replay and all-source figures for local intrinsic matching."""
import csv,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_intrinsic import BASE,PAIR,OUT,read,write,sha


def main():
    res=read(OUT/'RESULTS.json');cases={(r['dataset'],r['name'],r['condition'],r['seed']):r for r in read(OUT/'CASE_MANIFEST.json')}
    templates={d:dict(np.load(PAIR/(d+'_template.npz'))) for d in ['faust','scape']};loaded={};checks=0
    for r in res['raw_evaluation']:
        assert sha(Path(r['prediction_path']))==r['prediction_sha256']
        case=cases[(r['dataset'],r['name'],r['condition'],r['input_seed'])]
        if case['path'] not in loaded:
            assert sha(Path(case['path']))==case['sha256'];loaded[case['path']]=dict(np.load(case['path']))
        z=loaded[case['path']];t=templates[r['dataset']]
        with np.load(r['prediction_path']) as p:
            q=p['all_query_reference_idx'];chosen=p['all_retrieved_observed_idx'];vis=np.isin(q,z['local_reference_idx'])
            assert np.array_equal(vis,p['query_visible_mask'])
            true=np.array([np.flatnonzero(z['local_reference_idx']==j)[0] for j in q[vis]])
            qe=np.linalg.norm(t['canonical_xyz'][z['local_reference_idx'][chosen[vis]]]-t['canonical_xyz'][q[vis]],axis=1)*100
            se=np.linalg.norm(z['true_surface_xyz'][chosen[vis]]-z['true_surface_xyz'][true],axis=1)*100
            assert np.allclose(qe,p['query_canonical_errors_percent'],atol=1e-10);assert np.allclose(se,p['query_surface_errors_percent'],atol=1e-10)
            assert abs(np.median(qe)-r['visible_query_median_percent'])<1e-10;checks+=4
    for a in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(a['path']))==a['sha256']
    write(OUT/'CACHE_REPLAY.json',dict(status='PASS',actual_predictions=len(res['raw_evaluation']),actual_cases=len(loaded),checks=checks,source_unchanged=True))
    with (OUT/'PER_SOURCE_RESULTS.csv').open('w',newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=res['per_source'][0].keys());w.writeheader();w.writerows(res['per_source'])
    (OUT/'figures').mkdir(exist_ok=True);figures=[]
    for d in templates:
        for name in sorted({r['name'] for r in res['per_source'] if r['dataset']==d}):
            fig,axes=plt.subplots(1,2,figsize=(12,4));modes=res['modes']
            for j,condition in enumerate(['FULL','PARTIAL_BAND','NOISY_PARTIAL']):
                group=[r for r in res['per_source'] if (r['dataset'],r['name'],r['condition'])==(d,name,condition)]
                for ax,key in zip(axes,['visible_query_median_percent','visible_query_p95_percent']):
                    ax.bar(np.arange(3)+(j-1)*.24,[next(r[key] for r in group if r['mode']==m) for m in modes],width=.24,label=condition)
            for ax,title in zip(axes,['Median identity distance','P95 identity distance']):
                ax.set_xticks(range(3),['HKS','DiffNet NN','Local FMap']);ax.set_ylabel('% respective sqrt-area; NOT mm');ax.set_title(title);ax.legend(fontsize=7)
            fig.suptitle(d+' / '+name+' / local operators only; full pretraining, no local training');fig.tight_layout()
            p=OUT/'figures'/f'{d}_{name}.png';fig.savefig(p,dpi=110);plt.close(fig);figures.append(dict(dataset=d,name=name,path=str(p),sha256=sha(p)))
    write(OUT/'VISUALIZATION_MANIFEST.json',figures)
    print('INTRINSIC_CACHE_REPLAY',len(res['raw_evaluation']),checks,len(figures),flush=True)


if __name__=='__main__':main()
