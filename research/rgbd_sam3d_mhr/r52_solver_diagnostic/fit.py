"""Generate all A-only translations before any heldout evaluation."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,json,sys,time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from common import W,G,CFG,load,sha,tasks,key,dump
from solvers import nn_path,fixed_update,finish

FACES=FI=BC=QI=HIST=None


def initialize():
    global FACES,FI,BC,QI,HIST
    FACES=np.load(G/'assets/faces.npy')
    with np.load(G/'assets/anchors.npz') as z:FI=z['face_index'];BC=z['barycentric']
    QI=np.linspace(0,len(FI)-1,256,dtype=np.int64)
    sys.path.insert(0,str(G/'historical_code'))
    from run_r41_txyz import dependencies
    HIST=dependencies(G/'historical_code')['fit_txyz']


def one(t):
    tag=key(t);a=load(W/'inputs'/(tag+'.npz'));gold=load(G/t['prediction'])
    body=gold['body_m'];coarse=gold['coarse_camera'].reshape(3);fine=gold['camera_m'].reshape(3)
    original=gold.get('original_camera',np.asarray(t.get('original_camera'))).reshape(3).astype(np.float32)
    base_coarse=(body+coarse).astype(np.float64);base_official=(body+original).astype(np.float64)
    # These casts reproduce each original dataset's anchor computation.
    vertices=(body+coarse) if t['dataset']!='behave' else base_coarse
    anchors=(vertices[FACES[FI]]*BC[:,:,None]).sum(1)
    tri=vertices[FACES[FI]].astype(np.float64);normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    q=a['query_xyz'];obs=a['observed'];qn=a['query_normals'];points=a['points']
    anchor_numeric=float(np.max(np.linalg.norm(anchors[QI]-q,axis=1)))
    assert anchor_numeric<2e-6,(tag,anchor_numeric)
    results={}
    def add(name,raw,trace,start=coarse):
        applied,fallback=finish(raw)
        results[name]=dict(camera_m=(start+applied).tolist(),raw_delta_m=raw.tolist(),applied_delta_m=applied.tolist(),
            displacement_from_official_m=(start+applied-original).tolist(),fallback=fallback,trace=trace)
    for name,cam in [('coarse',coarse),('fine',fine)]:
        results[name]=dict(camera_m=cam.tolist(),raw_delta_m=(cam-coarse).tolist(),applied_delta_m=(cam-coarse).tolist(),
            displacement_from_official_m=(cam-original).tolist(),fallback=False,trace=[])
    official_vertices=(body+original) if t['dataset']!='behave' else base_official
    off_anchor=(official_vertices[FACES[FI]]*BC[:,:,None]).sum(1)
    raw,applied,trace,fallback=HIST(points,off_anchor);add('official_hist6',raw,trace,original)
    official_reproduction=None
    if t['dataset']!='native':
        ref=t['baseline'] if t['dataset']=='real' else t['baseline']['txyz']
        old_raw=np.asarray(ref['raw_translation_m' if t['dataset']=='real' else 'raw_m'])
        old_applied=np.asarray(ref['applied_translation_m' if t['dataset']=='real' else 'applied_m'])
        difference=max(float(np.max(abs(raw-old_raw))),float(np.max(abs(applied-old_applied))))
        assert difference<1e-6 and fallback==ref['fallback'],(tag,'HISTORICAL_TXYZ_MISMATCH',difference)
        official_reproduction=dict(max_translation_difference_m=difference,fallback_equal=True)
    raw,applied,trace,fallback=HIST(points,anchors)
    for n in [1,2,3,6]:add('hist_med%d'%n,np.asarray(trace[n-1]['raw_t_m']),trace[:n])
    for name,an,no,direction,kind in [
        ('all256_o2m_med6',anchors[QI],normals[QI],'o2m','median'),
        ('vis256_o2m_med6',anchors[QI][obs],normals[QI][obs],'o2m','median'),
        ('vis256_m2o_med6',anchors[QI][obs],normals[QI][obs],'m2o','median'),
        ('hist_mean6',anchors,normals,'o2m','mean'),
        ('hist_plane6',anchors,normals,'o2m','plane'),
        ('hist_plane_gate6',anchors,normals,'o2m','plane_gate')]:
        delta,tr=nn_path(points,an,no,6,direction,kind);add(name,delta,tr)
    for name,measurement,kind in [('proj_vis_med1',a['ray_measured'][obs],'median'),('proj_lattice_vis_med1',a['sampled_pixel_measured'],'median')]:
        delta,tr=fixed_update((measurement-q[obs]).astype(np.float64),qn[obs],kind);add(name,delta,tr)
    for kind in ['median','mean','plane']:
        name={'median':'lattice_nn_vis_med1','mean':'lattice_nn_vis_mean1','plane':'lattice_nn_vis_plane1'}[kind]
        delta,tr=nn_path(a['lattice_points'],q[obs],qn[obs],1,'m2o',kind);add(name,delta,tr)
    assert set(results)==set(CFG['methods'])
    out=W/'fits';out.mkdir(exist_ok=True)
    npz=out/(tag+'.npz')
    np.savez_compressed(npz,method_names=np.array(CFG['methods']),cameras_m=np.array([results[n]['camera_m'] for n in CFG['methods']]),
        raw_deltas_m=np.array([results[n]['raw_delta_m'] for n in CFG['methods']]),
        applied_deltas_m=np.array([results[n]['applied_delta_m'] for n in CFG['methods']]),
        body_m=body,coarse_camera_m=coarse,original_camera_m=original)
    result=dict(task=t,methods=results,fit_input_sha256=sha(W/'inputs'/(tag+'.npz')),prediction_sha256=sha(G/t['prediction']),
        compact_prediction=str(npz),compact_prediction_sha256=sha(npz),official_reproduction=official_reproduction,
        query_anchor_numeric_bound_m=anchor_numeric,Camera_B_read=False,body_exact_unchanged=True)
    dump(out/(tag+'.json'),result);return dict(tag=tag,sha256=sha(out/(tag+'.json')),official_reproduction=official_reproduction)


def preflight():
    from solvers import update
    initialize();rng=np.random.default_rng(52);p=rng.normal(0,.3,(120,3));delta=np.array([.009,-.006,.011])
    n=rng.normal(size=p.shape);n/=np.linalg.norm(n,axis=1)[:,None]
    for kind in ['median','mean','plane']:
        s,_=update(np.tile(delta,(len(p),1)),n,kind);np.testing.assert_allclose(s,delta,atol=1e-12)
    n=np.tile([0.,0.,1.],(20,1));s,stats=update(np.tile(delta,(20,1)),n,'plane');np.testing.assert_allclose(s,[0,0,.011],atol=1e-12)
    raw,tr=nn_path(p+delta,p,normals=np.ones_like(p),steps=6)
    old,_,old_tr,_=HIST(p+delta,p);np.testing.assert_array_equal(raw,old)
    selected=[]
    for seed in CFG['seeds']:
        for d in ['native','real','behave']:selected.append(next(t for t in tasks() if t['seed']==seed and t['dataset']==d))
    selected += [next(t for t in tasks() if t['seed']==11 and t['dataset']=='real' and t['identity']==i) for i in ['p001195','p001196']]
    results=[one(t) for t in selected]
    dump(W/'SOLVER_PREFLIGHT.json',dict(status='PASS',analytic_translation=True,plane_rank_deficiency_minimum_norm=True,historical_operator_exact=True,records=results))
    return selected


def main(workers,pilot):
    started=time.monotonic()
    if pilot:preflight();print('SOLVER_PREFLIGHT_PASS',flush=True);return
    assert json.loads((W/'SOLVER_PREFLIGHT.json').read_text())['status']=='PASS'
    files={str(p.relative_to(W)):sha(p) for p in sorted((W/'code').glob('*.py'))}
    files.update({n:sha(W/n) for n in ['EXPERIMENT.json','INPUT_FREEZE.json']})
    dump(W/'EXECUTION_FREEZE.json',dict(status='FROZEN_BEFORE_FULL_SOLVER_RUN',files=files))
    rr=tasks();done=[]
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize) as pool:
        for i,r in enumerate(pool.map(one,rr,chunksize=2),1):
            done.append(r)
            if i%200==0:print('FITS',i,len(rr),round(time.monotonic()-started,1),flush=True)
    dump(W/'FITS_COMPLETE.json',dict(status='COMPLETE',records=done,frames=len(done),method_frame_records=len(done)*len(CFG['methods']),seconds=time.monotonic()-started,Camera_B_read=False,training=False))
    print('FITS_COMPLETE',len(done),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=24);p.add_argument('--pilot',action='store_true');a=p.parse_args();main(a.workers,a.pilot)
