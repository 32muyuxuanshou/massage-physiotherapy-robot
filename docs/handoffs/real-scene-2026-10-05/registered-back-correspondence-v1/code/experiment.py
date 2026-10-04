"""Known-identity real scan mechanism benchmark. Raw/derived geometry stays on server."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
import torch
from torch import nn
from inspect_data import load_off
from model import CoordinateField

ROOT=Path('/raid5/xuhd/datasets/registered_human_correspondence_20261005')
CONDITIONS=['FULL','PARTIAL_BAND','NOISY_PARTIAL']
MODES=['POINT_GLOBAL','PRIOR_GLOBAL','PRIOR_LOCAL']


def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())


def area(v,f):return np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1).sum()/2


def vertex_normals(v,f):
    n=np.zeros_like(v);fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    for k in range(3):np.add.at(n,f[:,k],fn)
    return n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)


def normals(x):
    idx=cKDTree(x).query(x,k=12)[1];nb=x[idx];nb-=nb.mean(1,keepdims=True)
    _,vec=np.linalg.eigh(np.einsum('nki,nkj->nij',nb,nb));n=vec[:,:,0]
    return n*np.where(n[:,2:3]>0,-1,1)


def pack(x,template):
    prior=template[cKDTree(template).query(x)[1]]
    return np.column_stack([x,normals(x),prior,x-prior]).astype(np.float32)


def prepare():
    start=time.monotonic();(ROOT/'cases').mkdir(exist_ok=True)
    rows=read(ROOT/'DATA_INVENTORY.json')['meshes'];rows=[r for r in rows if r['dataset']=='faust']
    c,f=load_off(Path(rows[0]['mesh_path']));vts=np.loadtxt(rows[0]['vts_path'],dtype=int)-1
    samples=c[vts];n=vertex_normals(c,f)[vts]
    roi=(samples[:,1]>.10)&(samples[:,1]<.42)&(np.abs(samples[:,0])<.18)&(samples[:,2]<-.02)&(n[:,2]<-.3)
    reference_ids=np.flatnonzero(roi);template=(samples[roi]-c.mean(0))/np.sqrt(area(c,f))
    assert len(template)>50
    xs=np.linspace(*np.quantile(template[:,0],[.2,.8]),3);ys=np.linspace(*np.quantile(template[:,1],[.1,.9]),9)
    grid=np.array([[x,y] for y in ys for x in xs]);query=np.unique(cKDTree(template[:,:2]).query(grid)[1])
    np.savez_compressed(ROOT/'TEMPLATE.npz',canonical_xyz=template,reference_ids=reference_ids,query_local_ids=query)
    manifest=[]
    for r in rows:
        number=int(r['name'].split('_')[-1]);role='train' if number<60 else 'dev' if number<80 else 'test'
        assert sha(Path(r['mesh_path']))==r['mesh_sha256'] and sha(Path(r['vts_path']))==r['vts_sha256']
        v,f=load_off(Path(r['mesh_path']));index=np.loadtxt(r['vts_path'],dtype=int)-1
        x=(v[index[roi]]-v.mean(0))/np.sqrt(area(v,f))
        for condition in CONDITIONS:
            for seed in range(3):
                rng=np.random.default_rng(number*100+seed);ids=np.arange(len(x))
                if condition!='FULL':
                    lo,hi=np.quantile(x[:,1],[.05,.95]);center=rng.uniform(lo+.1*(hi-lo),hi-.1*(hi-lo))
                    ids=ids[np.abs(x[:,1]-center)>.1*(hi-lo)]
                observed=x[ids].copy()
                if condition=='NOISY_PARTIAL':observed+=rng.normal(0,.002,observed.shape)
                assert len(ids)>=24
                data=pack(observed,template);path=ROOT/'cases'/f'{r["name"]}_{condition}_{seed}.npz'
                np.savez_compressed(path,features=data,canonical_gt=template[ids].astype(np.float32),
                                    true_surface_xyz=x[ids],source_vertex_idx=index[roi][ids],local_reference_idx=ids)
                manifest.append(dict(name=r['name'],role=role,condition=condition,seed=seed,path=str(path),
                                     sha256=sha(path),points=len(ids),queries_visible=int(np.isin(query,ids).sum())))
    write(ROOT/'CASE_MANIFEST.json',manifest)
    cfg=dict(steps=1200,batch=8,points=256,lr=.001,huber_beta=.02,dev_every=200,model_seeds=[0,1,2],modes=MODES,
             conditions=CONDITIONS,normalization='centered full-mesh / sqrt(full-mesh area)',
             metric_unit='percent template sqrt-area, NOT mm or geodesic distance',back_points=len(template),engineering_queries=len(query),
             source_roles=dict(train=60,dev=20,test=20),clinical_validated=False,real_sensor=False)
    write(ROOT/'CONFIG.json',cfg)
    frozen=[ROOT/'PROTOCOL.md',ROOT/'CONFIG.json',ROOT/'TEMPLATE.npz',ROOT/'CASE_MANIFEST.json',
            *sorted((ROOT/'code').glob('*.py')), *[Path(r['path']) for r in manifest]]
    write(ROOT/'SOURCE_FREEZE.json',[dict(path=str(p),sha256=sha(p)) for p in frozen])
    write(ROOT/'PREPARATION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,cases=len(manifest),**cfg))
    print('PREPARED',len(template),len(query),len(manifest),round(time.monotonic()-start,2),flush=True)


def rotation(rng):
    a,b=rng.uniform(-np.pi/18,np.pi/18,2)
    z=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1]])
    xx=np.array([[1,0,0],[0,np.cos(b),-np.sin(b)],[0,np.sin(b),np.cos(b)]])
    return xx@z


def augment(case,rng,template,n):
    x=case['features'][:,:3]@rotation(rng).T
    feat=pack(x,template);ids=rng.choice(len(x),n,replace=len(x)<n)
    return feat[ids],case['canonical_gt'][ids]


def train():
    cfg=read(ROOT/'CONFIG.json');manifest=read(ROOT/'CASE_MANIFEST.json');torch.set_num_threads(4)
    for r in read(ROOT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    data={r['path']:dict(np.load(r['path'])) for r in manifest if r['role']!='test'}
    training=[r for r in manifest if r['role']=='train'];dev=[r for r in manifest if r['role']=='dev']
    template=np.load(ROOT/'TEMPLATE.npz')['canonical_xyz'];loss=nn.SmoothL1Loss(beta=cfg['huber_beta']);ledger=[];start=time.monotonic()
    (ROOT/'checkpoints').mkdir(exist_ok=True)
    for mode in MODES:
        for seed in cfg['model_seeds']:
            torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);rng=np.random.default_rng(seed)
            model=CoordinateField(mode).cuda();opt=torch.optim.Adam(model.parameters(),lr=cfg['lr']);best=float('inf');history=[];t=time.monotonic()
            for step in range(1,cfg['steps']+1):
                batch=[augment(data[training[i]['path']],rng,template,cfg['points']) for i in rng.integers(len(training),size=cfg['batch'])]
                x=torch.tensor(np.stack([r[0] for r in batch]),device='cuda');y=torch.tensor(np.stack([r[1] for r in batch]),device='cuda')
                model.train();opt.zero_grad();value=loss(model(x),y);value.backward();opt.step()
                if step%cfg['dev_every']==0:
                    model.eval();errors=[]
                    with torch.no_grad():
                        for r in dev:
                            z=data[r['path']];q=model(torch.tensor(z['features'][None],device='cuda'))[0].cpu().numpy()
                            errors.append(float(np.median(np.linalg.norm(q-z['canonical_gt'],axis=1))*100))
                    score=float(np.mean(errors));history.append(dict(step=step,train_loss=float(value.item()),dev_source_case_mean_median_percent=score))
                    if score<best:
                        best=score;best_step=step;torch.save(dict(state_dict=model.state_dict(),mode=mode,seed=seed,step=step),ROOT/'checkpoints'/f'{mode}_{seed}.pt')
                    print('TRAIN',mode,seed,step,round(score,3),round(time.monotonic()-t,1),flush=True)
            path=ROOT/'checkpoints'/f'{mode}_{seed}.pt'
            ledger.append(dict(mode=mode,seed=seed,parameters=sum(p.numel() for p in model.parameters()),checkpoint_path=str(path),checkpoint_sha256=sha(path),
                               best_dev=best,best_step=best_step,steps=cfg['steps'],seconds=time.monotonic()-t,history=history))
            write(ROOT/'TRAINING_LEDGER.json',dict(status='RUNNING',runs=ledger,seconds=time.monotonic()-start))
    write(ROOT/'TRAINING_LEDGER.json',dict(status='COMPLETE',runs=ledger,seconds=time.monotonic()-start));print('TRAINING_COMPLETE',round(time.monotonic()-start,2),flush=True)


def evaluate():
    start=time.monotonic();cfg=read(ROOT/'CONFIG.json');manifest=[r for r in read(ROOT/'CASE_MANIFEST.json') if r['role']=='test'];torch.set_num_threads(4)
    with np.load(ROOT/'TEMPLATE.npz') as z:template=z['canonical_xyz'];query=z['query_local_ids']
    models=[('TEMPLATE_NN',-1,None,None)]
    for r in read(ROOT/'TRAINING_LEDGER.json')['runs']:
        assert sha(Path(r['checkpoint_path']))==r['checkpoint_sha256']
        model=CoordinateField(r['mode']).cuda();model.load_state_dict(torch.load(r['checkpoint_path'],weights_only=True)['state_dict']);model.eval()
        models.append((r['mode'],r['seed'],model,r['checkpoint_sha256']))
    rows=[];(ROOT/'predictions').mkdir(exist_ok=True)
    for r in manifest:
        with np.load(r['path']) as z:features=z['features'];gt=z['canonical_gt'];ids=z['local_reference_idx'];surface=z['true_surface_xyz']
        visible=np.isin(query,ids);visible_query=query[visible];true_index=np.array([np.flatnonzero(ids==q)[0] for q in visible_query])
        for mode,seed,model,ckpt in models:
            with torch.no_grad():q=features[:,6:9].copy() if model is None else model(torch.tensor(features[None],device='cuda'))[0].cpu().numpy()
            error=np.linalg.norm(q-gt,axis=1)*100;retrieved=cKDTree(q).query(template[visible_query])[1]
            qe=np.linalg.norm(template[ids[retrieved]]-template[visible_query],axis=1)*100
            se=np.linalg.norm(surface[retrieved]-surface[true_index],axis=1)*100
            path=ROOT/'predictions'/f'{r["name"]}_{r["condition"]}_{r["seed"]}_{mode}_{seed}.npz'
            np.savez_compressed(path,predicted_canonical=q,canonical_gt=gt,local_reference_idx=ids,canonical_errors_percent=error,
                                query_canonical_errors_percent=qe,query_surface_errors_percent=se,query_reference_idx=visible_query,retrieved_observed_idx=retrieved)
            rows.append(dict(name=r['name'],condition=r['condition'],input_seed=r['seed'],mode=mode,model_seed=seed,points=len(error),
                canonical_median_percent=float(np.median(error)),canonical_p95_percent=float(np.quantile(error,.95)),
                visible_query_median_percent=float(np.median(qe)),visible_query_p95_percent=float(np.quantile(qe,.95)),
                visible_surface_query_median_percent=float(np.median(se)),query_visible_fraction=float(visible.mean()),
                prediction_path=str(path),prediction_sha256=sha(path),checkpoint_sha256=ckpt,case_sha256=r['sha256']))
        if r['condition']=='NOISY_PARTIAL' and r['seed']==2:print('EVAL_SOURCE',r['name'],flush=True)
    metrics=['canonical_median_percent','canonical_p95_percent','visible_query_median_percent','visible_query_p95_percent','visible_surface_query_median_percent','query_visible_fraction']
    per_case=[];per_source=[];aggregate=[]
    for name in sorted({r['name'] for r in rows}):
        for condition in CONDITIONS:
            for mode in ['TEMPLATE_NN']+MODES:
                for seed in range(3):
                    group=[r for r in rows if (r['name'],r['condition'],r['mode'],r['input_seed'])==(name,condition,mode,seed)]
                    per_case.append(dict(name=name,condition=condition,mode=mode,input_seed=seed,**{k:float(np.mean([r[k] for r in group])) for k in metrics}))
                group=[r for r in per_case if (r['name'],r['condition'],r['mode'])==(name,condition,mode)]
                per_source.append(dict(name=name,condition=condition,mode=mode,**{k:float(np.mean([r[k] for r in group])) for k in metrics}))
    for condition in CONDITIONS:
        for mode in ['TEMPLATE_NN']+MODES:
            group=[r for r in per_source if (r['condition'],r['mode'])==(condition,mode)]
            aggregate.append(dict(condition=condition,mode=mode,sources=len(group),**{k:float(np.median([r[k] for r in group])) for k in metrics}))
    write(ROOT/'RESULTS.json',dict(status='COMPLETE',metric_unit=cfg['metric_unit'],aggregate=aggregate,per_source=per_source,per_case=per_case,raw_evaluation=rows,
        clinical_validated=False,known_patient_identity=False,oracle_posterior_roi=True,complete_geometry_normalization=True,real_depth_test=False))
    for r in read(ROOT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    write(ROOT/'EVALUATION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,cases=len(manifest),model_evaluations=len(rows),source_unchanged=True))
    print('EVAL_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','train','evaluate'],required=True);a=p.parse_args()
    {'prepare':prepare,'train':train,'evaluate':evaluate}[a.phase]()
