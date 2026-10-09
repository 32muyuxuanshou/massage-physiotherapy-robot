"""Mechanical camera/body swaps on saved native meshes, never B fitting."""
import argparse,json,sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import numpy as np
from humman_geometry import transform_camera
from evaluate_r3_humman import aggregate_real


def one(task):
    root,base,new,key,faces_path,metric_path=task;root=Path(root)
    sys.path.insert(0,metric_path)
    from surface_metrics import point_to_triangle_distances
    a=np.load(Path(base)/(key+'.npz'));b=np.load(Path(new)/(key+'.npz'));faces=np.load(faces_path)
    points=np.load(root/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
    rows=json.loads((root/'datasets/cache/humman_development_v1/CACHE_MANIFEST.json').read_text())['records']
    row=next(r for r in rows if Path(r['cache_file']).stem==key)
    aa=np.load(root/'datasets/registered_v1'/row['views']['kinect_000']['file']);bb=np.load(root/'datasets/registered_v1'/row['views']['kinect_001']['file'])
    delta=(b['pred_cam_t']-a['pred_cam_t']).reshape(3)
    meshes={'g0':a['vertices_camera_A'],'g1':b['vertices_camera_A'],
        'g0_body_g1_camera':a['vertices_camera_A']+delta,'g1_body_g0_camera':b['vertices_camera_A']-delta}
    out={}
    for method,vc in meshes.items():
        vb=transform_camera(vc,{k:aa[k] for k in ['R','T']},{k:bb[k] for k in ['R','T']})
        distance=point_to_triangle_distances(points,vb,faces)*1000
        out[method]=dict(identity=row['identity'],role=row['role'],sequence=row['sequence'],frame=row['frame'],
            triangle=dict(median_mm=float(np.median(distance)),p95_mm=float(np.quantile(distance,.95)),coverage_50mm=float((distance<=50).mean())))
    changes=dict(camera_delta_xyz_mm=(delta*1000).tolist(),camera_delta_norm_mm=float(np.linalg.norm(delta)*1000),
        native_body_corresponding_mean_change_mm=float(np.linalg.norm((b['vertices_camera_A']-b['pred_cam_t'].reshape(3))-(a['vertices_camera_A']-a['pred_cam_t'].reshape(3)),axis=1).mean()*1000))
    return dict(key=key,metrics=out,changes=changes)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--base',type=Path,required=True)
    p.add_argument('--new',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rows=json.loads((a.root/'datasets/cache/humman_development_v1/CACHE_MANIFEST.json').read_text())['records'];assert all(r['role']!='TEST' for r in rows)
    metric=str(a.root/'project_snapshot/docs/handoffs/real-scene-2026-09-09/public-rgbd-surface-finetuning-pilot-v1/code')
    tasks=[(str(a.root),str(a.base),str(a.new),Path(r['cache_file']).stem,str(a.base/'faces.npy'),metric) for r in rows]
    with ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('spawn')) as pool:records=list(pool.map(one,tasks))
    report=dict(status='SAVED_OUTPUT_CAMERA_BODY_SWAPS_COMPLETE',test_read=False,B_fitted=False,
        interpretation='output components mechanically swapped; not causal training decomposition, no true Camera/MHR/anatomy labels',records=records,
        results={method:{role:aggregate_real([r['metrics'][method] for r in records if r['metrics'][method]['role']==role]) for role in ['TRAIN','VAL']} for method in records[0]['metrics']})
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2));print('ATTRIBUTION_COMPLETE',flush=True)
