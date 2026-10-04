"""Replay all learned and no-learning controls; retain per-initialization results."""
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_learning import OUT,PAIR,read,write,sha


def main():
    learned=read(OUT/'RESULTS.json');baseline=read(OUT/'BASELINE_RESULTS.json');rows=learned['raw_evaluation']+baseline['raw_evaluation']
    cases={(r['dataset'],r['name'],r['condition'],r['seed']):r for r in read(OUT/'CASE_MANIFEST.json')};templates={d:dict(np.load(PAIR/(d+'_template.npz'))) for d in ['faust','scape']}
    loaded={};checks=0
    for r in rows:
        assert sha(Path(r['prediction_path']))==r['prediction_sha256'];case=cases[(r['dataset'],r['name'],r['condition'],r['input_seed'])]
        if case['path'] not in loaded:
            assert sha(Path(case['path']))==case['sha256'];loaded[case['path']]=dict(np.load(case['path']))
        z=loaded[case['path']];t=templates[r['dataset']]
        with np.load(r['prediction_path']) as p:
            q=p['all_query_reference_idx'];chosen=p['all_retrieved_observed_idx'];vis=np.isin(q,z['local_reference_idx']);assert np.array_equal(vis,p['query_visible_mask'])
            true=np.array([np.flatnonzero(z['local_reference_idx']==j)[0] for j in q[vis]])
            qe=np.linalg.norm(t['canonical_xyz'][q[vis]]-z['canonical_gt'][chosen[vis]],axis=1)*100
            se=np.linalg.norm(z['true_surface_xyz'][chosen[vis]]-z['true_surface_xyz'][true],axis=1)*100
            assert np.allclose(qe,p['query_canonical_errors_percent'],atol=1e-10);assert np.allclose(se,p['query_surface_errors_percent'],atol=1e-10)
            assert abs(float(np.median(qe))-r['visible_query_median_percent'])<1e-10;checks+=4
    for a in read(OUT/'SOURCE_FREEZE.json')+read(OUT/'BASELINE_SOURCE_FREEZE.json'):assert sha(Path(a['path']))==a['sha256']
    write(OUT/'CACHE_REPLAY.json',dict(status='PASS',actual_predictions=len(rows),actual_cases=len(loaded),checks=checks,source_unchanged=True,new_fit=0))
    per=baseline['per_source']+learned['per_source'];aggregate=baseline['aggregate']+learned['aggregate'];by_init=[]
    for d in templates:
        for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
            for mode in ['BODY_QUERY','INTRINSIC_QUERY','DUAL_QUERY']:
                for seed in range(3):
                    subjects=[]
                    for name in sorted({r['name'] for r in rows if r['dataset']==d}):
                        g=[r for r in rows if (r['dataset'],r['name'],r['condition'],r['mode'],r.get('model_seed',-1))==(d,name,condition,mode,seed)]
                        subjects.append(float(np.mean([r['visible_query_median_percent'] for r in g])))
                    by_init.append(dict(dataset=d,condition=condition,mode=mode,model_seed=seed,source_equal_median_percent=float(np.median(subjects))))
    write(OUT/'COMPARISON_RESULTS.json',dict(status='COMPLETE',aggregate=aggregate,per_source=per,by_initialization=by_init,raw_evaluations=len(rows),clinical_accuracy=False))
    with (OUT/'PER_SOURCE_RESULTS.csv').open('w',newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=per[0].keys());w.writeheader();w.writerows(per)
    (OUT/'figures').mkdir(exist_ok=True);figures=[]
    for d in templates:
        for name in sorted({r['name'] for r in per if r['dataset']==d}):
            fig,axes=plt.subplots(1,2,figsize=(13,4));modes=['BODY_CHART_NN','BODY_QUERY','INTRINSIC_QUERY','DUAL_QUERY']
            for j,condition in enumerate(['FULL','PARTIAL_BAND','NOISY_PARTIAL']):
                g=[r for r in per if (r['dataset'],r['name'],r['condition'])==(d,name,condition)]
                for ax,key in zip(axes,['visible_query_median_percent','visible_query_p95_percent']):ax.bar(np.arange(4)+(j-1)*.24,[next(r[key] for r in g if r['mode']==m) for m in modes],width=.24,label=condition)
            for ax,title in zip(axes,['Median identity distance','P95 identity distance']):
                ax.set_xticks(range(4),['Chart NN','Body','Intrinsic','Dual']);ax.set_ylabel('% respective sqrt-area; NOT mm');ax.set_title(title);ax.legend(fontsize=7)
            fig.suptitle(d+' / '+name+' / all conditions and all model / input seeds');fig.tight_layout();p=OUT/'figures'/f'{d}_{name}.png';fig.savefig(p,dpi=110);plt.close(fig);figures.append(dict(dataset=d,name=name,path=str(p),sha256=sha(p)))
    write(OUT/'VISUALIZATION_MANIFEST.json',figures);print('LEARNING_REPLAY_COMPLETE',len(rows),checks,len(figures),flush=True)


if __name__=='__main__':main()
