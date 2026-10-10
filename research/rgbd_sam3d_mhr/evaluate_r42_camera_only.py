"""Frozen tiny Camera-only pilot on original 232 development frames; B eval only."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time
from camera_only_r42 import features, predict
from run_r41_txyz import dependencies, np, sha, summary, regional, summarize


def one(task):
    source,out,key,ref,cell=task;source,out=Path(source),Path(out);assets=source/'assets'
    f=dependencies(source/'code');z=np.load(assets/'original_assets/official'/(key+'.npz'))
    a=np.load(assets/'original_assets/inputs'/(key+'.npz'))
    faces=np.load(assets/'original_assets/official/faces.npy')
    anchor=np.load(assets/'runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz')
    body=z['vertices_camera_A'].astype(np.float64)-z['pred_cam_t'].reshape(3)
    body_anchors=(body[faces[anchor['face_index']]]*anchor['barycentric'][:,:,None]).sum(1)
    state=dict(np.load(out/'camera_only_pilot/camera_only_best.npz'))
    if cell=='metric_base_no_learned_offset':
        state['coefficients']=np.zeros_like(state['coefficients'])
    camera=predict(a['points_camera_A'],body_anchors,z['pred_cam_t'],state)
    camera=camera.astype(z['pred_cam_t'].dtype).reshape(1,3)
    vertices=z['vertices_camera_A']+(camera-z['pred_cam_t']).reshape(3)
    surface=(vertices[faces[anchor['face_index']]]*anchor['barycentric'][:,:,None]).sum(1)
    raw,applied,trace,fallback=f['fit_txyz'](a['points_camera_A'],surface)
    ca,cb=({k:a['A_'+k] for k in ['R','T']},{k:a['B_'+k] for k in ['R','T']})
    before_b=f['transform_camera'](vertices,ca,cb);after_b=f['transform_camera'](vertices+applied,ca,cb)
    for stage,va,vb,cam in [('raw',vertices,before_b,camera),('corrected',vertices+applied,after_b,camera+applied)]:
        p=out/stage/cell/(key+'.npz');p.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(p,vertices_camera_A=va,vertices_camera_B=vb,pred_cam_t=cam,raw_translation_m=raw,applied_translation_m=applied,
                            **{k:z[k] for k in ['global_rot','body_pose','shape','scale']})
    # Independent B loaded only after prediction and A-only fitting are fixed.
    b=np.load(assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
    before=f['distance'](b,before_b,faces)*1000;after=f['distance'](b,after_b,faces)*1000
    labels=np.load(source/'regions'/(key+'.npz'))['labels']
    p=out/'distances'/cell/(key+'.npz');p.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(p,before_mm=before,after_mm=after)
    checks={}
    origin=predict(a['points_camera_A'],body_anchors,z['pred_cam_t'],state)
    for name,delta in [('xyz_translation_200mm',np.array([.03,-.02,.2]))]:
        got=predict(a['points_camera_A']+delta,body_anchors,z['pred_cam_t'],state)
        checks[name]=dict(camera_delta_mm=((got-origin)*1000).tolist(),ideal_delta_mm=(delta*1000).tolist(),
                         max_error_mm=float(np.max(np.abs(got-origin-delta))*1000))
    for offset in [-.2,.2]:
        points=a['points_camera_A'];perturbed=points.astype(np.float64).copy()
        perturbed[:,:2]*=(1+offset/points[:,2])[:,None];perturbed[:,2]+=offset
        got=predict(perturbed,body_anchors,z['pred_cam_t'],state)
        checks[f'depth_offset_{offset}_fixed_RGB']=dict(camera_delta_mm=((got-origin)*1000).tolist(),
            interpretation='Numerical depth/ray perturbation with fixed RGB; not physically re-rendered GT experiment.')
    assert np.array_equal(predict(a['points_camera_A'][:0],body_anchors,z['pred_cam_t'],state),z['pred_cam_t'].reshape(3))
    return dict(**{k:ref[k] for k in ['identity','role','sequence','frame','key']},cell=cell,
        triangle_before=summary(before),triangle_after=summary(after),regions_before=regional(before,labels),regions_after=regional(after,labels),
        raw_translation_m=raw.tolist(),applied_translation_m=applied.tolist(),raw_norm_mm=float(np.linalg.norm(raw)*1000),
        applied_norm_mm=float(np.linalg.norm(applied)*1000),trace=trace,fallback=fallback,original_official_fallback=ref['fallback'],
        learned_camera_m=camera.reshape(3).tolist(),camera_delta_from_official_mm=((camera-z['pred_cam_t'])*1000).reshape(3).tolist(),
        depth_response=checks,missing_depth_camera_exact=True,body_parameter_arrays_exact=True,
        body_relative_vertex_roundoff_max_m=float(np.max(np.abs((vertices.astype(np.float64)-camera.reshape(3))-body))))


def main(a):
    start=time.monotonic();model=a.out/'camera_only_pilot/camera_only_best.npz'
    report=json.loads((a.out/'camera_only_pilot/TRAINING_RESULT.json').read_text())
    assert sha(model)==report['model_sha256']
    old=json.loads((a.source/'PAIRED_RESULTS.json').read_text())
    refs=[r for r in old['records'] if r['cell']=='official'];assert len(refs)==232
    config=dict(stage='R4.2_FROZEN_CAMERA_ONLY_EVALUATION',model_sha256=sha(model),frames=232,
                cells=['camera_only','metric_base_no_learned_offset'],B_model_selection=False,test_read=False,
                evaluator_sha256=sha(Path(__file__)),training_result_sha256=sha(a.out/'camera_only_pilot/TRAINING_RESULT.json'))
    (a.out/'camera_only_pilot/EVALUATION_CONFIG.json').write_text(json.dumps(config,indent=2))
    tasks=[(str(a.source),str(a.out),r['key'],r,cell) for cell in config['cells'] for r in refs]
    rows=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for r in pool.map(one,tasks):
            rows.append(r)
            if len(rows)%116==0:print('CAMERA_ONLY_EVAL',len(rows),'/',len(tasks),flush=True)
    new=summarize(rows,dependencies(a.source/'code'))
    new.update(seconds=time.monotonic()-start,model_sha256=sha(model))
    assert sha(model)==report['model_sha256']
    (a.out/'camera_only_pilot/PILOT_RESULTS.json').write_text(json.dumps(new,indent=2))
    combined=json.loads((a.out/'PAIRED_RESULTS.json').read_text())
    combined['records'].extend(rows);combined['results'].update(new['results'])
    (a.out/'ALL_RESULTS.json').write_text(json.dumps(combined,indent=2))
    for cell in config['cells']:
        print(cell,{role:{stage:new['results'][cell][stage][role]['identity_equal_mean'] for stage in ['before','after']} for role in ['TRAIN','VAL']},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=6);main(p.parse_args())
