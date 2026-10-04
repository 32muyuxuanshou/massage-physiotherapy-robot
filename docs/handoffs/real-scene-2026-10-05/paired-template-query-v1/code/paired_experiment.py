"""Real registered scan, portable-template query experiment with independent SCAPE space."""
import argparse,sys,time
from pathlib import Path
sys.path.insert(0,'/raid5/xuhd/datasets/registered_human_correspondence_20261005/code')
import numpy as np
import torch
from scipy.spatial import cKDTree
from experiment import ROOT,read,write,sha,area,vertex_normals,normals,rotation
from inspect_data import load_off
from pair_model import PairedQuery
OUT=ROOT/'paired_query_v1';MODES=['PAIR_GLOBAL','PAIR_LOCAL'];CONDITIONS=['FULL','PARTIAL_BAND','NOISY_PARTIAL']
SCAPE_ROT=np.array([[0,0,-1],[0,1,0],[1,0,0]])


def prepare():
    start=time.monotonic();OUT.mkdir(exist_ok=True);(OUT/'scape_cases').mkdir(exist_ok=True)
    old=read(ROOT/'CASE_MANIFEST.json');faust=[dict(r,dataset='faust',role='consumed_test' if r['role']=='test' else r['role']) for r in old]
    z=dict(np.load(ROOT/'TEMPLATE.npz'));source0=next(r for r in old if r['name']=='tr_reg_000' and r['condition']=='FULL' and r['seed']==0)
    with np.load(source0['path']) as d:feat=d['features'][:,:6];ids=d['local_reference_idx']
    np.savez_compressed(OUT/'faust_template.npz',features=feat,canonical_xyz=z['canonical_xyz'],query_local_ids=z['query_local_ids'],local_reference_idx=ids)
    inventory=[r for r in read(ROOT/'DATA_INVENTORY.json')['meshes'] if r['dataset']=='scape'];rows=[]
    v,f=load_off(Path(inventory[0]['mesh_path']));v=v@SCAPE_ROT.T;vts=np.loadtxt(inventory[0]['vts_path'],dtype=int)-1
    samples=v[vts];n=vertex_normals(v,f)[vts]
    roi=(samples[:,1]>.1)&(samples[:,1]<.42)&(np.abs(samples[:,0])<.18)&(samples[:,2]<-.02)&(n[:,2]<-.3)
    template=(samples[roi]-v.mean(0))/np.sqrt(area(v,f));assert len(template)>50
    grid=np.array([[x,y] for y in np.linspace(*np.quantile(template[:,1],[.1,.9]),9) for x in np.linspace(*np.quantile(template[:,0],[.2,.8]),3)])
    query=np.unique(cKDTree(template[:,:2]).query(grid)[1]);tf=np.column_stack([template,normals(template)]).astype(np.float32)
    np.savez_compressed(OUT/'scape_template.npz',features=tf,canonical_xyz=template,query_local_ids=query,local_reference_idx=np.arange(len(template)))
    for r in inventory:
        number=int(r['name'][4:])
        if number<51:continue
        v,f=load_off(Path(r['mesh_path']));v=v@SCAPE_ROT.T;vts=np.loadtxt(r['vts_path'],dtype=int)-1
        x=(v[vts[roi]]-v.mean(0))/np.sqrt(area(v,f))
        for condition in CONDITIONS:
            for seed in range(3):
                rng=np.random.default_rng(number*100+seed);ids=np.arange(len(x))
                if condition!='FULL':
                    lo,hi=np.quantile(x[:,1],[.05,.95]);center=rng.uniform(lo+.1*(hi-lo),hi-.1*(hi-lo));ids=ids[np.abs(x[:,1]-center)>.1*(hi-lo)]
                p=x[ids].copy()
                if condition=='NOISY_PARTIAL':p+=rng.normal(0,.002,p.shape)
                features=np.column_stack([p,normals(p)]).astype(np.float32);path=OUT/'scape_cases'/f'{r["name"]}_{condition}_{seed}.npz'
                np.savez_compressed(path,features=features,canonical_gt=template[ids].astype(np.float32),true_surface_xyz=x[ids],local_reference_idx=ids,source_vertex_idx=vts[roi][ids])
                rows.append(dict(dataset='scape',name=r['name'],role='fresh_cross_dataset_poses',condition=condition,seed=seed,path=str(path),sha256=sha(path),points=len(ids)))
    manifest=faust+rows;write(OUT/'CASE_MANIFEST.json',manifest)
    cfg=dict(steps=1200,batch=8,points=256,queries=24,soft_sigma=.01,lr=.001,modes=MODES,model_seeds=[0,1,2],
             faust_source_roles=dict(train=60,dev=20,consumed_test=20),scape_test_poses=20,scape_template_points=len(template),scape_queries=len(query),
             scape_rotation=SCAPE_ROT.tolist(),metric_unit='percent respective template sqrt-area, NOT mm',clinical_validated=False)
    write(OUT/'CONFIG.json',cfg)
    frozen=[OUT/'PROTOCOL.md',OUT/'CONFIG.json',OUT/'CASE_MANIFEST.json',OUT/'faust_template.npz',OUT/'scape_template.npz',
            ROOT/'code/experiment.py',ROOT/'code/inspect_data.py',*[p for p in (OUT/'code').glob('*.py')],*[Path(r['path']) for r in manifest]]
    write(OUT/'SOURCE_FREEZE.json',[dict(path=str(p),sha256=sha(p)) for p in frozen])
    write(OUT/'PREPARATION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,new_scape_cases=len(rows),faust_cases=len(faust),**cfg))
    print('PAIR_PREPARED',len(template),len(query),len(manifest),round(time.monotonic()-start,2),flush=True)


def sample_target(z,rng):
    x=z['features'][:,:3]@rotation(rng).T;feat=np.column_stack([x,normals(x)]).astype(np.float32)
    ids=rng.choice(len(x),256,replace=len(x)<256)
    return feat[ids],z['canonical_gt'][ids]


def dev_score(model,dev,data,template):
    source=torch.tensor(template['features'][None],device='cuda');queries=template['query_local_ids'];qi=torch.tensor(queries[None],device='cuda')
    truth=template['canonical_xyz'];scores=[];model.eval()
    with torch.no_grad():
        for r in dev:
            z=data[r['path']];chosen=model(source,torch.tensor(z['features'][None,:,:6],device='cuda'),qi)[0].argmax(-1).cpu().numpy()
            visible=np.isin(queries,z['local_reference_idx']);ids=z['local_reference_idx'][chosen[visible]]
            scores.append(np.median(np.linalg.norm(truth[ids]-truth[queries[visible]],axis=1))*100)
    return float(np.mean(scores))


def train():
    torch.set_num_threads(4)
    for r in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    manifest=read(OUT/'CASE_MANIFEST.json');training=[r for r in manifest if r['role']=='train'];dev=[r for r in manifest if r['role']=='dev']
    sources=[r for r in training if r['condition']=='FULL' and r['seed']==0];data={r['path']:dict(np.load(r['path'])) for r in training+dev};template=dict(np.load(OUT/'faust_template.npz'))
    ledger=[];start=time.monotonic();(OUT/'checkpoints').mkdir(exist_ok=True)
    for mode in MODES:
        for seed in range(3):
            torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);rng=np.random.default_rng(seed);m=PairedQuery(mode).cuda();opt=torch.optim.Adam(m.parameters(),lr=.001)
            history=[];best=float('inf');t=time.monotonic()
            for step in range(1,1201):
                src=[];tar=[];qtruth=[];tgtruth=[]
                for si,ti in zip(rng.integers(len(sources),size=8),rng.integers(len(training),size=8)):
                    tx,ty=sample_target(data[training[ti]['path']],rng);qtarget=ty[rng.integers(256,size=24)]
                    s=data[sources[si]['path']];sq=cKDTree(s['canonical_gt']).query(qtarget)[1]
                    sx=s['features'][:,:3]@rotation(rng).T;sf=np.column_stack([sx,normals(sx)]).astype(np.float32)
                    selected=np.concatenate([sq,rng.choice(len(sx),232,replace=False)])
                    src.append(sf[selected]);tar.append(tx);qtruth.append(s['canonical_gt'][sq]);tgtruth.append(ty)
                source=torch.tensor(np.stack(src),device='cuda');target=torch.tensor(np.stack(tar),device='cuda');qi=torch.arange(24,device='cuda')[None].expand(8,-1)
                yq=torch.tensor(np.stack(qtruth),device='cuda');yt=torch.tensor(np.stack(tgtruth),device='cuda')
                wanted=torch.softmax(-torch.cdist(yq,yt)**2/(2*.01**2),-1)
                m.train();opt.zero_grad();logits=m(source,target,qi);loss=-(wanted*torch.log_softmax(logits,-1)).sum(-1).mean();loss.backward();opt.step()
                if step%200==0:
                    score=dev_score(m,dev,data,template);history.append(dict(step=step,loss=float(loss.item()),dev_query_median_percent=score))
                    if score<best:
                        best=score;best_step=step;torch.save(dict(state_dict=m.state_dict(),mode=mode,seed=seed,step=step),OUT/'checkpoints'/f'{mode}_{seed}.pt')
                    print('PAIR_TRAIN',mode,seed,step,round(score,3),round(time.monotonic()-t,1),flush=True)
            cp=OUT/'checkpoints'/f'{mode}_{seed}.pt';ledger.append(dict(mode=mode,seed=seed,parameters=sum(p.numel() for p in m.parameters()),best_dev=best,best_step=best_step,
                checkpoint_path=str(cp),checkpoint_sha256=sha(cp),seconds=time.monotonic()-t,history=history))
            write(OUT/'TRAINING_LEDGER.json',dict(status='RUNNING',runs=ledger,seconds=time.monotonic()-start))
    write(OUT/'TRAINING_LEDGER.json',dict(status='COMPLETE',runs=ledger,seconds=time.monotonic()-start));print('PAIR_TRAIN_COMPLETE',round(time.monotonic()-start,2),flush=True)


def evaluate():
    torch.set_num_threads(4);start=time.monotonic();manifest=[r for r in read(OUT/'CASE_MANIFEST.json') if r['role'] not in ['train','dev']]
    templates={d:dict(np.load(OUT/(d+'_template.npz'))) for d in ['faust','scape']};models=[('PAIRED_NN',-1,None)]
    for r in read(OUT/'TRAINING_LEDGER.json')['runs']:
        assert sha(Path(r['checkpoint_path']))==r['checkpoint_sha256'];m=PairedQuery(r['mode']).cuda();m.load_state_dict(torch.load(r['checkpoint_path'],weights_only=True)['state_dict']);m.eval();models.append((r['mode'],r['seed'],m))
    inventory={(r['dataset'],r['name']):r for r in read(ROOT/'DATA_INVENTORY.json')['meshes']};bindings={}
    for d,name in {(r['dataset'],r['name']) for r in manifest}:
        v,f=load_off(Path(inventory[(d,name)]['mesh_path']));first=np.full(len(v),-1,int);corner=np.zeros(len(v),int)
        for j in range(3):first[f[:,j]]=np.arange(len(f));corner[f[:,j]]=j
        bindings[(d,name)]=(first,corner)
    (OUT/'predictions').mkdir(exist_ok=True);rows=[]
    for r in manifest:
        d=r['dataset'];t=templates[d];queries=t['query_local_ids'];source=torch.tensor(t['features'][None],device='cuda');qi=torch.tensor(queries[None],device='cuda')
        with np.load(r['path']) as z:feat=z['features'][:,:6];ids=z['local_reference_idx'];surface=z['true_surface_xyz'];vertex=z['source_vertex_idx']
        visible=np.isin(queries,ids);visible_query=queries[visible];true_idx=np.array([np.flatnonzero(ids==j)[0] for j in visible_query])
        for mode,seed,m in models:
            with torch.no_grad():chosen=cKDTree(feat[:,:3]).query(t['features'][queries,:3])[1] if m is None else m(source,torch.tensor(feat[None],device='cuda'),qi)[0].argmax(-1).cpu().numpy()
            qe=np.linalg.norm(t['canonical_xyz'][ids[chosen[visible]]]-t['canonical_xyz'][visible_query],axis=1)*100
            se=np.linalg.norm(surface[chosen[visible]]-surface[true_idx],axis=1)*100
            path=OUT/'predictions'/f'{d}_{r["name"]}_{r["condition"]}_{r["seed"]}_{mode}_{seed}.npz'
            face,corner=bindings[(d,r['name'])];face_id=face[vertex[chosen]];bary=np.eye(3)[corner[vertex[chosen]]];assert np.all(face_id>=0)
            np.savez_compressed(path,all_query_reference_idx=queries,all_retrieved_observed_idx=chosen,query_visible_mask=visible,
                                all_source_vertex_idx=vertex[chosen],all_face_id=face_id,all_barycentric=bary,
                                query_canonical_errors_percent=qe,query_surface_errors_percent=se)
            rows.append(dict(dataset=d,name=r['name'],role=r['role'],condition=r['condition'],input_seed=r['seed'],mode=mode,model_seed=seed,
                visible_query_median_percent=float(np.median(qe)),visible_query_p95_percent=float(np.quantile(qe,.95)),visible_surface_query_median_percent=float(np.median(se)),
                query_visible_fraction=float(visible.mean()),prediction_path=str(path),prediction_sha256=sha(path),case_sha256=r['sha256'],
                observed_mesh_path=inventory[(d,r['name'])]['mesh_path'],observed_mesh_sha256=inventory[(d,r['name'])]['mesh_sha256'],binding_domain='author scan, NOT predicted MHR'))
        if r['condition']=='NOISY_PARTIAL' and r['seed']==2:print('PAIR_EVAL_SOURCE',d,r['name'],flush=True)
    per_source=[];aggregate=[];metrics=['visible_query_median_percent','visible_query_p95_percent','visible_surface_query_median_percent','query_visible_fraction']
    for d in ['faust','scape']:
        for name in sorted({r['name'] for r in rows if r['dataset']==d}):
            for condition in CONDITIONS:
                for mode in ['PAIRED_NN']+MODES:
                    group=[r for r in rows if (r['dataset'],r['name'],r['condition'],r['mode'])==(d,name,condition,mode)]
                    per_source.append(dict(dataset=d,name=name,condition=condition,mode=mode,**{k:float(np.mean([r[k] for r in group])) for k in metrics}))
        for condition in CONDITIONS:
            for mode in ['PAIRED_NN']+MODES:
                group=[r for r in per_source if (r['dataset'],r['condition'],r['mode'])==(d,condition,mode)]
                aggregate.append(dict(dataset=d,condition=condition,mode=mode,sources=len(group),**{k:float(np.median([r[k] for r in group])) for k in metrics}))
    write(OUT/'RESULTS.json',dict(status='COMPLETE',aggregate=aggregate,per_source=per_source,raw_evaluation=rows,clinical_validated=False,source_template='arbitrary registered template geometry; no fixed FAUST canonical XYZ input',metric_unit='percent respective sqrt-area, NOT mm',score_visibility='GT for scoring only; model inferred all queries'))
    for r in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    write(OUT/'EVALUATION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,cases=len(manifest),model_evaluations=len(rows),source_unchanged=True));print('PAIR_EVAL_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','train','evaluate'],required=True);a=p.parse_args();{'prepare':prepare,'train':train,'evaluate':evaluate}[a.phase]()
