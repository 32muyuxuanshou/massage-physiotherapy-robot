"""One fixed local-query training experiment with three useful architecture branches."""
import argparse,sys,time
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree
from query_model import BodyIntrinsicQuery,BASE
sys.path.insert(0,str(BASE/'intrinsic_local_query_v1/code'))
from run_intrinsic import operator,loadop,PAIR,read,write,sha
import run_intrinsic
sys.path.insert(0,str(BASE/'code'))
from experiment import rotation
OUT=BASE/'body_intrinsic_query_v1';MODES=['BODY_QUERY','INTRINSIC_QUERY','DUAL_QUERY']


def body_features(features,rng=None):
    p=features[:,:3].copy();n=features[:,3:6].copy()
    if rng is not None:R=rotation(rng);p=p@R.T;n=n@R.T
    lo,hi=np.quantile(p,[.05,.95],axis=0);x=(p-(hi+lo)/2)/np.maximum((hi-lo)/2,.01)
    return np.column_stack([x,n]).astype(np.float32)


def prepare():
    start=time.monotonic();torch.set_num_threads(2);OUT.mkdir(exist_ok=True)
    (OUT/'operators').mkdir(exist_ok=True)
    allcases=read(PAIR/'CASE_MANIFEST.json');localops=read(BASE/'intrinsic_local_query_v1/OPERATOR_MANIFEST.json')
    cfg=dict(modes=MODES,model_seeds=[0,1,2],steps=1200,batch=1,queries=24,lr_head=.001,lr_geometry=.0001,loss='soft identity CE',sigma=.01,
        pretrained_checkpoint_sha256=sha(BASE/'author_diffusion_net/experiments/functional_correspondence/pretrained_models/faust_hks.pth'),
        dev_checkpoint_selection='20 FAUST dev sources, PARTIAL_BAND input_seed0',clinical_validated=False,body_features='observed patch .05/.95 XYZ ranges + oriented normals')
    write(OUT/'CONFIG.json',cfg);write(OUT/'CASE_MANIFEST.json',allcases)
    assets=[OUT/'PROTOCOL.md',OUT/'CONFIG.json',OUT/'CASE_MANIFEST.json',*list((OUT/'code').glob('*.py')),
        BASE/'intrinsic_local_query_v1/code/run_intrinsic.py',BASE/'code/experiment.py',BASE/'author_diffusion_net/src/diffusion_net/layers.py',
        BASE/'author_diffusion_net/src/diffusion_net/geometry.py',BASE/'author_diffusion_net/experiments/functional_correspondence/fmaps_model.py',
        BASE/'author_diffusion_net/experiments/functional_correspondence/pretrained_models/faust_hks.pth',*[Path(r['path']) for r in allcases]]
    write(OUT/'SOURCE_FREEZE.json',[dict(path=str(p),sha256=sha(p)) for p in assets])
    # Reuse the frozen test/template operators; construct only train/dev local operators.
    ops=list(localops);run_intrinsic.OUT=BASE/'intrinsic_local_query_v1'
    training=[r for r in allcases if r['role'] in ['train','dev']]
    for j,r in enumerate(training):
        with np.load(r['path']) as z:feat=z['features'][:,:6]
        p=OUT/'operators'/f'{r["dataset"]}_{r["name"]}_{r["condition"]}_{r["seed"]}.pt'
        ops.append(dict(dataset=r['dataset'],name=r['name'],condition=r['condition'],input_seed=r['seed'],case_sha256=r['sha256'],**operator(feat,p)))
        if (j+1)%60==0:print('TRAIN_OPERATORS',j+1,round(time.monotonic()-start,1),flush=True)
    write(OUT/'OPERATOR_MANIFEST.json',ops);write(OUT/'PREPARATION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,new_operators=len(training),reused_operators=len(localops)))
    print('TRAIN_PREP_COMPLETE',round(time.monotonic()-start,2),flush=True)


def loaded_cases(rows):
    ops={(r['dataset'],r['name'],r.get('condition'),r.get('input_seed')):r for r in read(OUT/'OPERATOR_MANIFEST.json')};data=[]
    for r in rows:
        op=ops[(r['dataset'],r['name'],r['condition'],r['seed'])];saved=torch.load(op['path'],weights_only=True);first=saved['first_idx'].numpy()
        with np.load(r['path']) as z:features=z['features'][first,:6];truth=z['canonical_gt'][first];reference=z['local_reference_idx'][first]
        data.append(dict(row=r,shape=saved['shape'],features=features,truth=truth,reference=reference,first=first,inverse=saved['inverse_idx'].numpy()))
    return data


def to_gpu(z,rng=None):
    return [t.cuda() for t in z['shape']],torch.tensor(body_features(z['features'],rng),device='cuda')


def dev_score(m,dev,template):
    m.eval();ss,sb=to_gpu(template);queries=template['query'];values=[]
    with torch.no_grad():
        sd=m.descriptors(ss,sb)
        for z in dev:
            ts,tb=to_gpu(z);chosen=m.match(sd,m.descriptors(ts,tb),sb,tb,queries).argmax(-1).cpu().numpy()
            visible=np.isin(template['query_reference'],z['reference']);error=np.linalg.norm(template['query_truth'][visible]-z['truth'][chosen[visible]],axis=1)*100
            values.append(float(np.median(error)))
    return float(np.mean(values))


def template_data(d):
    op=next(r for r in read(OUT/'OPERATOR_MANIFEST.json') if r['dataset']==d and r['name']=='TEMPLATE');saved=torch.load(op['path'],weights_only=True);first=saved['first_idx'].numpy()
    with np.load(PAIR/(d+'_template.npz')) as t:
        queries=t['query_local_ids'];z=dict(shape=saved['shape'],features=t['features'][first,:6],truth=t['canonical_xyz'][first],reference=t['local_reference_idx'][first],
            first=first,inverse=saved['inverse_idx'].numpy(),query=saved['inverse_idx'].numpy()[queries],query_reference=queries,query_truth=t['canonical_xyz'][queries])
    return z


def train(seed):
    torch.set_num_threads(2)
    for a in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(a['path']))==a['sha256']
    allcases=read(OUT/'CASE_MANIFEST.json');training=loaded_cases([r for r in allcases if r['role']=='train']);dev=loaded_cases([r for r in allcases if r['role']=='dev' and r['condition']=='PARTIAL_BAND' and r['seed']==0])
    sources=[z for z in training if z['row']['condition']=='FULL' and z['row']['seed']==0];template=template_data('faust');ledger=[];(OUT/'checkpoints').mkdir(exist_ok=True)
    for mode in MODES:
        start=time.monotonic();torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);rng=np.random.default_rng(seed);m=BodyIntrinsicQuery(mode).cuda()
        geom=list(m.geometry.parameters()) if mode!='BODY_QUERY' else [];geo_ids={id(p) for p in geom}
        opt=torch.optim.Adam([dict(params=[p for p in m.parameters() if id(p) not in geo_ids],lr=.001),dict(params=geom,lr=.0001)])
        best=float('inf');history=[]
        for step in range(1,1201):
            s=sources[rng.integers(len(sources))];t=training[rng.integers(len(training))];selected=rng.integers(len(t['truth']),size=24)
            sq=cKDTree(s['truth']).query(t['truth'][selected])[1];ss,sb=to_gpu(s,rng);ts,tb=to_gpu(t,rng)
            wanted=torch.softmax(-torch.cdist(torch.tensor(s['truth'][sq],dtype=torch.float32,device='cuda'),torch.tensor(t['truth'],dtype=torch.float32,device='cuda'))**2/(2*.01**2),-1)
            m.train();opt.zero_grad();logits=m.match(m.descriptors(ss,sb),m.descriptors(ts,tb),sb,tb,sq)
            loss=-(wanted*torch.log_softmax(logits,-1)).sum(-1).mean();loss.backward();opt.step()
            if step%200==0:
                score=dev_score(m,dev,template);history.append(dict(step=step,loss=float(loss.item()),dev_score=score))
                if score<best:best=score;best_step=step;torch.save(dict(mode=mode,seed=seed,step=step,state_dict=m.state_dict()),OUT/'checkpoints'/f'{mode}_{seed}.pt')
                print('DUAL_TRAIN',mode,seed,step,round(score,3),round(time.monotonic()-start,1),flush=True)
        p=OUT/'checkpoints'/f'{mode}_{seed}.pt';ledger.append(dict(mode=mode,seed=seed,steps=1200,best_step=best_step,best_dev=best,seconds=time.monotonic()-start,parameters=sum(p.numel() for p in m.parameters()),checkpoint_path=str(p),checkpoint_sha256=sha(p),history=history))
        write(OUT/f'TRAINING_LEDGER_{seed}.json',dict(status='RUNNING',runs=ledger))
    write(OUT/f'TRAINING_LEDGER_{seed}.json',dict(status='COMPLETE',runs=ledger));print('DUAL_SEED_COMPLETE',seed,flush=True)


def evaluate():
    torch.set_num_threads(2);start=time.monotonic();allcases=read(OUT/'CASE_MANIFEST.json');cases=loaded_cases([r for r in allcases if r['role'] not in ['train','dev']]);templates={d:template_data(d) for d in ['faust','scape']}
    ledger=sum([read(OUT/f'TRAINING_LEDGER_{s}.json')['runs'] for s in range(3)],[]);models=[]
    for r in ledger:
        assert sha(Path(r['checkpoint_path']))==r['checkpoint_sha256'];m=BodyIntrinsicQuery(r['mode']).cuda();m.load_state_dict(torch.load(r['checkpoint_path'],weights_only=True)['state_dict']);m.eval();models.append((r,m))
    rows=[];(OUT/'predictions').mkdir(exist_ok=True)
    with torch.no_grad():
        for z in cases:
            r=z['row'];d=r['dataset'];t=templates[d];ss,sb=to_gpu(t);ts,tb=to_gpu(z)
            with np.load(r['path']) as raw:allids=raw['local_reference_idx'];surface=raw['true_surface_xyz']
            vis=np.isin(t['query_reference'],allids);true=np.array([np.flatnonzero(allids==j)[0] for j in t['query_reference'][vis]])
            for ck,m in models:
                chosen=m.match(m.descriptors(ss,sb),m.descriptors(ts,tb),sb,tb,t['query']).argmax(-1).cpu().numpy();original=z['first'][chosen]
                qe=np.linalg.norm(t['query_truth'][vis]-z['truth'][chosen[vis]],axis=1)*100;se=np.linalg.norm(surface[original[vis]]-surface[true],axis=1)*100
                p=OUT/'predictions'/f'{d}_{r["name"]}_{r["condition"]}_{r["seed"]}_{ck["mode"]}_{ck["seed"]}.npz'
                np.savez_compressed(p,all_query_reference_idx=t['query_reference'],all_retrieved_observed_idx=original,query_visible_mask=vis,query_canonical_errors_percent=qe,query_surface_errors_percent=se)
                rows.append(dict(dataset=d,name=r['name'],condition=r['condition'],input_seed=r['seed'],mode=ck['mode'],model_seed=ck['seed'],visible_query_median_percent=float(np.median(qe)),visible_query_p95_percent=float(np.quantile(qe,.95)),visible_surface_query_median_percent=float(np.median(se)),query_visible_fraction=float(vis.mean()),prediction_path=str(p),prediction_sha256=sha(p),checkpoint_sha256=ck['checkpoint_sha256'],case_sha256=r['sha256']))
            if r['condition']=='NOISY_PARTIAL' and r['seed']==2:print('DUAL_EVAL_SOURCE',d,r['name'],flush=True)
    metrics=['visible_query_median_percent','visible_query_p95_percent','visible_surface_query_median_percent','query_visible_fraction'];per=[];agg=[]
    for d in templates:
        for name in sorted({r['name'] for r in rows if r['dataset']==d}):
            for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
                for mode in MODES:
                    g=[r for r in rows if (r['dataset'],r['name'],r['condition'],r['mode'])==(d,name,condition,mode)]
                    per.append(dict(dataset=d,name=name,condition=condition,mode=mode,**{k:float(np.mean([r[k] for r in g])) for k in metrics}))
        for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
            for mode in MODES:
                g=[r for r in per if (r['dataset'],r['condition'],r['mode'])==(d,condition,mode)];agg.append(dict(dataset=d,condition=condition,mode=mode,sources=len(g),**{k:float(np.median([r[k] for r in g])) for k in metrics}))
    write(OUT/'RESULTS.json',dict(status='COMPLETE',aggregate=agg,per_source=per,raw_evaluation=rows,medical_accuracy=False,metric_unit='percent respective sqrt-area, NOT mm'))
    for a in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(a['path']))==a['sha256']
    write(OUT/'EXECUTION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,evaluations=len(rows),source_unchanged=True));print('DUAL_EVAL_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','train','evaluate'],required=True);p.add_argument('--seed',type=int,default=0);a=p.parse_args()
    if a.phase=='train':train(a.seed)
    else:{'prepare':prepare,'evaluate':evaluate}[a.phase]()
