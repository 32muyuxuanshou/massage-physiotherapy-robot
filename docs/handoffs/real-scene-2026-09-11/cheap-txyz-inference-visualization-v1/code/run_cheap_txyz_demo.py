"""Frozen Official SAM3D + Camera-A depth Txyz demo and visual report.

Depth never enters SAM3D. Camera B is evaluation-only.
"""
import argparse, csv, hashlib, json, sys, time
from pathlib import Path
import cv2, numpy as np, torch
from scipy.spatial import cKDTree

ANCHORS=16384; ITERATIONS=6; TRIM=0.20; STEP_BOUND_M=0.05; TOTAL_BOUND_M=0.17788820176363325

def h(path):
    x=hashlib.sha256();
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): x.update(b)
    return x.hexdigest()

def surface_anchors(v,f,fi,bc): return (v[f[fi]]*bc[:,:,None]).sum(1)
def robust_translation(points,anchors):
    t=np.zeros(3,np.float64); trace=[]
    for i in range(ITERATIONS):
        moved=anchors+t; dist,near=cKDTree(moved).query(points,workers=-1)
        q=float(np.quantile(dist,1-TRIM)); keep=dist<=q
        step=np.median(points[keep]-moved[near[keep]],axis=0); step=np.clip(step,-STEP_BOUND_M,STEP_BOUND_M); t+=step
        trace.append({'iteration':i+1,'step_m':step.tolist(),'translation_m':t.tolist(),'matched':int(len(dist)),'kept':int(keep.sum()),'trim_threshold_m':q})
        if np.linalg.norm(step)<1e-5: break
    return t,trace

def cam_to_world(p,R,T): return (p-T.reshape(1,3))@R
def world_to_cam(p,R,T): return p@R.T+T.reshape(1,3)
def fixed_idx(n,key,cap=5000):
    if n<=cap:return np.arange(n)
    seed=int(hashlib.sha256(key.encode()).hexdigest()[:16],16)
    return np.sort(np.random.default_rng(seed).choice(n,cap,False))

def metric(obs,verts,faces):
    pts=obs[fixed_idx(len(obs),'metric',5000)]
    return point_to_triangle(pts,verts,faces)

def project(p,K):
    ok=p[:,2]>1e-5; p=p[ok]; uv=np.c_[K[0,0]*p[:,0]/p[:,2]+K[0,2],K[1,1]*p[:,1]/p[:,2]+K[1,2]]
    return uv,p[:,2]
def sparse_depth(p,K,H,W):
    uv,z=project(p,K); x=np.rint(uv[:,0]).astype(int); y=np.rint(uv[:,1]).astype(int); ok=(x>=0)&(x<W)&(y>=0)&(y<H)
    out=np.full((H,W),np.inf,np.float32); np.minimum.at(out,(y[ok],x[ok]),z[ok].astype(np.float32)); out[~np.isfinite(out)]=0
    return cv2.dilate(out,np.ones((5,5),np.uint8))
def depth_vis(points,K,H,W):
    d=sparse_depth(points,K,H,W); valid=d>0; out=np.zeros((H,W,3),np.uint8)
    if valid.any():
        lo,hi=np.quantile(d[valid],[.01,.99]); q=np.clip((d-lo)/(max(hi-lo,1e-6)),0,1); out=cv2.applyColorMap((255*(1-q)).astype(np.uint8),cv2.COLORMAP_TURBO); out[~valid]=[40,40,40]
    return out

def overlay(rgb,verts,faces,K,color):
    im=rgb.copy(); uv,z=project(verts,K); ok=(uv[:,0]>=0)&(uv[:,0]<im.shape[1])&(uv[:,1]>=0)&(uv[:,1]<im.shape[0]); uv=uv[ok].astype(int)
    for x,y in uv[::2]: cv2.circle(im,(x,y),1,color,-1,cv2.LINE_AA)
    return cv2.addWeighted(rgb,.62,im,.38,0)
def residual_img(obs,verts,K,H,W,scale_mm=100):
    do=sparse_depth(obs,K,H,W); dm=sparse_depth(verts,K,H,W); common=(do>0)&(dm>0); e=np.zeros((H,W),np.float32); e[common]=np.abs(do[common]-dm[common])*1000
    heat=cv2.applyColorMap(np.clip(e/scale_mm*255,0,255).astype(np.uint8),cv2.COLORMAP_TURBO); heat[~common]=[35,35,35]
    return heat,{'common_pixels':int(common.sum()),'coverage':float(common.sum()/max(1,(do>0).sum()))}
def write_obj(path,v,f):
    with open(path,'w') as o:
        for x in v:o.write(f'v {x[0]:.7f} {x[1]:.7f} {x[2]:.7f}\n')
        for x in f:o.write(f'f {x[0]+1} {x[1]+1} {x[2]+1}\n')
def viewer(path,obs,vo,vc,case):
    def arr(x,n=2200): return x[fixed_idx(len(x),case+str(len(x)),n)]
    po,p1,p2=arr(obs),arr(vo),arr(vc)
    html=f'''<!doctype html><meta charset="utf-8"><title>{case} 3D</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script><div id="v" style="width:100vw;height:96vh"></div><script>
const traces=[{{name:'Depth point cloud',mode:'markers',type:'scatter3d',x:{po[:,0].tolist()},y:{po[:,1].tolist()},z:{po[:,2].tolist()},marker:{{size:1,color:'#777'}}}},{{name:'Official',mode:'markers',type:'scatter3d',x:{p1[:,0].tolist()},y:{p1[:,1].tolist()},z:{p1[:,2].tolist()},marker:{{size:1,color:'#e34a33'}}}},{{name:'Corrected',mode:'markers',type:'scatter3d',x:{p2[:,0].tolist()},y:{p2[:,1].tolist()},z:{p2[:,2].tolist()},marker:{{size:1,color:'#2b8cbe'}}}}]; Plotly.newPlot('v',traces,{{title:'{case}: gray depth / red Official / blue Corrected',scene:{{aspectmode:'data'}}}});</script>'''
    path.write_text(html)

def save_png(path,im): cv2.imwrite(str(path),cv2.cvtColor(im,cv2.COLOR_RGB2BGR) if im.ndim==3 else im)
def main():
    ap=argparse.ArgumentParser();
    for n in ('sam-repo','official','mhr','manifest','anchors','out'): ap.add_argument('--'+n,required=True,type=Path)
    ap.add_argument('--limit',type=int,default=10); a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(a.sam_repo),'/raid5/xuhd/rgbd_mesh_system_v1']; global point_to_triangle; from surface_metrics import point_to_triangle; from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    rows=json.loads(a.manifest.read_text())['rows'][:a.limit]
    model,cfg=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr)); model.eval(); est=SAM3DBodyEstimator(model,cfg); faces=model.head_pose.faces.cpu().numpy().astype(np.int64)
    az=np.load(a.anchors); fi=az['face_index']; bc=az['barycentric'].astype(float); results=[]
    for ri,r in enumerate(rows):
        case=r['id']; d=a.out/'visualizations'/f'case_{case}'; d.mkdir(parents=True,exist_ok=True)
        with np.load(r['path']) as z:
            rgb=z['rgb_a'].copy(); dep=z['depth_a'].copy(); mask=z['mask_color_a'].copy(); K=z['K_a'].copy(); obs=z['points_a'].astype(float); ob=z['points_b'].astype(float)
            torch.cuda.synchronize(); st=time.perf_counter(); batch=recursive_to(prepare_batch(rgb,est.transform,z['bbox_a'][None].astype(np.float32),None,None),'cuda'); batch['cam_int']=torch.as_tensor(K[None],device='cuda').to(batch['img']); model._initialize_batch(batch); pred=model.forward_step(batch,decoder_type='body')['mhr']; torch.cuda.synchronize(); sam_ms=(time.perf_counter()-st)*1000
            vo=(pred['pred_vertices']+pred['pred_cam_t'][:,None])[0].detach().cpu().numpy(); params={k:v.detach().cpu().numpy() for k,v in pred.items() if torch.is_tensor(v) and v.numel()<10000}
            anchors=surface_anchors(vo,faces,fi,bc); st=time.perf_counter(); raw,trace=robust_translation(obs,anchors); txyz_ms=(time.perf_counter()-st)*1000; fallback=np.linalg.norm(raw)>TOTAL_BOUND_M; applied=np.zeros(3) if fallback else raw; vc=vo+applied
            vb0=world_to_cam(cam_to_world(vo,z['R_a'],z['T_a']),z['R_b'],z['T_b']); vb1=world_to_cam(cam_to_world(vc,z['R_a'],z['T_a']),z['R_b'],z['T_b'])
            ma0,ma1=metric(obs,vo,faces),metric(obs,vc,faces); mb0,mb1=metric(ob,vb0,faces),metric(ob,vb1,faces)
            H,W=rgb.shape[:2]; ov0=overlay(rgb,vo,faces,K,(255,50,40)); ov1=overlay(rgb,vc,faces,K,(40,120,255)); ra0,ca0=residual_img(obs,vo,K,H,W); ra1,ca1=residual_img(obs,vc,K,H,W)
            save_png(d/'input_rgb.png',rgb); save_png(d/'input_depth.png',depth_vis(obs,K,H,W)); cv2.imwrite(str(d/'person_mask.png'),mask); save_png(d/'official_rgb_overlay.png',ov0); save_png(d/'corrected_rgb_overlay.png',ov1); save_png(d/'rgb_overlay_comparison.png',np.hstack([ov0,ov1])); save_png(d/'official_depth_residual.png',ra0); save_png(d/'corrected_depth_residual.png',ra1); save_png(d/'depth_residual_comparison.png',np.hstack([ra0,ra1]))
            rb0,cb0=residual_img(ob,vb0,z['K_b'],*z['rgb_b'].shape[:2]); rb1,cb1=residual_img(ob,vb1,z['K_b'],*z['rgb_b'].shape[:2]); save_png(d/'b_official_depth_residual.png',rb0); save_png(d/'b_corrected_depth_residual.png',rb1); save_png(d/'b_heldout_comparison.png',np.hstack([rb0,rb1]))
            canvas=np.full((360,640,3),255,np.uint8); vals=raw*1000; lines=[f'Tx = {vals[0]:+.1f} mm',f'Ty = {vals[1]:+.1f} mm',f'Tz = {vals[2]:+.1f} mm',f'|T| = {np.linalg.norm(vals):.1f} mm',f'fallback = {fallback}'];
            for j,s in enumerate(lines): cv2.putText(canvas,s,(30,60+j*48),cv2.FONT_HERSHEY_SIMPLEX,.9,(20,20,20),2,cv2.LINE_AA)
            cv2.arrowedLine(canvas,(320,290),(int(320+vals[0]),int(290-vals[1])),(20,80,220),4); cv2.imwrite(str(d/'txyz_summary.png'),canvas)
            write_obj(d/'official_mesh.obj',vo,faces); write_obj(d/'corrected_mesh.obj',vc,faces); viewer(d/'3d_viewer.html',obs,vo,vc,case); np.savez_compressed(d/'official_mhr_parameters.npz',**params)
            valid=dep[dep>0]; info={'id':case,'subject_id':r['subject_id'],'sequence':r.get('action',str(z['sequence'])),'frame':int(z['frame_id']),'pose_family':r.get('pose_family',r.get('action')),'source_path':r['path'],'source_sha256':h(r['path']),'Txyz_m':raw.tolist(),'applied_Txyz_m':applied.tolist(),'Tnorm_m':float(np.linalg.norm(raw)),'iterations':trace,'valid_depth_points':int(len(obs)),'trimmed_point_count_last':int(trace[-1]['matched']-trace[-1]['kept']),'fallback_reason':'CORRECTION_OUT_OF_RANGE' if fallback else None,'official_A':ma0,'corrected_A':ma1,'official_B':mb0,'corrected_B':mb1,'official_B_coverage':cb0['coverage'],'corrected_B_coverage':cb1['coverage'],'runtime_sam_ms':sam_ms,'runtime_txyz_ms':txyz_ms,'runtime_total_ms':sam_ms+txyz_ms,'depth_raw_mm':{'min_valid':float(valid.min()) if len(valid) else None,'median':float(np.median(valid)) if len(valid) else None,'p95':float(np.quantile(valid,.95)) if len(valid) else None,'max_valid':float(valid.max()) if len(valid) else None},'fallback':bool(fallback)}
            info['outcome_class']='FALLBACK' if fallback else ('SMALL_CORRECTION' if np.linalg.norm(raw)<.03 else ('LARGE_CORRECTION' if np.linalg.norm(raw)>.12 else 'USEFUL_CORRECTION'))
            (d/'metrics.json').write_text(json.dumps(info,indent=2)+'\n'); results.append(info); print(ri+1,len(rows),case,info['outcome_class'],np.linalg.norm(raw)*1000,mb0['median_mm'],mb1['median_mm'],flush=True)
    (a.out/'raw_results.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__': main()

