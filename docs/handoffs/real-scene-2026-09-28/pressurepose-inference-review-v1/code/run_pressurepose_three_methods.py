#!/usr/bin/env python3
"""Single-view PressurePose inference and depth-fit comparison; no training."""
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path

import cv2
import numpy as np
import torch
from scipy.spatial import cKDTree

TOTAL_TXYZ = 0.17788820176363325
TXYZ_STEP = 0.05
TXYZ_ITERS = 6
TRIM = 0.20
O2_ITERS = 25
O2_OBSERVED_POINTS = 1024
O2_ANCHOR_STRIDE = 2
O2_HUBER_BETA = 0.02
O2_LR_TRANSLATION = 0.003
O2_LR_POSE = 0.001
O2_LAMBDA_TRANSLATION = 0.01
O2_LAMBDA_POSE = 0.01
EVAL_POINTS = 10000


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()


def fit_txyz(points: np.ndarray, anchors: np.ndarray):
    t=np.zeros(3); trace=[]
    for i in range(TXYZ_ITERS):
        dist,near=cKDTree(anchors+t).query(points,workers=-1)
        keep=dist<=np.quantile(dist,1-TRIM)
        step=np.clip(np.median(points[keep]-(anchors+t)[near[keep]],axis=0),-TXYZ_STEP,TXYZ_STEP)
        t+=step; trace.append({'iteration':i+1,'step_m':step.tolist(),'t_m':t.tolist()})
    return t,trace


def sample_points(points: np.ndarray, n: int, key: str):
    if len(points)<=n: return points
    seed=int(hashlib.sha256(key.encode()).hexdigest()[:16],16)
    rng=np.random.default_rng(seed)
    return points[np.sort(rng.choice(len(points),n,replace=False))]


def overlay_mesh(rgb, vertices, faces, K, render_depth):
    h,w=rgb.shape[:2]
    dep=render_depth(vertices,faces,K,h,w)
    mask=dep>0
    out=rgb.copy()
    tint=np.array([255,70,160],np.float32)
    out[mask]=np.clip(.58*out[mask].astype(np.float32)+.42*tint,0,255).astype(np.uint8)
    contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(out,contours,-1,(30,255,80),2)
    return out,dep


def optimize_pose(model, pred, applied_txyz, points, fi, bary, faces, device, key):
    head=model.head_pose
    def tensor(x,dtype=torch.float32): return torch.as_tensor(np.asarray(x),device=device,dtype=dtype)
    base={
        'pred_cam_t': tensor(pred['pred_cam_t'])[None]+tensor(applied_txyz)[None],
        'global_rot': tensor(pred['global_rot'])[None],
        'body_pose': tensor(pred['body_pose_params'])[None],
        'shape': tensor(pred['shape_params'])[None],
        'scale': tensor(pred['scale_params'])[None],
        'hand': tensor(pred['hand_pose_params'])[None],
        'face': tensor(pred['expr_params'])[None],
    }
    def forward(d):
        v=head.mhr_forward(global_trans=torch.zeros_like(d['global_rot']),global_rot=d['global_rot'],
                           body_pose_params=d['body_pose'],hand_pose_params=d['hand'],
                           scale_params=d['scale'],shape_params=d['shape'],expr_params=d['face'])[0]
        v=v.clone(); v[...,1:3]*=-1
        return v+d['pred_cam_t'][:,None]
    d={k:v.detach().clone() for k,v in base.items()}
    for k in d: d[k].requires_grad_(k in ('pred_cam_t','global_rot','body_pose'))
    opt=torch.optim.Adam([{'params':[d['pred_cam_t']],'lr':O2_LR_TRANSLATION},
                          {'params':[d['global_rot'],d['body_pose']],'lr':O2_LR_POSE}])
    obs_all=sample_points(points,O2_OBSERVED_POINTS,key+'-o2-observed')
    obs=tensor(obs_all)
    tri=tensor(faces[np.asarray(fi,np.int64)],torch.long)
    bc=tensor(bary)
    pick=torch.arange(0,len(fi),O2_ANCHOR_STRIDE,device=device)
    history=[]
    for it in range(O2_ITERS):
        opt.zero_grad(set_to_none=True); vv=forward(d)
        anc=(vv[0][tri]*bc[:,:,None]).sum(1)[pick]
        _,near_np=cKDTree(anc.detach().float().cpu().numpy()).query(obs.detach().float().cpu().numpy(),workers=-1)
        near=torch.as_tensor(near_np,device=device,dtype=torch.long)
        res=torch.linalg.norm(obs.float()-anc[near].float(),dim=1)
        cut=torch.quantile(res,.8); keep=res<=cut
        loss=torch.nn.functional.smooth_l1_loss(res[keep],torch.zeros_like(res[keep]),beta=O2_HUBER_BETA)
        loss=loss+O2_LAMBDA_TRANSLATION*(d['pred_cam_t']-base['pred_cam_t']).square().mean()
        loss=loss+O2_LAMBDA_POSE*((d['global_rot']-base['global_rot']).square().mean()+(d['body_pose']-base['body_pose']).square().mean())
        loss.backward();opt.step();history.append(float(loss.detach()))
    with torch.no_grad(): final=forward(d)[0].cpu().numpy()
    state={k:v.detach()[0].cpu().numpy() for k,v in d.items()}
    return final,state,history,obs_all


def main():
    ap=argparse.ArgumentParser()
    for name in ('raw','bbox-manifest','calibration','sam-repo','checkpoint','mhr','anchors','anchor-manifest','surface-metrics','out'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--max-frames',type=int)
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    bbox=json.loads(args.bbox_manifest.read_text()); bboxes={r['subject']:r for r in bbox['entries']}
    cal=json.loads(args.calibration.read_text()); calibrations={r['subject']:r for r in cal['rows']}
    anchor_meta=json.loads(args.anchor_manifest.read_text())
    anchor_file=args.anchors
    asset_hashes={'checkpoint_sha256':digest(args.checkpoint),'mhr_sha256':digest(args.mhr),
                  'anchors_sha256':digest(anchor_file),'surface_metrics_sha256':digest(args.surface_metrics),
                  'sam_repo_head':None}
    expected=anchor_meta['topology']
    if asset_hashes['checkpoint_sha256']!=expected['official_checkpoint_sha256'] or asset_hashes['mhr_sha256']!=expected['mhr_asset_sha256']:
        raise RuntimeError('Frozen SAM/MHR asset hash mismatch')
    if asset_hashes['anchors_sha256']!=anchor_meta['binary_sha256']:
        raise RuntimeError('Frozen MHR anchor file hash mismatch')
    import sys
    sys.path[:0]=[str(args.sam_repo),str(args.surface_metrics.parent)]
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    from surface_metrics import point_to_triangle_distances,render_depth
    model,cfg=load_sam_3d_body(str(args.checkpoint),device='cuda',mhr_path=str(args.mhr)); model.eval()
    estimator=SAM3DBodyEstimator(model,cfg)
    faces=estimator.faces.astype(np.int64)
    face_hash=hashlib.sha256(faces.astype('<i8',copy=False).tobytes()).hexdigest()
    if face_hash!=expected['faces_sha256']:
        raise RuntimeError(f'Frozen MHR topology mismatch: {face_hash}')
    az=np.load(anchor_file);fi=az['face_index'];bary=az['barycentric'].astype(float)
    rows=[]; raw_files=sorted(args.raw.glob('S*/p_select.p'))
    if args.max_frames: raw_files=raw_files[:args.max_frames]
    for j,path in enumerate(raw_files,1):
        import pickle
        subject=path.parent.name; bbox_row=bboxes[subject]; c=calibrations[subject]
        d=pickle.load(open(path,'rb'),encoding='latin1'); idx=int(bbox_row['pose_index'])
        rgb=np.asarray(d['RGB'][idx],np.uint8); pc_world=np.asarray(d['pc'][idx],np.float64)
        R=np.asarray(c['R_world_to_camera'],float); C=np.asarray(c['camera_center_m'],float)
        points=(pc_world-C)@R.T
        K=np.asarray(c['K'],np.float32); box=np.asarray(bbox_row['bbox_xyxy'],np.float32)
        device='cuda:0'; cam_int=torch.as_tensor(K[None],device=device,dtype=torch.float32)
        started=time.perf_counter()
        outs=estimator.process_one_image(rgb,bboxes=box[None],cam_int=cam_int,inference_type='body')
        if len(outs)!=1: raise RuntimeError(f'{subject}: expected one person, got {len(outs)}')
        pred=outs[0]
        vo=np.asarray(pred['pred_vertices'],np.float32)+np.asarray(pred['pred_cam_t'],np.float32)[None]
        anchors=(vo[faces[fi]]*bary[:,:,None]).sum(1)
        txyz,trace=fit_txyz(points,anchors)
        fallback=bool(np.linalg.norm(txyz)>TOTAL_TXYZ); applied=np.zeros(3) if fallback else txyz
        vt=vo+applied[None]
        vp,state,history,o2_points=optimize_pose(model,pred,applied,points,fi,bary,faces,device,subject)
        eval_points=sample_points(points,EVAL_POINTS,subject+'-pressurepose-eval')
        variants={'Official':vo,'Official+Txyz':vt,'Official+Txyz+Pose':vp}
        method_stats={}
        for name,verts in variants.items():
            dist=point_to_triangle_distances(eval_points,verts,faces)*1000
            method_stats[name]={'metric':'K0 same-source person point cloud to mesh surface','n_eval_points':int(len(dist)),
                                'mean_mm':float(dist.mean()),'median_mm':float(np.median(dist)),
                                'p90_mm':float(np.percentile(dist,90)),'p95_mm':float(np.percentile(dist,95)),
                                'coverage_50mm':float(np.mean(dist<=50))}
        outdir=args.out/'subjects'/subject;outdir.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(outdir/'mesh_parameters.npz',faces=faces,
            Official_vertices=vo,Txyz_vertices=vt,TxyzPose_vertices=vp,
            Official_cam_t=np.asarray(pred['pred_cam_t']),Txyz_cam_t=np.asarray(pred['pred_cam_t'])+applied,
            TxyzPose_cam_t=state['pred_cam_t'],Official_global_rot=np.asarray(pred['global_rot']),
            Txyz_global_rot=np.asarray(pred['global_rot']),TxyzPose_global_rot=state['global_rot'],
            Official_body_pose=np.asarray(pred['body_pose_params']),Txyz_body_pose=np.asarray(pred['body_pose_params']),
            TxyzPose_body_pose=state['body_pose'],K=K,bbox_xyxy=box)
        visual={}
        for name,verts in variants.items():
            img,dep=overlay_mesh(rgb,verts,faces,K,render_depth)
            key={'Official':'Official','Official+Txyz':'Txyz','Official+Txyz+Pose':'TxyzPose'}[name]
            cv2.imwrite(str(outdir/f'{key}_overlay.png'),cv2.cvtColor(img,cv2.COLOR_RGB2BGR))
            visual[name]={'rendered_pixels':int((dep>0).sum())}
        elapsed=time.perf_counter()-started
        row={'subject':subject,'pose_type':'p_sel_prn','pose_index':idx,'rgb_shape':list(rgb.shape),
             'bbox_xyxy_from_projected_filtered_depth_pointcloud':box.astype(int).tolist(),
             'input_point_count':int(len(points)),'camera_intrinsics':K.tolist(),
             'camera_reconstruction_corner_rms_px':float(c['mat_corner_reprojection_rms_px']),
             'methods':method_stats,'txyz_raw_m':txyz.tolist(),'txyz_applied_m':applied.tolist(),
             'txyz_norm_m':float(np.linalg.norm(txyz)),'txyz_fallback':fallback,'txyz_trace':trace,
             'tpose_iterations':O2_ITERS,'tpose_initial_loss':history[0],'tpose_final_loss':history[-1],
             'tpose_translation_delta_from_txyz_m':(state['pred_cam_t']-(np.asarray(pred['pred_cam_t'])+applied)).tolist(),
             'tpose_global_rot':state['global_rot'].tolist(),'tpose_body_pose':state['body_pose'].tolist(),
             'tpose_optimization_points':int(len(o2_points)),'visualization':visual,
             'inference_and_eval_seconds':float(elapsed)}
        (outdir/'result.json').write_text(json.dumps(row,indent=2)+'\n')
        rows.append(row);print(f'[{j}/{len(raw_files)}] {subject} {json.dumps({k:round(v["median_mm"],2) for k,v in method_stats.items()})} txyz_fallback={fallback} elapsed={elapsed:.1f}s',flush=True)
    report={'schema':'PRESSUREPOSE_K0_THREE_METHOD_TEST_V1','status':'COMPLETE','training':False,
        'input_contract':'20 PressurePose p_select_prn RGB images; same depth-derived bbox, calibrated K0 and same official 3D depth point cloud for all branches',
        'evaluation_contract':'Same-source single-camera K0 pointcloud-to-mesh fit consistency; not independent sensor validation or ground-truth mesh accuracy',
        'methods':['Official','Official+Txyz','Official+Txyz+Pose'],'subjects':len(rows),
        'txyz_contract':{'total_bound_m':TOTAL_TXYZ,'step_m':TXYZ_STEP,'iterations':TXYZ_ITERS,'trim_fraction':TRIM},
        'tpose_contract':{'iterations':O2_ITERS,'observed_points':O2_OBSERVED_POINTS,'anchor_stride':O2_ANCHOR_STRIDE,
          'huber_beta_m':O2_HUBER_BETA,'lr_translation':O2_LR_TRANSLATION,'lr_pose':O2_LR_POSE,
          'lambda_translation':O2_LAMBDA_TRANSLATION,'lambda_pose':O2_LAMBDA_POSE},
        'assets':asset_hashes,'rows':rows}
    (args.out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'COMPLETE','subjects':len(rows),'out':str(args.out)},indent=2),flush=True)

if __name__=='__main__': main()
