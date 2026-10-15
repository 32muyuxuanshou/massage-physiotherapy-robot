"""A-only fixed-scale rigid control, with matched translation and frozen Txyz."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0,str(Path(__file__).parent))
from analyze_cached import rigid_align,summary,REGIONS

BOUND=.17788820176363325


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def matched_fit(points, anchors, pivot, rotate):
    R=np.eye(3);d=np.zeros(3);trace=[]
    for iteration in range(6):
        current=(anchors-pivot)@R.T+pivot+d
        distances,near=cKDTree(current).query(points,workers=1)
        keep=distances<=np.quantile(distances,.8)
        p,q=current[near[keep]],points[keep]
        if rotate:
            _,step_row_R=rigid_align(p,q)
            rotation=step_row_R.T@R
            step=q.mean(0)-((p.mean(0)-pivot-d)@step_row_R+pivot+d)
        else:
            rotation=R;step=(q-p).mean(0)
        applied_step=np.clip(step,-.05,.05)
        R=rotation;d+=applied_step
        trace.append(dict(iteration=iteration+1,retained_points=int(keep.sum()),
            step_m=applied_step.tolist(),d_m=d.tolist(),R=R.tolist()))
    fallback=bool(np.linalg.norm(d)>BOUND)
    return dict(raw_R=R,raw_d=d,R=np.eye(3) if fallback else R,
                d=np.zeros(3) if fallback else d,fallback=fallback,trace=trace)


def worker(arg):
    geometry,official,out,task=arg
    geometry=Path(geometry);out=Path(out)
    sys.path.insert(0,str(geometry/'historical_code'))
    from run_r41_txyz import dependencies
    f=dependencies(geometry/'historical_code')
    path=Path(official)/(task['key']+'.npz')
    assert sha(path)==task['baseline']['prediction_sha256']
    with np.load(path) as z:v=z['vertices_camera_A']
    with np.load(geometry/task['input']) as z:
        points=z['points_camera_A'];ca={k:z['A_'+k] for k in ['R','T']};cb={k:z['B_'+k] for k in ['R','T']}
    faces=np.load(geometry/'assets/faces.npy')
    with np.load(geometry/'assets/anchors.npz') as z:
        anchors=(v[faces[z['face_index']]]*z['barycentric'][:,:,None]).sum(1)
    raw,applied,trace,fallback=f['fit_txyz'](points,anchors)
    assert np.max(np.abs(raw-np.array(task['baseline']['raw_translation_m'])))<1e-9
    assert fallback==task['baseline']['fallback']
    v=v.astype(np.float64)
    pivot=v.mean(0)
    fitted={name:matched_fit(points,anchors,pivot,rotate) for name,rotate in [('matched_translation',False),('matched_rigid',True)]}
    # Fix and save every transform before loading B observations.
    cache=out/'transforms'/(task['key']+'.npz');cache.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(cache,pivot_m=pivot,**{name+'_'+k:fit[k] for name,fit in fitted.items() for k in ['R','d','raw_R','raw_d']})
    with np.load(geometry/task['heldout']) as z:held=z['points_camera_B']
    with np.load(geometry/task['regions']) as z:labels=z['labels']
    report={k:task[k] for k in ['key','identity','sequence','frame','role']}
    report['official_txyz']=task['baseline']['triangle_txyz']
    report['historical_Txyz_reproduced']=True;report['methods']={}
    arrays={}
    for name,fit in fitted.items():
        moved=(v-pivot)@fit['R'].T+pivot+fit['d']
        vb=f['transform_camera'](moved,ca,cb)
        distance=f['distance'](held,vb,faces)*1000
        report['methods'][name]=dict(metrics=summary(distance),
            regions={label:summary(distance[labels==i]) for i,label in enumerate(REGIONS) if np.any(labels==i)},
            fallback=fit['fallback'],raw_translation_m=fit['raw_d'].tolist(),
            applied_translation_m=fit['d'].tolist(),trace=fit['trace'],
            applied_rotation_deg=float(np.rad2deg(np.arccos(np.clip((np.trace(fit['R'])-1)/2,-1,1)))))
        arrays[name+'_distance_mm']=distance
    distance_path=out/'distances'/(task['key']+'.npz');distance_path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(distance_path,**arrays)
    return report


def main(a):
    manifest=json.loads((a.geometry/'MANIFEST.json').read_text())
    tasks=[t for t in manifest['tasks'] if t['dataset']=='real' and t['seed']==11]
    assert len(tasks)==232
    a.out.mkdir(parents=True,exist_ok=True)
    contract=Path(__file__).with_name('RIGID_DIAGNOSTIC_CONTRACT.json')
    (a.out/'EXECUTION_CONTRACT.json').write_text(json.dumps(dict(
        contract=json.loads(contract.read_text()),contract_sha256=sha(contract),
        code_sha256=sha(__file__),geometry_manifest_sha256=sha(a.geometry/'MANIFEST.json'),
        seed_policy='Official body is one shared frozen cached input across all R5 training seeds; fitting deterministic, not repeated as independent seeds'),indent=2))
    if a.pilot:tasks=[tasks[0],next(t for t in tasks if t['identity']=='p001195'),next(t for t in tasks if t['identity']=='p001196')]
    directory=a.out/'records';directory.mkdir(exist_ok=True)
    tasks=[t for t in tasks if not (directory/(t['key']+'.json')).exists()]
    start=time.monotonic()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        args=[(str(a.geometry),str(a.official),str(a.out),t) for t in tasks]
        for i,r in enumerate(pool.map(worker,args),1):
            (directory/(r['key']+'.json')).write_text(json.dumps(r,indent=2))
            if i%10==0 or i==len(tasks):print('RIGID_COMPLETE',i,len(tasks),round(time.monotonic()-start,1),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['geometry','official','out']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--workers',type=int,default=6);p.add_argument('--pilot',action='store_true')
    main(p.parse_args())
