"""Reuse frozen shared inputs/splits and three meshes; fit only D_normal."""
import argparse,sys,shutil,time,os
from pathlib import Path
import numpy as np
from common import ROOT,BASE,OLD,METHODS,read,write,sha,token
sys.path.insert(0,str(BASE/'delivery/code'))
from cache_v2 import save_mesh,verify_cache,mesh_path
from normal_d import fit_normal
from evaluate_cache import evaluate_subject
from make_visuals import visualize_subject

OUT=ROOT/'c_pressure_normal'

def freeze():
    OUT.mkdir(exist_ok=True)
    old=read(BASE/'delivery/EXPERIMENT_CONTRACT.json')
    contract={**old,'id':'PRESSUREPOSE_NORMAL_CONSTRAINED_D_V2','methods':METHODS,
        'expected_rows':240,'new_fits':60,'new_official_inferences':0,
        'D_normal':'exact restriction of D vector quadratic to delta_i = u_i fixed_vertex_normal_i',
        'common_hit_methods':METHODS,'common_hit_scope_change':'four-method intersection, not the old five-method intersection',
        'original_contract_sha256':sha(BASE/'delivery/EXPERIMENT_CONTRACT.json'),
        'atlas_sha256':sha(ROOT/'a_atlas/ENGINEERING_BACK_ATLAS_V2.json'),
        'evaluation_note':'same-source spatial holdout under APPROXIMATE reconstructed camera; not independent sensor accuracy'}
    write(OUT/'EXECUTION_CONTRACT.json',contract)
    source=[]
    for s in old['subjects']:
        dest=OUT/'inputs'/s;dest.mkdir(parents=True,exist_ok=True)
        for name in ['input.npz',*[f'split_{i}.npz' for i in old['seeds']]]:
            p=BASE/'run_v2/inputs'/s/name
            target=dest/name
            if not target.exists():target.symlink_to(p)
            source.append(dict(path=str(p),sha256=sha(p)))
        for seed in old['seeds']:
            for m in METHODS[:3]:
                p=mesh_path(BASE/'run_v2',s,seed,m);verify_cache(p,BASE/'run_v2',s,seed)
                target=mesh_path(OUT,s,seed,m);target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(p,target);shutil.copy2(p.with_suffix('.json'),target.with_suffix('.json'))
                source.extend([dict(path=str(x),sha256=sha(x)) for x in [p,p.with_suffix('.json')]])
    for p in [BASE/'delivery/EXPERIMENT_CONTRACT.json',BASE/'delivery/POSTERIOR_FACE_MASK.json',
            BASE/'delivery/POSTERIOR_RGB_ROI.json',ROOT/'a_atlas/ENGINEERING_BACK_ATLAS_V2.json']:
        source.append(dict(path=str(p),sha256=sha(p)))
    for p in sorted((BASE/'delivery/code').glob('*.py')):source.append(dict(path=str(p),sha256=sha(p)))
    for name in ['normal_d.py','run_pressure_normal.py','common.py','test_normal_d.py']:
        p=ROOT/'code'/name;source.append(dict(path=str(p),sha256=sha(p)))
    source.append(dict(path=str(OUT/'EXECUTION_CONTRACT.json'),sha256=sha(OUT/'EXECUTION_CONTRACT.json')))
    write(OUT/'RUNTIME_SOURCE_FREEZE.json',source)
    print('PREPARE_NORMAL_PASS',len(source),flush=True)

def run_subject(s):
    cfg=read(OUT/'EXECUTION_CONTRACT.json');ledger=[]
    freeze=read(OUT/'RUNTIME_SOURCE_FREEZE.json')
    # Per-subject source verification; global post-check verifies the complete freeze.
    for r in freeze:
        p=Path(r['path'])
        if s in p.parts or p.suffix=='.py' or 'EXPERIMENT_CONTRACT' in p.name:
            assert sha(p)==r['sha256'],f'Frozen source changed: {p}'
    for seed in cfg['seeds']:
        start=time.time();inp=np.load(OUT/'inputs'/s/'input.npz');split=np.load(OUT/'inputs'/s/f'split_{seed}.npz')
        rp=mesh_path(OUT,s,seed,'Official+Rigid');verify_cache(rp,OUT,s,seed)
        z=np.load(rp);V=z['vertices_m'];F=z['faces'];idx=split['train_idx']
        dc=cfg['D'];assert dc['bed'] is None
        final,delta,u,n,info=fit_normal(V,F,inp['points_m'][idx],inp['K'],lam=dc['lam'],mu=dc['mu'],tau=dc['tau'],
            n0=dc['n0'],irls=dc['irls'],sigma=dc['sigma_m'],use_conf=dc['use_conf'],use_robust=dc['use_robust'])
        state={k[4:]:z[k] for k in z.files if k.startswith('mhr_')}
        p=save_mesh(OUT,s,seed,METHODS[-1],final,F,V,
            optimization=dict(config=dc,**info,input='same frozen train_idx as Rigid/D_vector',
                rigid_source_sha256=sha(rp),optimizer_source_sha256=sha(ROOT/'code/normal_d.py')),
            state=state,source_status='NEW_NORMAL_D_ONLY_FROM_FROZEN_RIGID',optimization_point_idx=idx,
            rigid_R=z['rigid_R'],rigid_t_m=z['rigid_t_m'],effective_cam_t_m=z['effective_cam_t_m'],
            displacement_m=delta,normal_scalar_m=u,fixed_vertex_normals=n)
        verify_cache(p,OUT,s,seed)
        ledger.append(dict(subject=s,seed=seed,new_fits=1,official_inferences=0,mesh_sha256=sha(p),
            fit_seconds=time.time()-start,train_count=len(idx),heldout_intersection=0,solver=info))
        write(OUT/'ledger'/(s+'.json'),dict(status='RUNNING',rows=ledger))
        print('NORMAL_FIT',s,seed,round(time.time()-start,1),flush=True)
    # Render and metrics only read cached final meshes, never fit.
    evaluate_subject(s,BASE/'delivery',OUT,METHODS,cfg['seeds'])
    visuals=visualize_subject(s,BASE/'delivery',OUT,METHODS,cfg['seeds'])
    rows=evaluate_subject(s,BASE/'delivery',OUT,METHODS,cfg['seeds'])
    assert len(rows)==12 and len(visuals)==12
    write(OUT/'ledger'/(s+'.json'),dict(status='COMPLETE',rows=ledger,method_evaluation_rows=12,
        cache_only_visuals=12,source_split_unchanged=True))
    print('SUBJECT_COMPLETE',s,flush=True)
    return s

def execute(phase,workers):
    from concurrent.futures import ProcessPoolExecutor,as_completed
    cfg=read(OUT/'EXECUTION_CONTRACT.json')
    subjects=cfg['dev'] if phase=='dev' else [s for s in cfg['subjects'] if s not in cfg['dev']]
    if phase=='validation':assert read(OUT/'DEV_STRUCTURAL_GATE.json')['status']=='PASS'
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(run_subject,s) for s in subjects]):f.result()
    if phase=='dev':
        ledgers=[read(OUT/'ledger'/(s+'.json')) for s in subjects]
        assert all(x['status']=='COMPLETE' for x in ledgers)
        assert sum(len(x['rows']) for x in ledgers)==12
        write(OUT/'DEV_STRUCTURAL_GATE.json',dict(status='PASS',new_fits=12,subjects=subjects,
            gate='finite scalar solves, vertex normal subspace, actual cache/split checks, cache-only renders/evaluation',
            performance_threshold_used=False,parameter_changes_after_dev=0,
            frozen_optimizer_sha256=sha(ROOT/'code/normal_d.py'),frozen_contract_sha256=sha(OUT/'EXECUTION_CONTRACT.json')))
    print('PHASE_COMPLETE',phase,flush=True)

def integrity():
    rows=read(OUT/'RUNTIME_SOURCE_FREEZE.json')
    for r in rows:assert sha(r['path'])==r['sha256'],r['path']
    cfg=read(OUT/'EXECUTION_CONTRACT.json');n=0
    for s in cfg['subjects']:
        for seed in cfg['seeds']:
            for m in METHODS:verify_cache(mesh_path(OUT,s,seed,m),OUT,s,seed);n+=1
    write(OUT/'POST_EXECUTION_INTEGRITY.json',dict(status='PASS',source_files_checked=len(rows),meshes_checked=n,
        previous_results_unchanged=True,optimizer_unchanged_since_dev_gate=True,medical_accuracy_validated=False))
    print('POST_INTEGRITY_PASS',n,flush=True)

if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','dev','validation','integrity'],required=True)
    p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    if a.phase=='prepare':freeze()
    elif a.phase=='integrity':integrity()
    else:execute(a.phase,a.workers)
