"""Freeze Camera predictions first; historical A Txyz, unchanged held-out B.

This is consumed HuMMan development evidence, not MHR anatomical ground truth.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import time
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import numpy as np
import torch
from camera_head import CameraHead
from train_camera import forward,sha


def predict(root,cell,checkpoint):
    data=root/'assets/compact_real'
    rows=json.loads((data/'MANIFEST.json').read_text())['records']
    assert len(rows)==232 and all(r['role'] in ['TRAIN','VAL'] for r in rows)
    values={k:[] for k in ['rgb','metric','original_camera','K','bbox_center','bbox_scale','available']}
    for r in rows:
        with np.load(data/r['compact_file']) as z:
            for k in values:values[k].append(z[k])
    table={k:torch.as_tensor(np.stack(v)) for k,v in values.items()}
    state=torch.load(checkpoint,map_location='cpu',weights_only=False)
    mode=state['execution_identity']['mode']
    if mode in ['mixed','native_only']:mode='metric_xyz'
    model=CameraHead(state['head']['metric_mean'],state['head']['metric_std'],mode)
    model.load_state_dict(state['head']);model.eval()
    with torch.no_grad():
        camera=torch.cat([forward(model,table,np.arange(b,min(b+16,len(rows))),'cpu')
                          for b in range(0,len(rows),16)]).numpy()
    directory=root/'real_predictions'/cell;directory.mkdir(parents=True,exist_ok=False)
    receipts=[]
    for r,c in zip(rows,camera):
        key=Path(r['compact_file']).stem
        with np.load(data/r['compact_file']) as z:
            body=z['official_pred_vertices'].reshape(-1,3)
            K=z['K'];center=z['bbox_center'];box=z['bbox_scale'][0]
            vc=body+c
            kp=z['official_pred_keypoints_3d'].reshape(-1,3)+c
            projection=lambda xyz:(xyz@K.T)[:,:2]/xyz[:,2:]
            bs=2*K[0,0]/c[2]
            raw=np.asarray([-(bs-1e-8)/box,
                c[0]-(center[0]-K[0,2])*c[2]/K[0,0],
                -c[1]+(center[1]-K[1,2])*c[2]/K[0,0]],np.float32)
            # Body identity is explicit; original camera-dependent fields stay prefixed.
            outputs={k:z['official_'+k] for k in ['pred_vertices','global_rot','body_pose','shape','scale',
                      'hand','face','pred_pose_raw','mhr_model_params','pred_joint_coords','joint_global_rots','pred_keypoints_3d']}
            np.savez_compressed(directory/(key+'.npz'),**outputs,vertices_camera_A=vc,
                pred_cam_t=c[None],pred_cam=raw[None],K=K,pred_keypoints_2d=projection(kp)[None],
                pred_keypoints_2d_verts=projection(vc)[None],pred_keypoints_2d_depth=kp[None,:,2],
                original_camera=z['original_camera'])
            receipts.append(dict(key=key,checkpoint_sha256=sha(checkpoint),camera_xyz_m=c.tolist(),
                all_Body_parameters_exact_equal=True,cropped_projection='not exported; original affine absent in compact package',
                positive_camera_space_vertex_fraction=float(np.mean(vc[:,2]>0))))
    (directory/'PREDICTION_FREEZE.json').write_text(json.dumps(dict(
        checkpoint_sha256=sha(checkpoint),records=receipts,camera_B_read=False,TEST_read=False),indent=2))


def worker(task):
    root,cell,row=task;root=Path(root);history=root/'assets/real_evaluation'
    sys.path.insert(0,str(history/'code'))
    from run_r41_txyz import dependencies,summary,regional
    f=dependencies(history/'code')
    key=f"{row['sequence']}_{row['frame']:06d}"
    native=history/'assets/original_assets/official' if cell=='official' else root/'real_predictions'/cell
    path=native/(key+'.npz');z=np.load(path)
    inputs=np.load(history/'assets/original_assets/inputs'/(key+'.npz'))
    faces=np.load(history/'assets/original_assets/official/faces.npy')
    anchors=np.load(history/'assets/runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz')
    va=z['vertices_camera_A'];surface=(va[faces[anchors['face_index']]]*anchors['barycentric'][:,:,None]).sum(1)
    raw,applied,trace,fallback=f['fit_txyz'](inputs['points_camera_A'],surface)
    ca={k:inputs['A_'+k] for k in ['R','T']};cb={k:inputs['B_'+k] for k in ['R','T']}
    vb=f['transform_camera'](va,ca,cb);moved=va+applied
    moved_b=f['transform_camera'](moved,ca,cb)
    target=root/'real_corrected'/cell/(key+'.npz');target.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(target,vertices_camera_A=moved,vertices_camera_B=moved_b,
        pred_cam_t=z['pred_cam_t']+applied,raw_translation_m=raw,applied_translation_m=applied,
        **{k:z[k] for k in ['global_rot','body_pose','shape','scale']})
    # B is first read only after the prediction and optional A fit have been fixed.
    points=np.load(history/'assets/datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
    labels=np.load(history/'regions'/(key+'.npz'))['labels']
    before=f['distance'](points,vb,faces)*1000
    after=f['distance'](points,moved_b,faces)*1000
    distance_path=root/'real_distances'/cell/(key+'.npz');distance_path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(distance_path,before_mm=before,after_mm=after)
    return dict(cell=cell,key=key,identity=row['identity'],role=row['role'],sequence=row['sequence'],frame=row['frame'],
        triangle_before=summary(before),triangle_after=summary(after),regions_before=regional(before,labels),
        regions_after=regional(after,labels),raw_translation_m=raw.tolist(),applied_translation_m=applied.tolist(),
        fallback=fallback,trace=trace,input_sha256=sha(path),corrected_sha256=sha(target),
        A_sample_indices_sha256=hashlib.sha256(inputs['source_indices'].tobytes()).hexdigest())


def run(a):
    torch.set_num_threads(2)
    history=a.root/'assets/real_evaluation'
    rows=json.loads((history/'FRAME_CONTRACT.json').read_text())['records']
    assert len(rows)==232 and all(r['role'] in ['TRAIN','VAL'] for r in rows)
    sys.path.insert(0,str(history/'code'))
    from run_r41_txyz import dependencies
    funcs=dependencies(history/'code')
    old={Path(r['file']).stem:r for r in json.loads((history/'HISTORICAL_TXYZ.json').read_text())['records'] if r['method']=='official'}
    cells=['official']
    stages=['native','continuation'] if a.stage=='all' else [a.stage]
    for stage in stages:
        for directory in sorted((a.root/stage).glob('*')):
            if (directory/'best.pt').exists() and (directory/'RESULTS.json').exists():
                cell=a.tag+stage+'__'+directory.name
                predict(a.root,cell,directory/'best.pt');cells.append(cell)
    receipts=[];records=[]
    a.root.joinpath('real_evaluation').mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for cell in cells:
            if time.time()>=a.deadline:break
            if (a.root/'real_evaluation'/(cell+'.json')).exists():
                continue
            result=list(pool.map(worker,[(str(a.root),cell,r) for r in rows]))
            if cell=='official':
                for r in result:
                    ref=old[r['key']]
                    assert np.max(np.abs(np.asarray(r['raw_translation_m'])-ref['raw_translation_m']))<1e-9
                    assert r['fallback']==ref['fallback']
                    assert max(abs(r['triangle_after'][k]-ref['triangle'][k]) for k in ['median_mm','p95_mm','coverage_50mm'])<1e-6
                (a.root/'real_evaluation/OFFICIAL_REPRODUCTION_GATE.json').write_text(json.dumps(dict(status='PASS',frames=232),indent=2))
            records.extend(result)
            aggregated={}
            for role in ['TRAIN','VAL']:
                for stage in ['before','after']:
                    rr=[dict(r,triangle=r['triangle_'+stage]) for r in result if r['role']==role]
                    aggregated[role+'_'+stage]=funcs['aggregate_real'](rr)
            report=dict(cell=cell,aggregated=aggregated,records=result,
                        fallback=sum(r['fallback'] for r in result),TEST_read=False,camera_B_fit=False)
            (a.root/'real_evaluation'/(cell+'.json')).write_text(json.dumps(report,indent=2))
            receipts.append(dict(cell=cell,fallback=report['fallback'],
                primary={k:v['identity_equal_mean'] for k,v in aggregated.items()}))
            (a.root/'real_evaluation'/('SUMMARY_'+a.tag+a.stage+'.json')).write_text(json.dumps(receipts,indent=2))
            print('REAL_COMPLETE',cell,report['fallback'],report['aggregated']['VAL_after']['identity_equal_mean'],flush=True)
    (a.root/'real_evaluation'/('EXECUTION_RESULT_'+a.tag+a.stage+'.json')).write_text(json.dumps(dict(
        planned_cells=cells,completed_cells=[r['cell'] for r in receipts],TEST_read=False,
        interpretation='independent visible surface geometry, not corresponding MHR Body or acupoint accuracy'),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--stage',choices=['native','continuation','all'],default='all')
    p.add_argument('--tag',default='')
    p.add_argument('--workers',type=int,default=8);p.add_argument('--deadline',type=float,required=True)
    run(p.parse_args())
