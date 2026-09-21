"""Formal BEHAVE FULL/UPPER/LOCAL_TORSO evaluation.

K0 supplies RGB, mask, depth and optimization. K1--K3 are evaluation only.
"""
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path
import cv2, numpy as np, torch
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

def crop_boxes(mask):
    y, x = np.where(mask > 127)
    x0, x1, y0, y1 = x.min(), x.max()+1, y.min(), y.max()+1
    w, h = x1-x0, y1-y0; H, W = mask.shape
    def b(a,b,c,d): return (max(0,round(x0+a*w)),max(0,round(y0+b*h)),min(W,round(x0+c*w)),min(H,round(y0+d*h)))
    return {'FULL':(0,0,W,H),'UPPER':b(.02,0,.98,.72),'LOCAL_TORSO':b(.20,.15,.80,.72)}

def historical_bbox(mask):
    y,x=np.where(mask>127)
    return (max(0,int(x.min()-25)),max(0,int(y.min()-25)),min(mask.shape[1]-1,int(x.max()+25)),min(mask.shape[0]-1,int(y.max()+25)))

def mask_rgb(rgb, mask, box, value=128):
    out=np.full_like(rgb,value); x0,y0,x1,y1=box; out[y0:y1,x0:x1]=rgb[y0:y1,x0:x1]; out[mask<=127]=value; return out

def read_camera(calibs, sequence, kid):
    date=sequence.split('_',1)[0]; ip=calibs/'intrinsics'/str(kid)/'calibration.json'; ep=calibs/date/'config'/str(kid)/'config.json'
    c=json.loads(ip.read_text())['color']; e=json.loads(ep.read_text())
    K=np.array([[c['fx'],0,c['cx']],[0,c['fy'],c['cy']],[0,0,1]],np.float32)
    return {'K':K,'dist':np.asarray(c['opencv'][4:],np.float32),'R':np.asarray(e['rotation'],float).reshape(3,3),'t':np.asarray(e['translation'],float)}

def world_to_local(v, camera):
    return (np.asarray(v)-camera['t']) @ camera['R']

def transform(v, src, dst):
    # BEHAVE official contract: local2world = points @ R.T + t.
    w=np.asarray(v) @ src['R'].T + src['t']
    return (w-dst['t']) @ dst['R']

def depth_points(depth, mask, table, box=None):
    good=(depth>0)&(mask>127)
    if box is not None:
        x0,y0,x1,y1=box; keep=np.zeros_like(good); keep[y0:y1,x0:x1]=1; good &= keep
    r=np.dstack([table,np.ones(table.shape[:2],table.dtype)])
    return r[good].astype(np.float32)*depth[good,None].astype(np.float32)/1000

def fit_txyz(points, anchors):
    t=np.zeros(3); trace=[]
    for i in range(TXYZ_ITERS):
        dist,near=cKDTree(anchors+t).query(points,workers=-1); keep=dist<=np.quantile(dist,1-TRIM)
        step=np.clip(np.median(points[keep]-(anchors+t)[near[keep]],axis=0),-TXYZ_STEP,TXYZ_STEP); t+=step
        trace.append({'iteration':i+1,'step_m':step.tolist(),'t_m':t.tolist()})
    return t,trace

def stats(x):
    x=np.asarray(x)*1000
    return {'count':int(len(x)),'mean_mm':float(x.mean()),'median_mm':float(np.median(x)),'p90_mm':float(np.percentile(x,90)),'p95_mm':float(np.percentile(x,95)),'coverage_50mm':float(np.mean(x<=50))}

def effective_k(K, box, size=(512,512)):
    x0,y0,x1,y1=box; sx,sy=size[0]/(x1-x0),size[1]/(y1-y0); k=K.copy(); k[0,0]*=sx;k[1,1]*=sy;k[0,2]=(k[0,2]-x0)*sx;k[1,2]=(k[1,2]-y0)*sy; return k

def metric(points, verts, faces, fn): return stats(fn(points,verts,faces))

def deterministic_sample(points, n, key):
    if len(points) <= n: return points
    seed=int(hashlib.sha256(key.encode()).hexdigest()[:16],16); rng=np.random.default_rng(seed)
    return points[np.sort(rng.choice(len(points), n, replace=False))]

def save(path, rgb):
    path.parent.mkdir(parents=True,exist_ok=True); cv2.imwrite(str(path),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))

def ply_surface(path):
    import trimesh
    m=trimesh.load(path,process=False); return np.asarray(m.vertices,float),np.asarray(m.faces,np.int64)

def main():
    ap=argparse.ArgumentParser()
    for n in ('manifest','sequences','calibs','sam-repo','checkpoint','mhr','anchors','surface-metrics','out','reference-root'): ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--max-frames',type=int); args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(args.manifest.read_text()); all_specs=manifest.get('rows', manifest.get('behave', [])); specs=all_specs[:args.max_frames] if args.max_frames else all_specs
    sys_paths=[str(args.sam_repo),str(args.surface_metrics.parent)]; import sys;sys.path[:0]=sys_paths
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    from surface_metrics import point_to_triangle_distances
    model,cfg=load_sam_3d_body(str(args.checkpoint),device='cuda',mhr_path=str(args.mhr)); model.eval(); est=SAM3DBodyEstimator(model,cfg); faces=model.head_pose.faces.cpu().numpy().astype(np.int64)
    az=np.load(args.anchors); fi,bc=az['face_index'],az['barycentric'].astype(float)
    rows=[]; ref_audit=[]
    for si,spec in enumerate(specs):
        sid=f"{spec['subject']}/{spec['sequence']}/{spec['frame']}"; frame=args.sequences/spec['sequence']/spec['frame']; cams=[read_camera(args.calibs,spec['sequence'],k) for k in range(4)]
        rgb=cv2.cvtColor(cv2.imread(str(frame/'k0.color.jpg')),cv2.COLOR_BGR2RGB); depth=cv2.imread(str(frame/'k0.depth.png'),-1); mask=cv2.imread(str(frame/'k0.person_mask.jpg'),0); table=np.load(args.calibs/'intrinsics'/'0'/'pointcloud_table.npy');
        refv,reff=ply_surface(frame/'person'/'fit02'/'person_fit.ply'); ref_local=[world_to_local(refv,cams[k]) for k in range(4)]
        ref_audit.append({'id':sid,'reference_vertices':len(refv),'reference_faces':len(reff),'k0_bounds_m':np.vstack([ref_local[0].min(0),ref_local[0].max(0)]).tolist()})
        for cond,box in crop_boxes(mask).items():
            x0,y0,x1,y1=box; rgbc=rgb if cond=='FULL' else mask_rgb(rgb,mask,box); K=cams[0]['K']; pts=depth_points(depth,mask,table,box)
            if len(pts)>O2_OBSERVED_POINTS:
                rng=np.random.default_rng(int(hashlib.sha256((sid+'observed').encode()).hexdigest()[:16],16)); pts=pts[np.sort(rng.choice(len(pts),O2_OBSERVED_POINTS,replace=False))]
            bbox=np.array([historical_bbox(mask)],np.float32); batch=recursive_to(prepare_batch(rgbc,est.transform,bbox,None,None),'cuda'); batch['cam_int']=torch.as_tensor(K[None],device='cuda').to(batch['img']); model._initialize_batch(batch)
            with torch.inference_mode(): pred=model.forward_step(batch,decoder_type='body')['mhr']
            official=(pred['pred_vertices']+pred['pred_cam_t'][:,None])[0].detach(); vo=official.cpu().numpy(); anchors=(vo[faces[fi]]*bc[:,:,None]).sum(1); txyz,trace=fit_txyz(pts,anchors); applied=txyz if np.linalg.norm(txyz)<=TOTAL_TXYZ else np.zeros(3); vt=vo+applied
            # O2 is initialized from M1 and optimizes only translation, global_rot and body_pose.
            head=model.head_pose; base={k:pred[k].detach().clone() for k in ('global_rot','body_pose','shape','scale','hand','face','pred_cam_t')}; base['pred_cam_t']=base['pred_cam_t']+torch.as_tensor(applied,device='cuda')[None]
            def forward(d):
                v=head.mhr_forward(global_trans=torch.zeros_like(d['global_rot']),global_rot=d['global_rot'],body_pose_params=d['body_pose'],hand_pose_params=d['hand'],scale_params=d['scale'],shape_params=d['shape'],expr_params=d['face'])[0]; v=v.clone(); v[...,1:3]*=-1; return v+d['pred_cam_t'][:,None]
            d={k:v.clone() for k,v in base.items()}; d['pred_cam_t'].requires_grad_(True); d['global_rot'].requires_grad_(True); d['body_pose'].requires_grad_(True); opt=torch.optim.Adam([{'params':[d['pred_cam_t']],'lr':O2_LR_TRANSLATION},{'params':[d['global_rot'],d['body_pose']],'lr':O2_LR_POSE}]); obs=torch.as_tensor(pts,device='cuda'); history=[]
            anchor_pick=torch.arange(0,len(fi),O2_ANCHOR_STRIDE,device='cuda')
            for it in range(O2_ITERS):
                opt.zero_grad(); vv=forward(d); anc=(vv[0][torch.as_tensor(faces[fi],device='cuda').long()]*torch.as_tensor(bc,device='cuda',dtype=vv.dtype)[:,:,None]).sum(1)[anchor_pick]; _,near_np=cKDTree(anc.detach().float().cpu().numpy()).query(obs.detach().float().cpu().numpy(),workers=-1); near=torch.as_tensor(near_np,device='cuda',dtype=torch.long); res=torch.linalg.norm(obs.float()-anc[near].float(),dim=1); cut=torch.quantile(res,.8); keep=res<=cut; loss=torch.nn.functional.smooth_l1_loss(res[keep],torch.zeros_like(res[keep]),beta=O2_HUBER_BETA)+O2_LAMBDA_TRANSLATION*(d['pred_cam_t']-base['pred_cam_t']).square().mean()+O2_LAMBDA_POSE*((d['global_rot']-base['global_rot']).square().mean()+(d['body_pose']-base['body_pose']).square().mean()); loss.backward();opt.step();history.append(float(loss.detach()))
            vp=forward(d).detach()[0].cpu().numpy()
            methods={'Official':vo,'Txyz':vt,'T+Pose':vp}; evals={}
            for method,v in methods.items():
                cams_eval={}
                for k in range(4):
                    vk=v if k==0 else transform(v,cams[0],cams[k]); pk=depth_points(cv2.imread(str(frame/f'k{k}.depth.png'),-1),cv2.imread(str(frame/f'k{k}.person_mask.jpg'),0),np.load(args.calibs/'intrinsics'/str(k)/'pointcloud_table.npy')); pk=deterministic_sample(pk,5000,sid+'sensor'+str(k)); ref_sample=deterministic_sample(ref_local[k],2000,sid+'reference'+str(k)); cams_eval[f'K{k}']={'sensor':metric(pk,vk,faces,point_to_triangle_distances),'reference':metric(ref_sample,vk,faces,point_to_triangle_distances)}
                evals[method]=cams_eval
            row={'spec':spec,'condition':cond,'crop_box':list(box),'input_points':len(pts),'methods':evals,'txyz_m':txyz.tolist(),'txyz_trace':trace,'txyz_fallback':bool(np.linalg.norm(txyz)>TOTAL_TXYZ),'o2_final_loss':history[-1],'o2_initial_loss':history[0],'o2_translation_delta_m':(d['pred_cam_t'].detach()[0].cpu().numpy()-base['pred_cam_t'].detach()[0].cpu().numpy()).tolist(),'o2_global_rot':d['global_rot'].detach()[0].cpu().numpy().tolist(),'o2_body_pose':d['body_pose'].detach()[0].cpu().numpy().tolist()}
            out_frame=args.out/'raw'/spec['subject']/spec['sequence']/spec['frame']; out_frame.mkdir(parents=True,exist_ok=True)
            pred_cam=pred['pred_cam_t'].detach()[0].cpu().numpy(); txyz_cam=pred_cam+np.asarray(applied); pose_cam=d['pred_cam_t'].detach()[0].cpu().numpy()
            base_rot=base['global_rot'].detach()[0].cpu().numpy(); base_body=base['body_pose'].detach()[0].cpu().numpy(); pose_rot=d['global_rot'].detach()[0].cpu().numpy(); pose_body=d['body_pose'].detach()[0].cpu().numpy()
            np.savez_compressed(out_frame/f'{cond}_vertices.npz',Official=vo,Txyz=vt,T_pose=vp,faces=faces,Official_cam_t=pred_cam,Txyz_cam_t=txyz_cam,T_pose_cam_t=pose_cam,Official_global_rot=base_rot,Txyz_global_rot=base_rot,T_pose_global_rot=pose_rot,Official_body_pose=base_body,Txyz_body_pose=base_body,T_pose_body_pose=pose_body)
            (out_frame/f'{cond}.json').write_text(json.dumps(row,indent=2)+'\n'); rows.append(row); print(si+1,len(specs),sid,cond,flush=True)
    (args.out/'report').mkdir(exist_ok=True); (args.out/'report'/'per_frame_results.json').write_text(json.dumps(rows,indent=2)+'\n'); (args.out/'report'/'reference_coordinate_audit.json').write_text(json.dumps(ref_audit,indent=2)+'\n')
    print(json.dumps({'status':'COMPLETE','frames':len(specs),'conditions':3,'methods':3,'out':str(args.out)}))

if __name__=='__main__':main()
