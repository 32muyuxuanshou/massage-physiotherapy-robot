"""TRAIN/VAL-only real transfer, K000 inputs; K001 held-out sensor evidence."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys
import numpy as np
import torch
from fusion import RGBDBodyAdapter
from humman_geometry import transform_camera
from r3_common import load_official,read_cache,combine,cached_forward,sha
from render_losses import MeshRenderer


def sample_points(root,out):
    data=root/'datasets/registered_v1';manifest=json.loads((data/'FRAME_MANIFEST_V1.json').read_text())
    out.mkdir(parents=True,exist_ok=False);records=[]
    for row in manifest['records']:
        if row['role']=='TEST':continue
        source=data/row['views']['kinect_001']['file']
        with np.load(source) as z:points=z['points_color']
        seed=int(hashlib.sha256(f"R3_HUMMAN_K1:{row['sequence']}:{row['frame']}".encode()).hexdigest()[:8],16)
        index=np.random.default_rng(seed).choice(len(points),min(2048,len(points)),replace=False)
        name=f"{row['sequence']}_{row['frame']:06d}.npz"
        np.savez_compressed(out/name,points_camera_B=points[index],source_indices=index)
        records.append(dict(sequence=row['sequence'],frame=row['frame'],identity=row['identity'],role=row['role'],
            file=name,source_file=str(source),source_sha256=sha(source),sample_sha256=sha(out/name),points=len(index)))
    report=dict(status='FROZEN_PRE_MODEL_HELDOUT_POINTS_NO_TEST',camera='kinect_001',sampling='2048 fixed seeded points; shared across every model/seed',
                records=records,counts={r:sum(x['role']==r for x in records) for r in ['TRAIN','VAL']})
    (out/'MANIFEST.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)


def triangle_worker(task):
    mesh_path,points_path,faces_path,metric_root=task
    sys.path.insert(0,metric_root)
    from surface_metrics import point_to_triangle_distances
    vertices=np.load(mesh_path)['vertices_camera_B'];points=np.load(points_path)['points_camera_B'];faces=np.load(faces_path)
    distance=point_to_triangle_distances(points,vertices,faces)*1000
    return dict(median_mm=float(np.median(distance)),p95_mm=float(np.quantile(distance,.95)),mean_mm=float(distance.mean()),
                coverage_50mm=float((distance<=50).mean()),point_count=len(distance),max_mm=float(distance.max()))


def aggregate_real(records):
    groups={}
    for identity in sorted({r['identity'] for r in records}):
        rr=[r for r in records if r['identity']==identity];sequences={}
        for seq in sorted({r['sequence'] for r in rr}):
            ss=[r for r in rr if r['sequence']==seq]
            sequences[seq]={k:float(np.mean([r['triangle'][k] for r in ss])) for k in ['median_mm','p95_mm','coverage_50mm']}
        groups[identity]=dict(sequences=sequences,metrics={k:float(np.mean([r[k] for r in sequences.values()])) for k in ['median_mm','p95_mm','coverage_50mm']})
    return dict(identity_equal_mean={k:float(np.mean([r['metrics'][k] for r in groups.values()])) for k in ['median_mm','p95_mm','coverage_50mm']},per_identity=groups,records=records)


def evaluate(root,cache,points,out,checkpoint=None):
    out.mkdir(parents=True,exist_ok=False)
    rows=json.loads((cache/'CACHE_MANIFEST.json').read_text())['records'];assert all(r['role']!='TEST' for r in rows)
    official,_=load_official(root)
    model=RGBDBodyAdapter(official,mode='residual' if checkpoint is None else torch.load(checkpoint,map_location='cpu',weights_only=False)['mode']).cuda()
    if checkpoint:model.fusion.load_state_dict(torch.load(checkpoint,map_location='cuda',weights_only=False)['fusion'])
    faces_path=out/'faces.npy';np.save(faces_path,official.head_pose.faces.cpu().numpy())
    renderer=MeshRenderer(official.head_pose.faces,1080,1920)
    records=[];tasks=[]
    metric_root=str(root/'project_snapshot/docs/handoffs/real-scene-2026-09-09/public-rgbd-surface-finetuning-pilot-v1/code')
    raw=root/'datasets/registered_v1'
    with torch.no_grad():
        for i,row in enumerate(rows):
            name=row['cache_file'].removesuffix('.pt');rec=read_cache(str(cache/row['cache_file']))
            b,feature,d,valid,rays,*_=combine([rec]);o=cached_forward(model,b,feature,d,valid,rays)
            with np.load(raw/row['views']['kinect_000']['file']) as a,np.load(raw/row['views']['kinect_001']['file']) as z:
                ca={k:a[k] for k in ['R','T']};cb={k:z[k] for k in ['R','T']};K=z['K']
            vertices=o['pred_vertices'][0].cpu().numpy()+o['pred_cam_t'][0].cpu().numpy()
            vb=transform_camera(vertices,ca,cb)
            path=out/(name+'.npz')
            np.savez_compressed(path,vertices_camera_A=vertices,vertices_camera_B=vb,
                **{k:o[k].cpu().numpy() for k in ['pred_cam_t','global_rot','body_pose','shape','scale']})
            observed=np.load(points/(name+'.npz'))['points_camera_B']
            rd,_=renderer(torch.from_numpy(vb[None]).float().cuda(),torch.from_numpy(K[None]).float().cuda())
            u=np.rint(K[0,0]*observed[:,0]/observed[:,2]+K[0,2]).astype(int)
            v=np.rint(K[1,1]*observed[:,1]/observed[:,2]+K[1,2]).astype(int)
            rendered=rd[0].cpu().numpy()[v,u];hit=rendered>0;res=np.abs(rendered[hit]-observed[hit,2])*1000
            records.append(dict(identity=row['identity'],sequence=row['sequence'],frame=row['frame'],role=row['role'],file=path.name,
                depth_common_median_mm=float(np.median(res)) if len(res) else None,
                depth_common_p95_mm=float(np.quantile(res,.95)) if len(res) else None,depth_hit_rate=float(hit.mean())))
            tasks.append((str(path),str(points/(name+'.npz')),str(faces_path),metric_root))
            if i%40==0:print('REAL_PREDICTED',i+1,'/',len(rows),flush=True)
    if hasattr(model,'remove_hooks'):model.remove_hooks()
    else:model._hook.remove()
    # Release GPU before the independent CPU triangle evaluation, allowing the
    # next training cell to proceed while held-out metrics finish in parallel.
    del model,official,renderer,o,b,feature,d,valid,rays,rd
    torch.cuda.empty_cache()
    (out/'GPU_STAGE_DONE.json').write_text(json.dumps(dict(status='GPU_PREDICTIONS_COMPLETE_CPU_METRICS_RUNNING',frames=len(rows))))
    with ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('spawn')) as pool:
        for row,result in zip(records,pool.map(triangle_worker,tasks)):
            row['triangle']=result
    summary={role:aggregate_real([r for r in records if r['role']==role]) for role in ['TRAIN','VAL']}
    report=dict(status='REAL_TRAIN_VAL_TRANSFER_COMPLETED_NO_TEST',checkpoint=str(checkpoint) if checkpoint else 'OFFICIAL',
        checkpoint_sha256=sha(checkpoint) if checkpoint else None,heldout_points_manifest_sha256=sha(points/'MANIFEST.json'),
        results=summary,primary='independent Camera B measured points to exact predicted mesh triangles',
        aggregation='Camera B -> frame -> equal sequence mean -> equal identity mean; TRAIN/VAL separate',
        limitations='Public K/R/T and released images used as-is; distortion coefficients absent. Clothing surface observations; not anatomical/acupoint ground truth. Official pretraining overlap unknown.')
    (out/'HUMMAN_RESULTS.json').write_text(json.dumps(report,indent=2));print('REAL_EVALUATION_COMPLETE',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--points',type=Path,required=True)
    p.add_argument('--cache',type=Path);p.add_argument('--out',type=Path);p.add_argument('--checkpoint',type=Path);p.add_argument('--freeze-points',action='store_true')
    a=p.parse_args()
    if a.freeze_points:sample_points(a.root,a.points)
    else:evaluate(a.root,a.cache,a.points,a.out,a.checkpoint)
