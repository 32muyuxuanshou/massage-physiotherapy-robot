"""Frozen selections -> raw meshes -> unchanged heldout evaluation, never fitting."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,json,sys,time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from core import WORK,G,sha


def jobs():
    frozen=json.loads((WORK/'SELECTION_FREEZE.json').read_text())
    assert frozen['status']=='FROZEN_BEFORE_ANY_REAL_EVAL'
    entries={};links=[]
    for r in frozen['records']:
        arm,seed=r['arm'],r['seed'];root=WORK/'runs'/('%s_s%d'%(arm,seed))
        for label,epoch in [('old_best',r['old_best_epoch']),('joint_best',r['joint_best_epoch']),('last',r['last_epoch'])]:
            path=root/('epoch_%02d.pt'%epoch);assert sha(path)==r['checkpoint_sha256'][str(epoch)]
            name=('parent_s%d_e00'%seed) if epoch==0 else '%s_s%d_e%02d'%(arm,seed,epoch)
            entries.setdefault(name,dict(name=name,seed=seed,epoch=epoch,arm=arm,checkpoint=str(path),checkpoint_sha256=sha(path)))
            links.append(dict(arm=arm,seed=seed,selection=label,epoch=epoch,job=name))
    # Parent is always present as a current-runtime control, independently of selection.
    for seed in [11,23,37]:
        name='parent_s%d_e00'%seed;path=WORK/'runs'/('E0_s%d'%seed)/'epoch_00.pt'
        entries.setdefault(name,dict(name=name,seed=seed,epoch=0,arm='E0',checkpoint=str(path),checkpoint_sha256=sha(path)))
    return list(entries.values()),links


def infer(seed):
    import torch
    from core import FineOnly,load_parent,batch,read_prepared
    from train218 import selected_rows
    from frozen_render_losses import MeshRenderer
    torch.set_num_threads(2);torch.backends.cuda.matmul.allow_tf32=False
    faces=torch.from_numpy(np.load(G/'assets/faces.npy')).cuda();renderer=MeshRenderer(faces)
    model=FineOnly(load_parent(seed,renderer)).eval();rr=selected_rows(seed)
    entries,links=jobs();source=[r for r in rr if r['domain'] in ['real','behave']]
    assert len(source)==502
    for job in [j for j in entries if j['seed']==seed]:
        out=WORK/'real_evaluation'/job['name'];out.mkdir(parents=True,exist_ok=True)
        if (out/'PREDICTIONS.json').exists():continue
        state=torch.load(job['checkpoint'],map_location='cpu',weights_only=False)
        assert state['seed']==seed;model.load_state_dict(state['model']);records=[]
        with torch.no_grad():
            for domain in ['real','behave']:
                rows=[r for r in source if r['domain']==domain]
                for start in range(0,len(rows),4):
                    rows_batch=rows[start:start+4];x=batch(rows_batch,seed);camera,delta=model(x)
                    vertices=x['body']+camera[:,None]
                    for i,r in enumerate(rows_batch):
                        path=out/(domain+'_'+r['key']+'.npz')
                        np.savez_compressed(path,camera_m=camera[i].cpu().numpy(),fine_delta_m=delta[i].cpu().numpy(),
                            coarse_camera_m=x['coarse'][i].cpu().numpy(),vertices_camera_A=vertices[i].cpu().numpy())
                        initial=read_prepared(str(WORK/'prepared'/('s%d'%seed)/domain/(r['key']+'.npz')))['initial_camera']
                        change=float(np.max(np.abs(initial-camera[i].cpu().numpy())))
                        if job['epoch']==0:assert change<1e-4,change
                        records.append(dict(domain=domain,key=r['key'],prediction=str(path),sha256=sha(path),parent_camera_max_abs_change_m=change))
        report=dict(status='COMPLETE',job=job,records=records,Camera_B_read=False,new_model_Txyz=False,selection_freeze_sha256=sha(WORK/'SELECTION_FREEZE.json'))
        (out/'PREDICTIONS.json').write_text(json.dumps(report,indent=2))
        print('RAW_PREDICTIONS_COMPLETE',job['name'],len(records),flush=True)
    (WORK/'REAL_EVALUATION_INDEX.json').write_text(json.dumps(dict(jobs=entries,links=links),indent=2))


FUNCTIONS=None
FACES=None
MAP_FACES=None
MAP_WEIGHTS=None


def initialize():
    global FUNCTIONS,FACES,MAP_FACES,MAP_WEIGHTS
    sys.path.insert(0,str(G/'historical_code'))
    from run_r41_txyz import dependencies
    FUNCTIONS=dependencies(G/'historical_code');FACES=np.load(G/'assets/faces.npy')
    with np.load(G/'assets/mhr2smpl_mapping.npz') as z:MAP_FACES=FACES[z['triangle_ids']];MAP_WEIGHTS=z['baryc_coords']


def load(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}


def stats(d):
    return dict(median_mm=float(np.median(d)),p95_mm=float(np.quantile(d,.95)),coverage_50mm=float(np.mean(d<=50)))


def evaluate_one(task):
    job,t=task;start=time.monotonic();path=WORK/'real_evaluation'/job['name']/(t['dataset']+'_'+t['key']+'.npz')
    z=load(path);vertices=z['vertices_camera_A'];source=load(G/t['input']);held=load(G/t['heldout'])
    result={k:t[k] for k in ['dataset','key','identity','role','sequence','frame']};distances={}
    if t['dataset']=='real':
        ca={k:source['A_'+k] for k in ['R','T']};cb={k:source['B_'+k] for k in ['R','T']}
        transformed=FUNCTIONS['transform_camera'](vertices,ca,cb)
        points=held['points_camera_B'];assert len(points)==2048
        distance=FUNCTIONS['distance'](points,transformed,FACES)*1000
        result['metrics']=stats(distance);distances['B_mm']=distance
        labels=load(G/t['regions'])['labels']
        result['regions']={name:stats(distance[labels==i]) for i,name in enumerate(['shoulder_upper_torso_proxy','middle_torso_proxy','waist_lower_torso_proxy','arms','legs','head','hands_feet']) if np.any(labels==i)}
        reference=t['original_final_evaluation']['triangle']
    else:
        reference_vertices=load(G/t['reference'])['vertices_camera_m'].astype(np.float64)
        mapped=np.einsum('nj,njk->nk',MAP_WEIGHTS,vertices.astype(np.float64)[MAP_FACES])
        result['pve_mm']=float(np.linalg.norm(mapped-reference_vertices,axis=1).mean()*1000)
        result['per_camera']={}
        for kid in [1,2,3]:
            transformed=(vertices@source['K0_R'].T+source['K0_t']-held['K%d_t'%kid])@held['K%d_R'%kid]
            distance=FUNCTIONS['distance'](held['K%d_points_m'%kid],transformed,FACES)*1000
            result['per_camera']['K%d'%kid]=stats(distance);distances['K%d_mm'%kid]=distance
        result['metrics']={k:float(np.mean([v[k] for v in result['per_camera'].values()])) for k in ['median_mm','p95_mm','coverage_50mm']}
        reference=t['original_final_evaluation']['frame_surface_camera_equal_mean']
    result.update(camera_m=z['camera_m'].tolist(),fine_delta_m=z['fine_delta_m'].tolist(),
        coarse_camera_m=z['coarse_camera_m'].tolist(),prediction_sha256=sha(path),seconds=time.monotonic()-start)
    if job['epoch']==0:
        old=load(G/t['prediction'])['vertices_camera_A']
        mesh_bound=float(np.linalg.norm(vertices.astype(np.float64)-old.astype(np.float64),axis=1).max()*1000)
        difference={k:abs(result['metrics'][k]-reference[k]) for k in ['median_mm','p95_mm']}
        assert max(difference.values())<=mesh_bound+.002,(t['key'],difference,mesh_bound)
        if t['dataset']=='behave':assert abs(result['pve_mm']-t['original_final_evaluation']['pve']['pve_absolute_mm'])<=mesh_bound+.002
        result['parent_reproduction']=dict(metric_difference_mm=difference,mesh_perturbation_bound_mm=mesh_bound,pass_within_bound=True)
    out=WORK/'real_evaluation'/job['name']/'metrics';out.mkdir(exist_ok=True)
    np.savez_compressed(out/(t['dataset']+'_'+t['key']+'.npz'),**distances)
    (out/(t['dataset']+'_'+t['key']+'.json')).write_text(json.dumps(result,indent=2))
    return result


def run_cpu(workers,pilot):
    entries,links=jobs();tasks=json.loads((G/'MANIFEST.json').read_text())['tasks'];todo=[]
    for job in entries:
        if pilot and job['epoch']!=0:continue
        source=[t for t in tasks if t['seed']==job['seed'] and t['dataset'] in ['real','behave']]
        if pilot:
            source=[next(t for t in source if t['dataset']==d) for d in ['real','behave']]
            if job['seed']==11:
                source += [next(t for t in tasks if t['dataset']=='real' and t['seed']==11 and t['identity']==i) for i in ['p001195','p001196']]
        for t in source:
            path=WORK/'real_evaluation'/job['name']/'metrics'/(t['dataset']+'_'+t['key']+'.json')
            if not path.exists():todo.append((job,t))
    started=time.monotonic()
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize) as pool:
        for i,r in enumerate(pool.map(evaluate_one,todo,chunksize=1),1):
            if i%100==0 or i==len(todo):print('HELDOUT_EVAL',i,len(todo),round(time.monotonic()-started,1),flush=True)
    if pilot:
        (WORK/'REAL_EVALUATOR_PILOT.json').write_text(json.dumps(dict(status='PASS',newly_evaluated=len(todo),workers=workers,original_metrics_reproduced_within_mesh_numeric_bound=True),indent=2))
    else:
        counts={job['name']:len(list((WORK/'real_evaluation'/job['name']/'metrics').glob('*.json'))) for job in entries}
        assert all(v==502 for v in counts.values()),counts
        (WORK/'REAL_EVALUATION_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',jobs=counts,selection_links=links,seconds=time.monotonic()-started,Camera_B_fit=False),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['infer','evaluate'],required=True);p.add_argument('--seed',type=int);p.add_argument('--workers',type=int,default=12);p.add_argument('--pilot',action='store_true');a=p.parse_args()
    infer(a.seed) if a.stage=='infer' else run_cpu(a.workers,a.pilot)
