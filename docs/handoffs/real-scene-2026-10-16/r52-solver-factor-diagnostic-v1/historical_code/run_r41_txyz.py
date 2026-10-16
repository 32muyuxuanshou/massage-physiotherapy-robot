"""R4.1 cached-native, TRAIN/VAL-only fair Cheap Txyz diagnostic (CPU).

Historical functions are executed from their original AST without editing their
implementation. This avoids importing the GPU training stack for cached geometry.
"""
import argparse
import ast
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
METRICS = ['median_mm', 'p95_mm', 'coverage_50mm']
REGIONS = ['shoulder_upper_torso_proxy', 'middle_torso_proxy', 'waist_lower_torso_proxy', 'arms', 'legs', 'head', 'hands_feet']


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def load_historical(path, names, namespace):
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in selected}==set(names)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),namespace)
    return {n.name:namespace[n.name] for n in selected}


def dependencies(code):
    space=dict(np=np,cKDTree=cKDTree)
    funcs=load_historical(code/'diagnose_r31.py',['fit_txyz'],space)
    funcs.update(load_historical(code/'humman_geometry.py',['world_to_camera','camera_to_world','transform_camera'],space))
    funcs.update(load_historical(code/'evaluate_r3_humman.py',['aggregate_real'],space))
    # Full evaluator is an unchanged historical source file.
    sys.path.insert(0,str(code))
    import surface_metrics
    funcs['distance']=surface_metrics.point_to_triangle_distances
    funcs['paired_triangle']=surface_metrics._point_triangle_distance_squared
    return funcs


def summary(d):
    return dict(median_mm=float(np.median(d)),p95_mm=float(np.quantile(d,.95)),
        coverage_50mm=float(np.mean(d<=50)),mean_mm=float(np.mean(d)),max_mm=float(np.max(d)),point_count=len(d))


def regional(d, labels):
    return {name:summary(d[labels==i]) for i,name in enumerate(REGIONS) if np.any(labels==i)}


def make_labels(points,vertices,faces,face_labels,f):
    """Exact nearest reference triangle, fixed for every method; evaluation only."""
    dist=f['distance'](points,vertices,faces)
    triangles=np.asarray(vertices,np.float64)[faces]
    centroids=triangles.mean(1);radii=np.linalg.norm(triangles-centroids[:,None],axis=2).max(1)
    tree=cKDTree(centroids);candidates=tree.query_ball_point(points,dist+float(radii.max()),workers=1)
    chosen=np.empty(len(points),np.int64)
    for i,ids in enumerate(candidates):
        ids=np.asarray(ids,np.int64)
        ids=ids[np.linalg.norm(centroids[ids]-points[i],axis=1)-radii[ids]<=dist[i]+1e-12]
        dd=f['paired_triangle'](np.broadcast_to(points[i],(len(ids),3)),triangles[ids])
        index=int(np.argmin(dd));chosen[i]=ids[index]
        assert abs(np.sqrt(dd[index])-dist[i])<1e-9
    return face_labels[chosen],chosen


def region_worker(task):
    work,key=task;work=Path(work);assets=work/'assets';path=work/'regions'/(key+'.npz')
    if path.exists():return key
    f=dependencies(work/'code');faces=np.load(assets/'original_assets/official/faces.npy')
    face_labels=np.load(work/'REGION_TOPOLOGY.npz')['face_region']
    points=np.load(assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
    z=np.load(assets/'runs/r31_diagnosis_pilot_v1/txyz/txyz/official'/(key+'.npz'))
    labels,nearest=make_labels(points,z['vertices_camera_B'],faces,face_labels,f)
    np.savez_compressed(path,labels=labels,nearest_reference_face=nearest)
    return key


def worker(task):
    work,cell,key,row=task;work=Path(work);assets=work/'assets';f=dependencies(work/'code')
    native=assets/'original_assets/official' if cell=='official' else assets/'r4/formal'/cell/'real'
    input_path=native/(key+'.npz');z=np.load(input_path)
    compact=np.load(assets/'original_assets/inputs'/(key+'.npz'))
    faces=np.load(assets/'original_assets/official/faces.npy')
    anchors=np.load(assets/'runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz')
    fi,bc=anchors['face_index'],anchors['barycentric']
    vertices=z['vertices_camera_A']
    surface=(vertices[faces[fi]]*bc[:,:,None]).sum(1)
    # Fit has exactly two arguments, both Camera A arrays. B isn't loaded yet.
    raw,applied,trace,fallback=f['fit_txyz'](compact['points_camera_A'],surface)
    ca={k:compact['A_'+k] for k in ['R','T']};cb={k:compact['B_'+k] for k in ['R','T']}
    moved=vertices+applied
    vb=f['transform_camera'](moved,ca,cb)
    before_b=f['transform_camera'](vertices,ca,cb)
    assert np.max(np.abs(before_b-z['vertices_camera_B']))<1e-9
    corrected=work/'corrected'/cell/(key+'.npz');corrected.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(corrected,vertices_camera_A=moved,vertices_camera_B=vb,
        pred_cam_t=z['pred_cam_t']+applied,raw_translation_m=raw,applied_translation_m=applied,
        **{k:z[k] for k in ['global_rot','body_pose','shape','scale']})
    zz=np.load(corrected)
    assert all(np.array_equal(z[k],zz[k]) for k in ['global_rot','body_pose','shape','scale'])
    assert np.max(np.abs((zz['vertices_camera_A']-vertices)-applied))<1e-12
    # All B evidence enters only after correction is fixed and saved.
    points=np.load(assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
    labels=np.load(work/'regions'/(key+'.npz'))['labels']
    before=f['distance'](points,before_b,faces)*1000
    after=f['distance'](points,vb,faces)*1000
    distance_path=work/'distances'/cell/(key+'.npz');distance_path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(distance_path,before_mm=before,after_mm=after)
    identity=dict(identity=row['identity'],role=row['role'],sequence=row['sequence'],frame=row['frame'],key=key)
    report=dict(**identity,cell=cell,triangle_before=summary(before),triangle_after=summary(after),
        regions_before=regional(before,labels),regions_after=regional(after,labels),
        raw_translation_m=raw.tolist(),applied_translation_m=applied.tolist(),
        raw_norm_mm=float(np.linalg.norm(raw)*1000),applied_norm_mm=float(np.linalg.norm(applied)*1000),fallback=fallback,
        trace=trace,input_sha256=sha(input_path),corrected_sha256=sha(corrected),
        source_indices_sha256=hashlib.sha256(compact['source_indices'].tobytes()).hexdigest())
    old=np.load(assets/'original_assets/official'/(key+'.npz'))
    body=(vertices-z['pred_cam_t'].reshape(3))-(old['vertices_camera_A']-old['pred_cam_t'].reshape(3))
    camera=(z['pred_cam_t']-old['pred_cam_t']).reshape(3)
    rotation=(z['global_rot']-old['global_rot']).reshape(3)
    # Parameter coordinates are native MHR; no nonexistent real Pose/Shape GT.
    report['native_changes_from_official']=dict(camera_delta_xyz_mm=(camera*1000).tolist(),
        camera_delta_norm_mm=float(np.linalg.norm(camera)*1000),
        body_corresponding_mean_change_mm=float(np.linalg.norm(body,axis=1).mean()*1000),
        global_rotation_parameter_delta_norm_rad=float(np.linalg.norm(rotation)),
        body_pose_delta_rms_native=float(np.sqrt(np.mean((z['body_pose']-old['body_pose'])**2))),
        shape_delta_rms_native=float(np.sqrt(np.mean((z['shape']-old['shape'])**2))),
        scale_delta_rms_native=float(np.sqrt(np.mean((z['scale']-old['scale'])**2))))
    return report


def check_official(record,old,work):
    key=record['key'];ref=old[key]
    translation_error=float(np.max(np.abs(np.asarray(record['raw_translation_m'])-ref['raw_translation_m'])))
    trace_error=float(np.max(np.abs(np.array([r['step_m'] for r in record['trace']])-np.array([r['step_m'] for r in ref['trace']]))))
    metric_error=max(abs(record['triangle_after'][k]-ref['triangle'][k]) for k in METRICS)
    old_z=np.load(Path(work)/'assets/runs/r31_diagnosis_pilot_v1/txyz/txyz/official'/(key+'.npz'))
    new_z=np.load(Path(work)/'corrected/official'/(key+'.npz'))
    mesh_error=max(float(np.max(np.abs(old_z[k]-new_z[k]))) for k in ['vertices_camera_A','vertices_camera_B','pred_cam_t'])
    assert record['input_sha256']==ref['input_mesh_sha256']
    assert translation_error<1e-9 and trace_error<1e-9 and metric_error<1e-6 and mesh_error<1e-9
    assert record['fallback']==ref['fallback']
    return dict(key=key,raw_translation_max_error_m=translation_error,trace_step_max_error_m=trace_error,
        corrected_mesh_max_error_m=mesh_error,metric_max_error=metric_error,status='PASS')


def summarize(records, f):
    cells=sorted({r['cell'] for r in records})
    results={}
    for cell in cells:
        rr=[r for r in records if r['cell']==cell];result={}
        for stage in ['before','after']:
            rows=[dict(identity=r['identity'],role=r['role'],sequence=r['sequence'],frame=r['frame'],key=r['key'],triangle=r['triangle_'+stage]) for r in rr]
            result[stage]={role:f['aggregate_real']([r for r in rows if r['role']==role]) for role in ['TRAIN','VAL']}
        result['txyz']={role:dict(frames=sum(r['role']==role for r in rr),fallback_count=sum(r['fallback'] for r in rr if r['role']==role),
            raw_norm_median_mm=float(np.median([r['raw_norm_mm'] for r in rr if r['role']==role])),
            applied_norm_median_mm=float(np.median([r['applied_norm_mm'] for r in rr if r['role']==role]))) for role in ['TRAIN','VAL']}
        results[cell]=result
    report=dict(status='COMPLETE',results=results,records=records,
        aggregation='Per-frame median/P95/coverage -> equal sequence mean -> equal identity mean. No pooled point percentile.',
        test_read=False,camera_B_fitting=False)
    return report


def main(a):
    work=a.work;f=dependencies(work/'code');assets=work/'assets'
    rows=json.loads((work/'FRAME_CONTRACT.json').read_text())['records']
    receipt=json.loads((assets/'original_assets/SOURCE_RECEIPT.json').read_text())
    old_report=json.loads((work/'HISTORICAL_TXYZ.json').read_text())
    old={Path(r['file']).stem:r for r in old_report['records'] if r['method']=='official'}
    assert len(rows)==232 and all(r['role'] in ['TRAIN','VAL'] for r in rows)
    indices=json.loads((assets/'runs/r31_diagnosis_pilot_v1/txyz/CAMERA_A_FIT_INDICES.json').read_text())
    ix={r['file']:r for r in indices}
    faces=np.load(assets/'original_assets/official/faces.npy')
    anchor_path=assets/'runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz'
    anchors=np.load(anchor_path)
    assert hashlib.sha256(anchors['face_index'].tobytes()).hexdigest()=='288d658dfc791fae63e81b704170b678d8e9c68f199e5b9bdb84229f3e095b0c'
    assert hashlib.sha256(anchors['barycentric'].tobytes()).hexdigest()=='23054af1ce137268a516d30c25b1c7f27f1fbf87e59080fa1c9f060b7cdbac56'
    for rec in receipt['records']:
        key=rec['key'];p=assets/'original_assets/inputs'/(key+'.npz')
        assert sha(p)==rec['compact_sha256']
        assert np.array_equal(np.load(p)['source_indices'],ix[key]['indices'])
        assert sha(assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))==rec['heldout_sha256']
        assert sha(assets/'original_assets/official'/(key+'.npz'))==rec['official_sha256']
    heldout=assets/'datasets/heldout/humman_r3_k1_v1/MANIFEST.json'
    assert sha(heldout)==old_report['heldout_manifest_sha256']
    for ck in receipt['checkpoint_receipts']:
        cell=ck['cell'];directory=assets/'r4/formal'/cell/'real'
        model_report=json.loads((directory/'HUMMAN_RESULTS.json').read_text())
        assert ck['best_checkpoint_sha256']==model_report['checkpoint_sha256']
        assert np.array_equal(np.load(directory/'faces.npy'),faces)
        assert len(list(directory.glob('*.npz')))==232
        for key,h in ck['predictions_sha256'].items():assert sha(directory/(key+'.npz'))==h
    (work/'ASSET_PREFLIGHT.json').write_text(json.dumps(dict(status='PASS',frames=232,models=6,anchor_sha256=sha(anchor_path),
        heldout_manifest_sha256=sha(heldout),all_actual_samples_and_native_predictions_hashed=True,test_read=False),indent=2))
    (work/'regions').mkdir(exist_ok=True)
    smoke=[r for r in rows if r['identity']=='p001196'][:2]+[r for r in rows if r['identity']=='p001194'][:1]+[r for r in rows if r['identity']=='p001199'][:1]
    assert len(smoke)==4
    checked=[]
    for row in smoke:
        key=f"{row['sequence']}_{row['frame']:06d}";region_worker((str(work),key))
        r=worker((str(work),'official',key,row));checked.append(check_official(r,old,work))
    (work/'SMALL_CONSISTENCY.json').write_text(json.dumps(dict(status='PASS',records=checked,tolerances=dict(translation_m=1e-9,mesh_m=1e-9,metrics=1e-6)),indent=2))
    print('SMALL_OFFICIAL_CONSISTENCY_PASS',checked,flush=True)
    records=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        # Independent regional reporting is frozen before comparing the models.
        list(pool.map(region_worker,[(str(work),f"{r['sequence']}_{r['frame']:06d}") for r in rows]))
        print('FROZEN_REGION_ASSIGNMENTS_COMPLETE',len(rows),flush=True)
        # The complete Official reproduction gate precedes any G0/G1 correction.
        tasks=[(str(work),'official',f"{r['sequence']}_{r['frame']:06d}",r) for r in rows]
        records=list(pool.map(worker,tasks))
        comparisons=[check_official(r,old,work) for r in records]
        (work/'OFFICIAL_REPRODUCTION_GATE.json').write_text(json.dumps(dict(status='PASS',records=comparisons,
            maximum_metric_error=max(x['metric_max_error'] for x in comparisons),fallback_count=sum(r['fallback'] for r in records)),indent=2))
        print('OFFICIAL_FULL_REPRODUCTION_PASS',len(records),flush=True)
        for cell in [f'{m}_seed{s}' for m in ['g0','g1'] for s in [11,23,37]]:
            tasks=[(str(work),cell,f"{r['sequence']}_{r['frame']:06d}",r) for r in rows]
            for i,result in enumerate(pool.map(worker,tasks)):
                records.append(result)
                if (i+1)%40==0:print('CELL_PROGRESS',cell,i+1,'/232',flush=True)
            (work/'PAIRED_RESULTS.json').write_text(json.dumps(summarize(records,f),indent=2))
            print('CELL_COMPLETE',cell,flush=True)
    report=summarize(records,f)
    assert len(records)==1624
    # Raw metrics are independently recomputed too: match R4 originals exactly.
    checks=[]
    for ck in receipt['checkpoint_receipts']:
        cell=ck['cell'];historic=json.loads((assets/'r4/formal'/cell/'real/HUMMAN_RESULTS.json').read_text())
        for role in ['TRAIN','VAL']:
            new=report['results'][cell]['before'][role]['identity_equal_mean'];old_metrics=historic['results'][role]['identity_equal_mean']
            err=max(abs(new[k]-old_metrics[k]) for k in METRICS)
            assert err<1e-6
            checks.append(dict(cell=cell,role=role,max_metric_error=err,status='PASS'))
    report['raw_R4_reproduction']=checks
    (work/'PAIRED_RESULTS.json').write_text(json.dumps(report,indent=2))
    (work/'EXECUTION_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',frame_method_metrics=3248,new_corrected_native_meshes=1624,
        train_frames=192,val_frames=40,test_read=False,B_optimized=False,training_run=False),indent=2))
    print('R41_COMPLETE',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--workers',type=int,default=6)
    a=p.parse_args();main(a)
