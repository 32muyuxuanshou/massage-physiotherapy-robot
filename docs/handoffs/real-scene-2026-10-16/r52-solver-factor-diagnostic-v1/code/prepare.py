"""Read A-only caches; freeze exact source bytes and noisy observations."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,json,time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import torch
from torch.nn import functional as F
from common import W,OLD,G,CFG,load,sha,tasks,key,dump


def one(t):
    tag=key(t);out=W/'inputs'/(tag+'.npz')
    source=OLD/'cache'/('native_scale_v2' if t['dataset']=='native' else 'humman_development_v1' if t['dataset']=='real' else 'behave/s%d'%t['seed'])/(t['key']+'.pt')
    replay=OLD/'query_replay_frozen_coarse'/('s%d'%t['seed'])/(t['dataset']+'_'+t['key']+'.npz')
    rec=torch.load(source,map_location='cpu',weights_only=False)
    z=load(replay);geo=z['geometry'];obs=z['observed'];gold=load(G/t['prediction'])
    np.testing.assert_array_equal(rec['official']['pred_vertices'].numpy().reshape(-1,3),gold['body_m'])
    assert np.max(abs(z['replay_coarse_m'].reshape(3)-gold['coarse_camera'].reshape(3)))<1e-7
    depth=rec['depth'].numpy().reshape(rec['depth'].shape[-2:]);valid=rec['valid'].numpy().reshape(depth.shape)
    rays=rec['rays'].numpy().reshape(2,*depth.shape)
    xyz=np.concatenate((rays*depth[None],depth[None]),axis=0).transpose(1,2,0)
    lattice=xyz[valid]
    # Use the original CUDA grid_sample arithmetic. NumPy float64 rounding
    # picks a different pixel at float32 half-pixel boundaries.
    grid=torch.from_numpy(geo[:,15:17].copy()).cuda()[None,:,None]
    source_xyz=torch.from_numpy(xyz.transpose(2,0,1).copy()).cuda()[None]
    selected=F.grid_sample(source_xyz,grid,mode='nearest',align_corners=True)[0,:,:,0].T.cpu().numpy()[obs]
    np.testing.assert_allclose(selected[:,2],geo[obs,5],atol=1e-6,rtol=0,err_msg=tag)
    if t['dataset']=='native':
        rng=np.random.default_rng(int(__import__('hashlib').sha256(('R52_NATIVE_A:'+t['key']).encode()).hexdigest()[:16],16))
        indices=np.sort(rng.choice(len(lattice),min(5000,len(lattice)),replace=False));points=lattice[indices]
    else:
        a=load(G/t['input']);points=a['points_camera_A' if t['dataset']=='real' else 'K0_points_m'];indices=np.arange(len(points))
    sources={str(source):sha(source),str(replay):sha(replay),str(G/t['prediction']):sha(G/t['prediction'])}
    # Actual A points and indices already frozen in the old geometry bundle.
    if 'input' in t:sources[str(G/t['input'])]=sha(G/t['input'])
    np.savez_compressed(out,points=points,point_indices=indices,lattice_points=lattice,
        query_xyz=geo[:,:3],query_normals=geo[:,9:12],observed=obs,
        ray_measured=geo[:,3:6],sampled_pixel_measured=selected)
    return dict(tag=tag,dataset=t['dataset'],seed=t['seed'],key=t['key'],input=str(out),sha256=sha(out),
        sources=sources,lattice_count=len(lattice),raw_fit_count=len(points),visible_queries=int(obs.sum()),
        query_ray_reassignment_median_mm=float(np.median(np.linalg.norm(selected-geo[obs,3:6],axis=1))*1000))


def main(workers):
    torch.set_num_threads(1);start=time.monotonic();(W/'inputs').mkdir(exist_ok=True)
    rr=tasks();assert len(rr)==2706
    # Exact source hashes from the historical replay, including its known boundary case.
    expected={}
    for seed in CFG['seeds']:
        for r in json.loads((OLD/'query_replay_frozen_coarse'/('s%d'%seed)/'RESULTS.json').read_text())['records']:
            expected[r['source_cache_file']]=r['source_cache_sha256'];expected[r['output_file']]=r['output_sha256']
    records=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i,r in enumerate(pool.map(one,rr,chunksize=4),1):
            for p,h in r['sources'].items():
                if p in expected:assert h==expected[p],p
            records.append(r)
            if i%200==0:print('INPUTS',i,len(rr),round(time.monotonic()-start,1),flush=True)
    dump(W/'INPUT_FREEZE.json',dict(status='PASS',records=records,Camera_B_read=False,seconds=time.monotonic()-start,source_hashes_checked=True))
    files={str(p.relative_to(W)):sha(p) for p in sorted((W/'code').glob('*.py'))}
    files['EXPERIMENT.json']=sha(W/'EXPERIMENT.json');files['INPUT_FREEZE.json']=sha(W/'INPUT_FREEZE.json')
    dump(W/'SCIENCE_FREEZE.json',dict(status='FROZEN_BEFORE_SOLVER_RESULTS',files=files))
    print('INPUT_PREPARATION_COMPLETE',len(records),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);main(p.parse_args().workers)
