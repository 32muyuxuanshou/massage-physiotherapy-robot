"""Historical Camera-B evaluator; Txyz is used only for Official baseline."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,hashlib,json,sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def worker(task):
    history,directory,mode,out,row=task;history=Path(history);out=Path(out)
    sys.path.insert(0,str(history/'code'))
    from run_r41_txyz import dependencies,summary,regional
    f=dependencies(history/'code');key=f"{row['sequence']}_{row['frame']:06d}"
    official=history/'assets/original_assets/official'/(key+'.npz')
    path=official if mode=='official' else Path(directory)/(key+'.npz')
    with np.load(path) as z:va=z['vertices_camera_A']
    with np.load(history/'assets/original_assets/inputs'/(key+'.npz')) as inputs:
        ca={k:inputs['A_'+k] for k in ['R','T']};cb={k:inputs['B_'+k] for k in ['R','T']}
        faces=np.load(history/'assets/original_assets/official/faces.npy')
        if mode=='official':
            with np.load(history/'assets/runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz') as anchors:
                surface=(va[faces[anchors['face_index']]]*anchors['barycentric'][:,:,None]).sum(1)
            raw,applied,trace,fallback=f['fit_txyz'](inputs['points_camera_A'],surface)
            A_indices_sha=hashlib.sha256(inputs['source_indices'].tobytes()).hexdigest()
    vb=f['transform_camera'](va,ca,cb)
    # Prediction (and Official-only A fit) frozen before opening B.
    with np.load(history/'assets/datasets/heldout/humman_r3_k1_v1'/(key+'.npz')) as z:points=z['points_camera_B']
    assert len(points)==2048
    labels=np.load(history/'regions'/(key+'.npz'))['labels'];distance=f['distance'](points,vb,faces)*1000
    result=dict(key=key,identity=row['identity'],role=row['role'],sequence=row['sequence'],frame=row['frame'],
        triangle=summary(distance),regions=regional(distance,labels),prediction_sha256=sha(path),
        B_points_sha256=hashlib.sha256(points.tobytes()).hexdigest(),new_model_Txyz=False)
    arrays=dict(raw_mm=distance)
    if mode=='official':
        moved=f['transform_camera'](va+applied,ca,cb);after=f['distance'](points,moved,faces)*1000
        result.update(triangle_txyz=summary(after),regions_txyz=regional(after,labels),
            raw_translation_m=raw.tolist(),applied_translation_m=applied.tolist(),fallback=fallback,trace=trace,
            A_indices_sha256=A_indices_sha)
        arrays['Official_Txyz_mm']=after
    out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/(key+'.npz'),**arrays)
    return result

def run(a):
    sys.path.insert(0,str(a.history/'code'))
    from run_r41_txyz import dependencies
    f=dependencies(a.history/'code');rows=json.loads((a.history/'FRAME_CONTRACT.json').read_text())['records']
    assert len(rows)==232 and all(r['role'] in ['TRAIN','VAL'] for r in rows)
    a.out.mkdir(parents=True,exist_ok=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        records=list(pool.map(worker,[(str(a.history),str(a.predictions),a.mode,str(a.out/'distances'),r) for r in rows]))
    if a.mode=='official':
        old={Path(r['file']).stem:r for r in json.loads((a.history/'HISTORICAL_TXYZ.json').read_text())['records'] if r['method']=='official'}
        for r in records:
            ref=old[r['key']]
            assert np.max(np.abs(np.asarray(r['raw_translation_m'])-ref['raw_translation_m']))<1e-9
            assert r['fallback']==ref['fallback']
            assert max(abs(r['triangle_txyz'][k]-ref['triangle'][k]) for k in ['median_mm','p95_mm','coverage_50mm'])<1e-6
        (a.out/'OFFICIAL_TXYZ_REPRODUCTION_GATE.json').write_text(json.dumps(dict(status='PASS',frames=232),indent=2))
    aggregate={role:f['aggregate_real']([r for r in records if r['role']==role]) for role in ['TRAIN','VAL']}
    if a.mode=='official':
        aggregate.update({role+'_Txyz':f['aggregate_real']([dict(r,triangle=r['triangle_txyz']) for r in records if r['role']==role]) for role in ['TRAIN','VAL']})
    (a.out/'RESULTS.json').write_text(json.dumps(dict(status='CAMERA_B_EVALUATION_COMPLETE',mode=a.mode,records=records,
        aggregated=aggregate,TEST_read=False,camera_B_fit=False,new_model_Txyz=False,
        interpretation='fixed Camera-B visible sensor points to exact predicted triangles; no native MHR correspondence or acupoint GT'),indent=2))
    print('REAL_RAW_COMPLETE',a.mode,{k:v['identity_equal_mean'] for k,v in aggregate.items()},flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['history','predictions','out']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--mode',required=True);p.add_argument('--workers',type=int,default=8);run(p.parse_args())
