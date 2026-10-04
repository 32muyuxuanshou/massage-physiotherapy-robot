"""Replay the actual query caches and report every FAUST/SCAPE source."""
import csv,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE=Path('/raid5/xuhd/datasets/registered_human_correspondence_20261005')
sys.path.insert(0,str(BASE/'code'))
from experiment import read,write,sha
from inspect_data import load_off
ROOT=BASE/'paired_query_v1'


def main():
    results=read(ROOT/'RESULTS.json');cases={(r['dataset'],r['name'],r['condition'],r['seed']):r for r in read(ROOT/'CASE_MANIFEST.json')}
    templates={d:dict(np.load(ROOT/(d+'_template.npz'))) for d in ['faust','scape']}
    meshes={};loaded={};checks=0;visible=0
    for r in results['raw_evaluation']:
        assert sha(Path(r['prediction_path']))==r['prediction_sha256']
        case=cases[(r['dataset'],r['name'],r['condition'],r['input_seed'])]
        if case['path'] not in loaded:loaded[case['path']]=dict(np.load(case['path']))
        z=loaded[case['path']];t=templates[r['dataset']]
        if r['observed_mesh_path'] not in meshes:
            assert sha(Path(r['observed_mesh_path']))==r['observed_mesh_sha256'];meshes[r['observed_mesh_path']]=load_off(Path(r['observed_mesh_path']))
        v,f=meshes[r['observed_mesh_path']]
        with np.load(r['prediction_path']) as p:
            q=p['all_query_reference_idx'];chosen=p['all_retrieved_observed_idx'];vis=np.isin(q,z['local_reference_idx'])
            assert np.array_equal(vis,p['query_visible_mask'])
            assert np.array_equal(z['source_vertex_idx'][chosen],p['all_source_vertex_idx'])
            assert np.allclose(np.sum(v[f[p['all_face_id']]]*p['all_barycentric'][:,:,None],1),v[p['all_source_vertex_idx']],atol=1e-12)
            true=np.array([np.flatnonzero(z['local_reference_idx']==j)[0] for j in q[vis]])
            qe=np.linalg.norm(t['canonical_xyz'][z['local_reference_idx'][chosen[vis]]]-t['canonical_xyz'][q[vis]],axis=1)*100
            se=np.linalg.norm(z['true_surface_xyz'][chosen[vis]]-z['true_surface_xyz'][true],axis=1)*100
            assert np.allclose(qe,p['query_canonical_errors_percent'],atol=1e-10)
            assert np.allclose(se,p['query_surface_errors_percent'],atol=1e-10)
            assert abs(float(np.median(qe))-r['visible_query_median_percent'])<1e-10
            checks+=6;visible+=len(qe)
    for r in read(ROOT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    write(ROOT/'CACHE_REPLAY.json',dict(status='PASS',actual_predictions=len(results['raw_evaluation']),numeric_checks=checks,visible_queries=visible,
        actual_meshes=len(meshes),actual_cases=len(loaded),source_unchanged=True,medical_accuracy=False))
    with (ROOT/'PER_SOURCE_RESULTS.csv').open('w',newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=results['per_source'][0].keys());w.writeheader();w.writerows(results['per_source'])
    (ROOT/'figures').mkdir(exist_ok=True);figures=[]
    for d in ['faust','scape']:
        sources=sorted({r['name'] for r in results['per_source'] if r['dataset']==d})
        for name in sources:
            fig,axes=plt.subplots(1,2,figsize=(12,4));modes=['PAIRED_NN','PAIR_GLOBAL','PAIR_LOCAL']
            for j,condition in enumerate(['FULL','PARTIAL_BAND','NOISY_PARTIAL']):
                group=[r for r in results['per_source'] if (r['dataset'],r['name'],r['condition'])==(d,name,condition)]
                for ax,key in zip(axes,['visible_query_median_percent','visible_query_p95_percent']):
                    ax.bar(np.arange(3)+(j-1)*.24,[next(r[key] for r in group if r['mode']==m) for m in modes],width=.24,label=condition)
            for ax,title in zip(axes,['Median identity distance','P95 identity distance']):
                ax.set_xticks(range(3),modes);ax.set_ylabel('% respective sqrt-area; NOT mm');ax.set_title(title);ax.legend(fontsize=7)
            fig.suptitle(d+' / '+name+' / all conditions, averaged input and model seeds');fig.tight_layout()
            p=ROOT/'figures'/f'{d}_{name}.png';fig.savefig(p,dpi=110);plt.close(fig);figures.append(dict(dataset=d,name=name,path=str(p),sha256=sha(p)))
    write(ROOT/'VISUALIZATION_MANIFEST.json',figures)
    print('PAIR_CACHE_REPLAY',len(results['raw_evaluation']),checks,len(figures),flush=True)


if __name__=='__main__':main()
