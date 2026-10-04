"""Frozen author encoder on exactly the local observations; no complete-shape operators."""
import argparse,sys,time
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree
BASE=Path('/raid5/xuhd/datasets/registered_human_correspondence_20261005')
PAIR=BASE/'paired_query_v1';OUT=BASE/'intrinsic_local_query_v1';AUTHOR=BASE/'author_diffusion_net'
sys.path[:0]=[str(BASE/'author_deps'),str(AUTHOR/'src'),str(AUTHOR/'experiments/functional_correspondence'),str(BASE/'code')]
import diffusion_net
from fmaps_model import FunctionalMapCorrespondenceWithDiffusionNetFeatures
from experiment import read,write,sha


def operator(feat,path):
    unique,first,inverse=np.unique(feat[:,:3],axis=0,return_index=True,return_inverse=True)
    v=torch.tensor(unique,dtype=torch.float32);f=torch.empty((0,3),dtype=torch.int64)
    n=torch.tensor(feat[first,3:6],dtype=torch.float32)
    frames,mass,L,ev,vec,gx,gy=diffusion_net.geometry.get_operators(v,f,k_eig=128,normals=n,op_cache_dir=str(OUT/'operator_cache'))
    hks=diffusion_net.geometry.compute_hks_autoscale(ev,vec,16)
    torch.save(dict(shape=[v,f,frames,mass,L,ev,vec,gx,gy,hks,torch.empty(0,dtype=torch.int64)],first_idx=torch.tensor(first),inverse_idx=torch.tensor(inverse)),path)
    return dict(path=str(path),sha256=sha(path),original_points=len(feat),unique_points=len(unique))


def prepare():
    torch.set_num_threads(2);OUT.mkdir(exist_ok=True)
    for d in ['operators','operator_cache']:(OUT/d).mkdir(exist_ok=True)
    cases=[r for r in read(PAIR/'CASE_MANIFEST.json') if r['role'] not in ['train','dev']]
    ck=AUTHOR/'experiments/functional_correspondence/pretrained_models/faust_hks.pth'
    cfg=dict(modes=['HKS_NN','DIFFNET_DESCRIPTOR_NN','DIFFNET_LOCAL_FMAP'],k_eig=128,hks=16,n_fmap=30,lambda_fmap=.001,
        checkpoint_path=str(ck),checkpoint_sha256=sha(ck),author_commit='b1019b049597711d10259ce28250f7dfc4335a2b',new_training=0,full_geometry_to_model=False,
        source_preprocessing_uses_full_normalization=True,metric_unit='percent respective sqrt-area, NOT mm')
    write(OUT/'CONFIG.json',cfg);write(OUT/'CASE_MANIFEST.json',cases)
    assets=[OUT/'PROTOCOL.md',OUT/'CONFIG.json',OUT/'CASE_MANIFEST.json',ck,*list((OUT/'code').glob('*.py')),
        AUTHOR/'src/diffusion_net/geometry.py',AUTHOR/'src/diffusion_net/layers.py',AUTHOR/'experiments/functional_correspondence/fmaps_model.py',
        *[PAIR/(d+'_template.npz') for d in ['faust','scape']],*[Path(r['path']) for r in cases]]
    write(OUT/'SOURCE_FREEZE.json',[dict(path=str(p),sha256=sha(p)) for p in assets])
    start=time.monotonic();rows=[]
    for d in ['faust','scape']:
        with np.load(PAIR/(d+'_template.npz')) as z:feat=z['features'][:,:6]
        rows.append(dict(dataset=d,name='TEMPLATE',**operator(feat,OUT/'operators'/(d+'_template.pt'))))
    for j,r in enumerate(cases):
        with np.load(r['path']) as z:feat=z['features'][:,:6]
        rows.append(dict(dataset=r['dataset'],name=r['name'],condition=r['condition'],input_seed=r['seed'],case_sha256=r['sha256'],
            **operator(feat,OUT/'operators'/f'{r["dataset"]}_{r["name"]}_{r["condition"]}_{r["seed"]}.pt')))
        if (j+1)%30==0:print('LOCAL_OPERATORS',j+1,round(time.monotonic()-start,1),flush=True)
    write(OUT/'OPERATOR_MANIFEST.json',rows);write(OUT/'PREPARATION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,operators=len(rows),cases=len(cases),full_surface_operators_used=False))
    print('LOCAL_PREP_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


def loadop(row):
    assert sha(Path(row['path']))==row['sha256'];z=torch.load(row['path'],weights_only=True)
    return [t.cuda() for t in z['shape']],z['first_idx'].numpy(),z['inverse_idx'].numpy()


def unit(x):return x/np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-20)


def run():
    start=time.monotonic();torch.set_num_threads(2);cfg=read(OUT/'CONFIG.json')
    for a in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(a['path']))==a['sha256']
    m=FunctionalMapCorrespondenceWithDiffusionNetFeatures(input_features='hks').cuda();m.load_state_dict(torch.load(cfg['checkpoint_path'],weights_only=True));m.eval()
    operators=read(OUT/'OPERATOR_MANIFEST.json');source={};templates={d:dict(np.load(PAIR/(d+'_template.npz'))) for d in ['faust','scape']}
    for d in templates:
        row=next(r for r in operators if r['dataset']==d and r['name']=='TEMPLATE');shape,first,inverse=loadop(row)
        with torch.no_grad():desc=m.feature_extractor(shape[9],shape[3],L=shape[4],evals=shape[5],evecs=shape[6],gradX=shape[7],gradY=shape[8],faces=shape[1]).cpu().numpy()
        source[d]=(shape,first,inverse,desc)
    rows=[];(OUT/'predictions').mkdir(exist_ok=True)
    for case in read(OUT/'CASE_MANIFEST.json'):
        d=case['dataset'];r=next(r for r in operators if (r['dataset'],r['name'],r.get('condition'),r.get('input_seed'))==(d,case['name'],case['condition'],case['seed']))
        target,first,inverse=loadop(r);ss,sfirst,sinverse,sdesc=source[d];t=templates[d];q=t['query_local_ids'];uq=sinverse[q]
        with torch.no_grad():C,_,tdesc=m(ss,target)
        predmap=cKDTree((ss[6][:,:30]@C[0].T).cpu().numpy()).query(target[6][:,:30].cpu().numpy())[1]
        predicted_source=t['canonical_xyz'][sfirst[predmap]]
        choices={
            'HKS_NN':first[cKDTree(unit(target[9].cpu().numpy())).query(unit(ss[9].cpu().numpy()[uq]))[1]],
            'DIFFNET_DESCRIPTOR_NN':first[cKDTree(unit(tdesc.cpu().numpy())).query(unit(sdesc[uq]))[1]],
            'DIFFNET_LOCAL_FMAP':first[cKDTree(predicted_source).query(t['canonical_xyz'][q])[1]]}
        with np.load(case['path']) as z:ids=z['local_reference_idx'];surface=z['true_surface_xyz']
        vis=np.isin(q,ids);true=np.array([np.flatnonzero(ids==j)[0] for j in q[vis]])
        for mode,chosen in choices.items():
            qe=np.linalg.norm(t['canonical_xyz'][ids[chosen[vis]]]-t['canonical_xyz'][q[vis]],axis=1)*100
            se=np.linalg.norm(surface[chosen[vis]]-surface[true],axis=1)*100
            path=OUT/'predictions'/f'{d}_{case["name"]}_{case["condition"]}_{case["seed"]}_{mode}.npz'
            np.savez_compressed(path,all_query_reference_idx=q,all_retrieved_observed_idx=chosen,query_visible_mask=vis,
                query_canonical_errors_percent=qe,query_surface_errors_percent=se)
            rows.append(dict(dataset=d,name=case['name'],condition=case['condition'],input_seed=case['seed'],mode=mode,
                visible_query_median_percent=float(np.median(qe)),visible_query_p95_percent=float(np.quantile(qe,.95)),visible_surface_query_median_percent=float(np.median(se)),
                query_visible_fraction=float(vis.mean()),prediction_path=str(path),prediction_sha256=sha(path),case_sha256=case['sha256'],operator_sha256=r['sha256']))
        if case['condition']=='NOISY_PARTIAL' and case['seed']==2:print('LOCAL_SOURCE',d,case['name'],round(time.monotonic()-start,1),flush=True)
    metrics=['visible_query_median_percent','visible_query_p95_percent','visible_surface_query_median_percent','query_visible_fraction'];per=[];aggregate=[]
    for d in templates:
        for name in sorted({r['name'] for r in rows if r['dataset']==d}):
            for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
                for mode in cfg['modes']:
                    group=[r for r in rows if (r['dataset'],r['name'],r['condition'],r['mode'])==(d,name,condition,mode)]
                    per.append(dict(dataset=d,name=name,condition=condition,mode=mode,**{k:float(np.mean([r[k] for r in group])) for k in metrics}))
        for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
            for mode in cfg['modes']:
                group=[r for r in per if (r['dataset'],r['condition'],r['mode'])==(d,condition,mode)]
                aggregate.append(dict(dataset=d,condition=condition,mode=mode,sources=len(group),**{k:float(np.median([r[k] for r in group])) for k in metrics}))
    write(OUT/'RESULTS.json',dict(status='COMPLETE',aggregate=aggregate,per_source=per,raw_evaluation=rows,**cfg))
    for a in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(a['path']))==a['sha256']
    write(OUT/'EXECUTION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,cases=len(rows)//3,evaluations=len(rows),source_unchanged=True))
    print('LOCAL_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','run','all'],required=True);a=p.parse_args()
    if a.phase=='all':prepare();run()
    else:{'prepare':prepare,'run':run}[a.phase]()
