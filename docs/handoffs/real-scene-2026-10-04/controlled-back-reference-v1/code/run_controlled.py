"""Fixed 20-source controlled diagnosis, K0 optimization and K1/K2 evaluation."""
import sys,argparse,time
from pathlib import Path
import numpy as np,cv2,scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra
from common import ROOT,PREV,BASE,METHODS,CASES,read,write,sha,summary
sys.path[:0]=[str(BASE/'delivery/code'),str(PREV/'code')]
from geometry import camera,local,world,raster_samples,probe,K,H,W
from l1_fit import vertex_normals,edges,fit_rigid,fit_displacement,mesh_quality
from normal_d import fit_normal
from surface_metrics import point_to_triangle_distances
from metrics_v2 import ray_depth_residual

def selected(n,cap):return np.arange(0,n,max(1,int(np.ceil(n/cap))))

def prepare():
    ROOT.mkdir(exist_ok=True)
    old=read(PREV/'c_pressure_normal/EXECUTION_CONTRACT.json');atlas=read(PREV/'a_atlas/ENGINEERING_BACK_ATLAS_V2.json')
    ids=np.asarray(read(BASE/'delivery/POSTERIOR_FACE_MASK.json')['face_ids'],int)
    write(ROOT/'CONTRACT.json',dict(id='CONTROLLED_BACK_REFERENCE_V1',status='FROZEN_BEFORE_FITS',subjects=old['subjects'],dev=old['dev'],
        methods=METHODS,cases=CASES,D=old['D'],rigid=old['rigid'],camera_K=K.tolist(),image_hw=[H,W],
        centers_m=[[0,0,0],[.45,0,0],[-.45,0,0]],target_m=[0,0,2.4],noise_sigma_m=0,
        optimization_view='K0 only',evaluation_views=['K1','K2'],max_K0_points=40000,max_posterior_eval_points=1500,
        normal_amplitude_m=.012,tangent_amplitude_m=.020,geodesic_sigma_m=.15,
        rotation_rodrigues_deg=[2,-1,1],translation_m=[.015,-.010,.040],
        source_reference='recentered cached prediction; procedural geometry, not human GT',
        aggregation='camera median per case -> subject median within each injection class; dev and historical-validation roles separate',
        new_inferences=0,training_runs=0,independent_real_sensor=False))
    write(ROOT/'ATLAS.json',atlas);write(ROOT/'POSTERIOR_FACE_IDS.json',dict(face_ids=ids.tolist()))
    sources=[];prepared=[]
    for subject in old['subjects']:
        source=BASE/'run_v2/meshes'/subject/'seed_0/Official.npz';sources.append(dict(path=str(source),sha256=sha(source)))
        z=np.load(source);V=z['vertices_m'].astype(float);F=z['faces'];shift=np.array([0.,0,2.4])-V.mean(0);V=V+shift
        d=ROOT/'reference'/subject;d.mkdir(parents=True,exist_ok=True)
        E=edges(F);length=np.linalg.norm(V[E[:,0]]-V[E[:,1]],axis=1)
        graph=sp.coo_matrix((np.r_[length,length],(np.r_[E[:,0],E[:,1]],np.r_[E[:,1],E[:,0]])),shape=(len(V),len(V))).tocsr()
        rec=next(r for r in atlas['records'] if r['id']=='ENG_PAIR_2_POS_X');center=rec['vertex_ids'][int(np.argmax(rec['barycentric']))]
        dist=dijkstra(graph,directed=False,indices=center);field=np.exp(-.5*(dist/.15)**2)
        normals=vertex_normals(V,F);norm=np.linalg.norm(normals,axis=1,keepdims=True);normals=np.divide(normals,norm,out=np.zeros_like(normals),where=norm>0)
        p,_=probe(V,F,atlas['records']);axis=p[5]-p[4];axis/=np.linalg.norm(axis)
        tangent=axis-np.sum(normals*axis,axis=1)[:,None]*normals;length=np.linalg.norm(tangent,axis=1,keepdims=True)
        tangent=np.divide(tangent,length,out=np.zeros_like(tangent),where=length>1e-8)
        np.savez_compressed(d/'reference.npz',vertices_m=V,faces=F,recenter_translation_m=shift,
            normal_injection_m=.012*field[:,None]*normals,tangent_injection_m=.020*field[:,None]*tangent,
            geodesic_distance_m=dist,fixed_reference_normals=normals,source_geodesic_vertex=center)
        views=[]
        for k,C in enumerate([[0,0,0],[.45,0,0],[-.45,0,0]]):
            R,C=camera(C);obs=raster_samples(local(V,R,C),F)
            source_idx=selected(len(obs['points_m']),40000) if k==0 else np.array([],int)
            back_idx=np.flatnonzero(np.isin(obs['face_id'],ids));ev=back_idx[selected(len(back_idx),1500)]
            assert len(ev)>0 and (k!=0 or len(source_idx)>0)
            obs['points_world_m']=world(obs['points_m'],R,C)
            np.savez_compressed(d/f'K{k}.npz',**obs,R_world_to_camera=R,camera_center_world_m=C,K=K,
                optimization_idx=source_idx,posterior_eval_idx=ev)
            views.append(dict(camera=k,points=len(obs['points_m']),optimization_points=len(source_idx),posterior_eval_points=len(ev),
                generated_before_fit=True,sha256=sha(d/f'K{k}.npz')))
        prepared.append(dict(subject=subject,source_cache_sha256=sha(source),reference_sha256=sha(d/'reference.npz'),views=views))
        print('REFERENCE_PREPARED',subject,[(v['points'],v['posterior_eval_points']) for v in views],flush=True)
    for p in [BASE/'delivery/POSTERIOR_FACE_MASK.json',PREV/'a_atlas/ENGINEERING_BACK_ATLAS_V2.json',PREV/'code/normal_d.py']:
        sources.append(dict(path=str(p),sha256=sha(p)))
    for p in sorted((BASE/'delivery/code').glob('*.py')):sources.append(dict(path=str(p),sha256=sha(p)))
    for p in sorted((ROOT/'code').glob('*.py')):sources.append(dict(path=str(p),sha256=sha(p)))
    for p in [ROOT/'CONTRACT.json',ROOT/'ATLAS.json',ROOT/'POSTERIOR_FACE_IDS.json',ROOT/'PROTOCOL.md']:
        sources.append(dict(path=str(p),sha256=sha(p)))
    write(ROOT/'SOURCE_FREEZE.json',sources);write(ROOT/'REFERENCE_MANIFEST.json',prepared)
    print('PREPARE_COMPLETE',len(prepared),len(sources),flush=True)

def evaluate(subject,case,variants,F,truth,records):
    dest=ROOT/'runs'/subject/case;p0,n0=probe(truth,F,records);rows=[]
    cams={k:np.load(ROOT/'reference'/subject/f'K{k}.npz') for k in [1,2]}
    per={};common={}
    for k,z in cams.items():
        ev=z['posterior_eval_idx'];query=z['points_m'][ev];R=z['R_world_to_camera'];C=z['camera_center_world_m']
        for m,V in variants.items():
            camV=local(V,R,C);r,hit=ray_depth_residual(query,camV,F);per[k,m]=(r,hit)
        common[k]=np.logical_and.reduce([per[k,m][1] for m in METHODS])
    ids=np.asarray(read(ROOT/'POSTERIOR_FACE_IDS.json')['face_ids'],int)
    for m,V in variants.items():
        points,normals=probe(V,F,records);delta=points-p0;signed=np.sum(delta*n0,1);tangent=delta-signed[:,None]*n0
        p_error=np.linalg.norm(delta,axis=1);camera_rows=[]
        for k,z in cams.items():
            ev=z['posterior_eval_idx'];query=z['points_world_m'][ev];dist=point_to_triangle_distances(query,V,F[ids]);r,hit=per[k,m]
            np.savez_compressed(dest/f'{m}_K{k}_metrics.npz',evaluation_point_idx=ev,point_to_surface_m=dist,
                ray_z_residual_m=r,ray_hit=hit,common_ray_hit=common[k])
            camera_rows.append(dict(camera=k,posterior=summary(dist),ray=summary(np.abs(r[hit])),
                common_ray=summary(np.abs(r[common[k]])),hit_fraction=float(hit.mean()),common_hit_fraction=float(common[k].mean())))
        row=dict(subject=subject,case=case,method=m,cameras=camera_rows,known_probe_error=summary(p_error),
            probe_normal_error=summary(np.abs(signed)),probe_tangent_error=summary(np.linalg.norm(tangent,axis=1)),
            probe_ids=[r['id'] for r in records],probe_errors_mm=(p_error*1000).tolist(),
            probe_normal_angle_deg=np.degrees(np.arccos(np.clip(np.sum(n0*normals,1),-1,1))).tolist(),
            mesh_quality_against_reference=mesh_quality(truth,V,F),synthetic_reference_only=True)
        np.savez_compressed(dest/(m+'_probes.npz'),xyz_m=points,reference_xyz_m=p0,normals=normals,reference_normals=n0)
        rows.append(row)
    write(dest/'results.json',rows);return rows

def run_subject(subject):
    cfg=read(ROOT/'CONTRACT.json');records=read(ROOT/'ATLAS.json')['records']
    ref=np.load(ROOT/'reference'/subject/'reference.npz');V=ref['vertices_m'];F=ref['faces'];obs=np.load(ROOT/'reference'/subject/'K0.npz')
    cloud=obs['points_world_m'][obs['optimization_idx']];R0=cv2.Rodrigues(np.deg2rad(cfg['rotation_rodrigues_deg']))[0]
    center=V.mean(0);T=np.asarray(cfg['translation_m']);ledgers=[]
    for case in CASES:
        start=time.time();dest=ROOT/'runs'/subject/case;dest.mkdir(parents=True,exist_ok=False)
        inject=np.zeros_like(V) if case=='RIGID_ONLY' else ref['normal_injection_m' if case=='NORMAL_BUMP' else 'tangent_injection_m']
        initial=(V+inject-center)@R0.T+center+T
        R,t=fit_rigid(initial,F,cloud,K,iters=cfg['rigid']['iterations'],trim=cfg['rigid']['trim_fraction']);rigid=initial@R.T+t
        dc=cfg['D'];pars={k:dc[k] for k in ['lam','mu','tau','n0','irls','use_conf','use_robust']};pars['sigma']=dc['sigma_m']
        vector,dv,iv=fit_displacement(rigid,F,cloud,K,**pars)
        normal,dn,u,n,inorm=fit_normal(rigid,F,cloud,K,**pars)
        variants=dict(zip(METHODS,[initial,rigid,vector,normal]))
        for m,Wv in variants.items():
            extra={} if m in METHODS[:2] else dict(displacement_m=dv if m=='D_VECTOR' else dn)
            if m=='D_NORMAL':extra.update(normal_scalar_m=u,fixed_rigid_normals=n)
            np.savez_compressed(dest/(m+'.npz'),vertices_m=Wv,faces=F,rigid_R=R,rigid_t_m=t,
                global_injected_R=R0,global_injected_t_m=T,local_injected_displacement_m=inject,
                actual_K0_optimization_point_idx=obs['optimization_idx'],reference_vertices_m=V,**extra)
        rows=evaluate(subject,case,variants,F,V,records)
        record=dict(subject=subject,case=case,status='COMPLETE',seconds=time.time()-start,new_official_inferences=0,
            fits=dict(rigid=1,vector_D=1,normal_D=1),K0_points=len(cloud),heldout_camera_optimization_points=0,
            vector_solver=iv,normal_solver=inorm,output_meshes=[dict(method=m,sha256=sha(dest/(m+'.npz'))) for m in METHODS])
        write(dest/'ledger.json',record);ledgers.append(record)
        print('CASE_COMPLETE',subject,case,round(record['seconds'],1),'probe',[round(r['known_probe_error']['median_mm'],2) for r in rows],flush=True)
    write(ROOT/'ledger'/(subject+'.json'),ledgers);return subject

def execute(phase,workers):
    from concurrent.futures import ProcessPoolExecutor,as_completed
    cfg=read(ROOT/'CONTRACT.json');subjects=cfg['dev'] if phase=='dev' else [s for s in cfg['subjects'] if s not in cfg['dev']]
    for r in read(ROOT/'SOURCE_FREEZE.json'):assert sha(r['path'])==r['sha256'],r['path']
    for row in read(ROOT/'REFERENCE_MANIFEST.json'):
        if row['subject'] in subjects:
            d=ROOT/'reference'/row['subject'];assert sha(d/'reference.npz')==row['reference_sha256']
            for v in row['views']:assert sha(d/f"K{v['camera']}.npz")==v['sha256']
    if phase=='validation':assert read(ROOT/'DEV_GATE.json')['status']=='PASS'
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(run_subject,s) for s in subjects]):f.result()
    if phase=='dev':write(ROOT/'DEV_GATE.json',dict(status='PASS',cases=12,gate='finite results and cached known-reference data flow; no performance cutoff',parameters_changed=0))
    print('PHASE_COMPLETE',phase,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','dev','validation'],required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    prepare() if a.phase=='prepare' else execute(a.phase,a.workers)
