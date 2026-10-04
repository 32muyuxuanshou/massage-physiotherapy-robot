"""No-learning control, registered before the new models' evaluation."""
import time
import numpy as np
from scipy.spatial import cKDTree
from run_learning import OUT,read,write,sha,loaded_cases,template_data,body_features
from pathlib import Path


def main():
    start=time.monotonic();cases=[r for r in read(OUT/'CASE_MANIFEST.json') if r['role'] not in ['train','dev']]
    frozen=[Path(__file__),OUT/'BASELINE_ADDENDUM.md',OUT/'code/run_learning.py',OUT/'CONFIG.json',OUT/'CASE_MANIFEST.json',*[Path(r['path']) for r in cases]]
    assets=[dict(path=str(p),sha256=sha(p)) for p in frozen];write(OUT/'BASELINE_SOURCE_FREEZE.json',assets)
    data=loaded_cases(cases);templates={d:template_data(d) for d in ['faust','scape']};rows=[]
    (OUT/'baseline_predictions').mkdir(exist_ok=True)
    for z in data:
        r=z['row'];t=templates[r['dataset']];source=body_features(t['features'])[:,:3];target=body_features(z['features'])[:,:3]
        chosen=cKDTree(target).query(source[t['query']])[1];original=z['first'][chosen]
        with np.load(r['path']) as raw:ids=raw['local_reference_idx'];surface=raw['true_surface_xyz']
        vis=np.isin(t['query_reference'],ids);true=np.array([np.flatnonzero(ids==j)[0] for j in t['query_reference'][vis]])
        qe=np.linalg.norm(t['query_truth'][vis]-z['truth'][chosen[vis]],axis=1)*100;se=np.linalg.norm(surface[original[vis]]-surface[true],axis=1)*100
        p=OUT/'baseline_predictions'/f'{r["dataset"]}_{r["name"]}_{r["condition"]}_{r["seed"]}.npz'
        np.savez_compressed(p,all_query_reference_idx=t['query_reference'],all_retrieved_observed_idx=original,query_visible_mask=vis,query_canonical_errors_percent=qe,query_surface_errors_percent=se)
        rows.append(dict(dataset=r['dataset'],name=r['name'],condition=r['condition'],input_seed=r['seed'],mode='BODY_CHART_NN',visible_query_median_percent=float(np.median(qe)),visible_query_p95_percent=float(np.quantile(qe,.95)),visible_surface_query_median_percent=float(np.median(se)),query_visible_fraction=float(vis.mean()),prediction_path=str(p),prediction_sha256=sha(p),case_sha256=r['sha256']))
    metrics=['visible_query_median_percent','visible_query_p95_percent','visible_surface_query_median_percent','query_visible_fraction'];per=[];agg=[]
    for d in templates:
        for name in sorted({r['name'] for r in rows if r['dataset']==d}):
            for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
                g=[r for r in rows if (r['dataset'],r['name'],r['condition'])==(d,name,condition)]
                per.append(dict(dataset=d,name=name,condition=condition,mode='BODY_CHART_NN',**{k:float(np.mean([r[k] for r in g])) for k in metrics}))
        for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
            g=[r for r in per if r['dataset']==d and r['condition']==condition];agg.append(dict(dataset=d,condition=condition,mode='BODY_CHART_NN',sources=len(g),**{k:float(np.median([r[k] for r in g])) for k in metrics}))
    for a in assets:assert sha(Path(a['path']))==a['sha256']
    write(OUT/'BASELINE_RESULTS.json',dict(status='COMPLETE',aggregate=agg,per_source=per,raw_evaluation=rows,seconds=time.monotonic()-start,registered_after_training_started_before_new_network_eval=True))
    print('BODY_CHART_CONTROL_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':main()
