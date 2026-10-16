"""Open heldout evidence only after A-only fits; retain every frame and seed."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,json,sys,time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from common import W,G,CFG,load,sha,tasks,key,dump

FUN=FACES=MAPF=MAPB=None


def initialize():
    global FUN,FACES,MAPF,MAPB
    sys.path.insert(0,str(G/'historical_code'))
    from run_r41_txyz import dependencies
    FUN=dependencies(G/'historical_code');FACES=np.load(G/'assets/faces.npy')
    with np.load(G/'assets/mhr2smpl_mapping.npz') as z:MAPF=FACES[z['triangle_ids']];MAPB=z['baryc_coords']


def stats(d):return dict(median_mm=float(np.median(d)),p95_mm=float(np.quantile(d,.95)),coverage_50mm=float(np.mean(d<=50)))


def one(t):
    started=time.monotonic();tag=key(t);fit=json.loads((W/'fits'/(tag+'.json')).read_text());z=load(fit['compact_prediction']);gold=load(G/t['prediction'])
    assert sha(fit['compact_prediction'])==fit['compact_prediction_sha256']
    base_coarse=(z['body_m']+z['coarse_camera_m']).astype(np.float64)
    base_official=(z['body_m']+z['original_camera_m']).astype(np.float64)
    if t['dataset']=='native':truth=load(G/t['truth']);gt=(truth['pred_vertices']+truth['pred_cam_t'][:,None]).reshape(-1,3).astype(np.float64)
    else:
        source=load(G/t['input']);held=load(G/t['heldout'])
        if t['dataset']=='behave':reference=load(G/t['reference'])['vertices_camera_m'].astype(np.float64)
        else:labels=load(G/t['regions'])['labels']
    methods={};distance_cache={}
    for name in CFG['methods']:
        r=fit['methods'][name]
        v=gold['vertices_camera_A'].astype(np.float64) if name=='fine' else base_official+np.asarray(r['applied_delta_m']) if name=='official_hist6' else base_coarse+np.asarray(r['applied_delta_m'])
        if t['dataset']=='native':
            error=np.linalg.norm(v-gt,axis=1)*1000
            metrics=dict(vertex_camera_mm=float(error.mean()),vertex_p95_mm=float(np.quantile(error,.95)),camera_mm=float(np.linalg.norm(np.asarray(r['camera_m'])-truth['pred_cam_t'].reshape(3))*1000))
            methods[name]=dict(metrics=metrics);continue
        if t['dataset']=='real':
            ca={k:source['A_'+k] for k in ['R','T']};cb={k:source['B_'+k] for k in ['R','T']}
            vb=FUN['transform_camera'](v,ca,cb);d=FUN['distance'](held['points_camera_B'],vb,FACES)*1000
            methods[name]=dict(metrics=stats(d),regions={region:stats(d[labels==i]) for i,region in enumerate(['shoulder_upper_torso_proxy','middle_torso_proxy','waist_lower_torso_proxy','arms','legs','head','hands_feet']) if np.any(labels==i)})
            distance_cache[name+'_B_mm']=d.astype(np.float32)
        else:
            cameras={}
            for kid in [1,2,3]:
                vb=(v@source['K0_R'].T+source['K0_t']-held['K%d_t'%kid])@held['K%d_R'%kid]
                d=FUN['distance'](held['K%d_points_m'%kid],vb,FACES)*1000;cameras['K%d'%kid]=stats(d);distance_cache[name+'_K%d_mm'%kid]=d.astype(np.float32)
            mapped=np.einsum('nj,njk->nk',MAPB,v[MAPF]);pve=float(np.linalg.norm(mapped-reference,axis=1).mean()*1000)
            methods[name]=dict(metrics={k:float(np.mean([r[k] for r in cameras.values()])) for k in ['median_mm','p95_mm','coverage_50mm']},per_camera=cameras,pve_mm=pve)
    reproduction={}
    if t['dataset']!='native':
        for name,reference in [('official_hist6',t['baseline']),('fine',t['original_final_evaluation'])]:
            ref=reference['triangle_txyz' if name=='official_hist6' else 'triangle'] if t['dataset']=='real' else reference['frame_surface_camera_equal_mean']
            diff={k:abs(methods[name]['metrics'][k]-ref[k]) for k in ['median_mm','p95_mm']}
            assert max(diff.values())<.02,(tag,name,'OLD_EVALUATION_MISMATCH',diff)
            reproduction[name]=diff
    out=W/'evaluation';out.mkdir(exist_ok=True)
    if distance_cache:np.savez_compressed(out/(tag+'.npz'),**distance_cache)
    result=dict(task={k:t.get(k,'all_images') for k in ['dataset','seed','key','identity','role','sequence','frame']},methods=methods,
        fit_sha256=sha(W/'fits'/(tag+'.json')),reproduction=reproduction,seconds=time.monotonic()-started,Camera_B_fit=False)
    dump(out/(tag+'.json'),result);return dict(tag=tag,sha256=sha(out/(tag+'.json')),seconds=result['seconds'],reproduction=reproduction)


def main(workers,pilot):
    started=time.monotonic()
    if pilot:
        tags={r['tag'] for r in json.loads((W/'SOLVER_PREFLIGHT.json').read_text())['records']};rr=[t for t in tasks() if key(t) in tags]
    else:
        assert json.loads((W/'FITS_COMPLETE.json').read_text())['status']=='COMPLETE';rr=tasks()
    todo=[t for t in rr if not (W/'evaluation'/(key(t)+'.json')).exists()];done=[]
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize) as pool:
        for i,r in enumerate(pool.map(one,todo,chunksize=1),1):
            done.append(r)
            if i%25==0 or i==len(todo):print('EVALUATED_FRAMES',i,len(todo),round(time.monotonic()-started,1),flush=True)
    result=dict(status='PASS' if pilot else 'COMPLETE',expected_frames=len(rr),newly_evaluated=len(done),
        method_records=len(rr)*len(CFG['methods']),seconds=time.monotonic()-started,workers=workers,
        reproduction_max_mm=max([v for r in done for d in r['reproduction'].values() for v in d.values()]+[0]),Camera_B_fit=False)
    dump(W/('EVALUATOR_PREFLIGHT.json' if pilot else 'EVALUATION_COMPLETE.json'),result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=32);p.add_argument('--pilot',action='store_true');a=p.parse_args();main(a.workers,a.pilot)
