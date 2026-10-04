"""A new task-output stage; original coordinate-field training/results remain frozen."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree
from inspect_data import load_off
from experiment import ROOT,read,write,sha,augment
from query_model import QuerySurface
OUT=ROOT/'query_stage_v1'
MODES=['Q_GLOBAL','Q_PRIOR_LOCAL']


def train():
    OUT.mkdir(exist_ok=True);(OUT/'checkpoints').mkdir(exist_ok=True);cfg=read(ROOT/'CONFIG.json');torch.set_num_threads(4)
    for r in read(ROOT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    cases=read(ROOT/'CASE_MANIFEST.json');training=[r for r in cases if r['role']=='train'];dev=[r for r in cases if r['role']=='dev']
    data={r['path']:dict(np.load(r['path'])) for r in cases if r['role']!='test'}
    with np.load(ROOT/'TEMPLATE.npz') as z:template=z['canonical_xyz'];query_ids=z['query_local_ids']
    frozen=[ROOT/'QUERY_STAGE_SPEC.md',ROOT/'CASE_MANIFEST.json',ROOT/'TEMPLATE.npz',ROOT/'code/query_model.py',ROOT/'code/query_experiment.py',ROOT/'code/experiment.py']
    write(OUT/'SOURCE_FREEZE.json',[dict(path=str(p),sha256=sha(p)) for p in frozen])
    write(OUT/'CONFIG.json',dict(steps=1200,batch=8,points=256,queries_per_batch=24,soft_target_sigma=.01,lr=.001,
        model_seeds=[0,1,2],modes=MODES,test_role='consumed mechanism sources',clinical_validated=False))
    ledger=[];start=time.monotonic()
    for mode in MODES:
        for seed in range(3):
            torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);rng=np.random.default_rng(seed)
            model=QuerySurface(mode).cuda();opt=torch.optim.Adam(model.parameters(),lr=.001);history=[];best=float('inf');t=time.monotonic()
            for step in range(1,1201):
                b=[augment(data[training[i]['path']],rng,template,256) for i in rng.integers(len(training),size=8)]
                x=torch.tensor(np.stack([r[0] for r in b]),device='cuda');y=torch.tensor(np.stack([r[1] for r in b]),device='cuda')
                qi=rng.integers(256,size=(8,24));q=y[torch.arange(8,device='cuda')[:,None],torch.tensor(qi,device='cuda')]
                target=torch.softmax(-torch.cdist(q,y)**2/(2*.01**2),dim=-1)
                model.train();opt.zero_grad();logits=model(x,q);loss=-(target*torch.log_softmax(logits,dim=-1)).sum(-1).mean();loss.backward();opt.step()
                if step%200==0:
                    model.eval();errors=[]
                    with torch.no_grad():
                        for r in dev:
                            z=data[r['path']];visible_query=query_ids[np.isin(query_ids,z['local_reference_idx'])]
                            q=template[visible_query].astype(np.float32)
                            idx=model(torch.tensor(z['features'][None],device='cuda'),torch.tensor(q[None],device='cuda'))[0].argmax(-1).cpu().numpy()
                            errors.append(np.median(np.linalg.norm(z['canonical_gt'][idx]-q,axis=1))*100)
                    score=float(np.mean(errors));history.append(dict(step=step,train_loss=float(loss.item()),dev_query_median_percent=score))
                    if score<best:
                        best=score;best_step=step;torch.save(dict(state_dict=model.state_dict(),mode=mode,seed=seed,step=step),OUT/'checkpoints'/f'{mode}_{seed}.pt')
                    print('QUERY_TRAIN',mode,seed,step,round(score,3),round(time.monotonic()-t,1),flush=True)
            cp=OUT/'checkpoints'/f'{mode}_{seed}.pt';ledger.append(dict(mode=mode,seed=seed,best_dev=best,best_step=best_step,history=history,
                parameters=sum(p.numel() for p in model.parameters()),checkpoint_path=str(cp),checkpoint_sha256=sha(cp),seconds=time.monotonic()-t))
            write(OUT/'TRAINING_LEDGER.json',dict(status='RUNNING',runs=ledger,seconds=time.monotonic()-start))
    write(OUT/'TRAINING_LEDGER.json',dict(status='COMPLETE',runs=ledger,seconds=time.monotonic()-start));print('QUERY_TRAIN_COMPLETE',round(time.monotonic()-start,2),flush=True)


def evaluate():
    start=time.monotonic();torch.set_num_threads(4);cases=[r for r in read(ROOT/'CASE_MANIFEST.json') if r['role']=='test']
    with np.load(ROOT/'TEMPLATE.npz') as z:template=z['canonical_xyz'];query=z['query_local_ids']
    meshes={r['name']:r for r in read(ROOT/'DATA_INVENTORY.json')['meshes'] if r['dataset']=='faust'}
    bindings={}
    for name in {r['name'] for r in cases}:
        v,f=load_off(Path(meshes[name]['mesh_path']));first_face=np.full(len(v),-1,int);corner=np.zeros(len(v),int)
        for j in range(3):
            first_face[f[:,j]]=np.arange(len(f));corner[f[:,j]]=j
        bindings[name]=(first_face,corner)
    models=[]
    for r in read(OUT/'TRAINING_LEDGER.json')['runs']:
        assert sha(Path(r['checkpoint_path']))==r['checkpoint_sha256']
        m=QuerySurface(r['mode']).cuda();m.load_state_dict(torch.load(r['checkpoint_path'],weights_only=True)['state_dict']);m.eval();models.append((r,m))
    (OUT/'predictions').mkdir(exist_ok=True);rows=[]
    for r in cases:
        with np.load(r['path']) as z:feat=z['features'];ids=z['local_reference_idx'];surface=z['true_surface_xyz'];vertex=z['source_vertex_idx']
        visible=query[np.isin(query,ids)];q=template[visible].astype(np.float32);true_idx=np.array([np.flatnonzero(ids==j)[0] for j in visible])
        for model_row,m in models:
            with torch.no_grad():chosen=m(torch.tensor(feat[None],device='cuda'),torch.tensor(q[None],device='cuda'))[0].argmax(-1).cpu().numpy()
            qe=np.linalg.norm(template[ids[chosen]]-template[visible],axis=1)*100;se=np.linalg.norm(surface[chosen]-surface[true_idx],axis=1)*100
            face,corner=bindings[r['name']];face_id=face[vertex[chosen]];bary=np.eye(3)[corner[vertex[chosen]]];assert np.all(face_id>=0)
            path=OUT/'predictions'/f'{r["name"]}_{r["condition"]}_{r["seed"]}_{model_row["mode"]}_{model_row["seed"]}.npz'
            np.savez_compressed(path,retrieved_observed_idx=chosen,query_reference_idx=visible,source_vertex_idx=vertex[chosen],face_id=face_id,barycentric=bary,
                                query_canonical_errors_percent=qe,query_surface_errors_percent=se)
            rows.append(dict(name=r['name'],condition=r['condition'],input_seed=r['seed'],mode=model_row['mode'],model_seed=model_row['seed'],
                visible_query_median_percent=float(np.median(qe)),visible_query_p95_percent=float(np.quantile(qe,.95)),
                visible_surface_query_median_percent=float(np.median(se)),query_visible_fraction=len(visible)/len(query),
                prediction_path=str(path),prediction_sha256=sha(path),checkpoint_sha256=model_row['checkpoint_sha256'],binding_domain='author observed scan, NOT predicted MHR'))
    metrics=['visible_query_median_percent','visible_query_p95_percent','visible_surface_query_median_percent','query_visible_fraction'];per_source=[];aggregate=[]
    for name in sorted({r['name'] for r in rows}):
        for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
            for mode in MODES:
                # Equal three input perturbations and three model initializations.
                group=[r for r in rows if (r['name'],r['condition'],r['mode'])==(name,condition,mode)]
                per_source.append(dict(name=name,condition=condition,mode=mode,**{k:float(np.mean([r[k] for r in group])) for k in metrics}))
    for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
        for mode in MODES:
            group=[r for r in per_source if (r['condition'],r['mode'])==(condition,mode)]
            aggregate.append(dict(condition=condition,mode=mode,sources=len(group),**{k:float(np.median([r[k] for r in group])) for k in metrics}))
    write(OUT/'RESULTS.json',dict(status='COMPLETE',aggregate=aggregate,per_source=per_source,raw_evaluation=rows,
        metric_unit='percent sqrt-area, NOT mm',test_role='consumed mechanism sources',clinical_validated=False))
    for r in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    write(OUT/'EVALUATION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,cases=len(cases),model_evaluations=len(rows),source_unchanged=True))
    print('QUERY_EVAL_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['train','evaluate'],required=True);a=p.parse_args();{'train':train,'evaluate':evaluate}[a.phase]()
