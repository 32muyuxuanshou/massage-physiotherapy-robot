"""Frozen BEHAVE cohort, K0-only fits, reference-only posterior patches.

Fresh refers only to newly recomputed Official initializations. All people were
previously consumed. Clothing patches are not skin or acupoint ground truth.
"""
import argparse, hashlib, json, os, platform, sys, time
from pathlib import Path
import cv2
import numpy as np
from scipy.spatial import cKDTree
from behave_v2_io import read_camera, transform_between, local_to_world
from run_cached_point_diagnostics import sha, read, write, save_csv

BASE = Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/delivery')
SAM = Path('/raid5/xuhd/sam3d_s01_pilot_20260906/sam-3d-body')
WEIGHTS = Path('/raid5/xuhd/sam3d_s01_pilot_20260906/weights')
ANCHORS = Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/run_assets/anchors.npz')
STATE_KEYS = {'pred_cam_t':'pred_cam_t','global_rot':'global_rot','body_pose':'body_pose_params',
              'shape':'shape_params','scale':'scale_params','hand':'hand_pose_params','face':'expr_params'}
METHODS = ['Official','Official+Txyz','Official+Txyz+Pose','Official+Rigid','Official+Rigid+D']


def token(method):
    return method.replace('+','_')


def identity(a):
    paths = [WEIGHTS/'model.ckpt', WEIGHTS/'assets/mhr_model.pt', ANCHORS,
             BASE/'EXPERIMENT_CONTRACT.json', a.root/'assets/candidate_posterior_mask.json',
             a.out/'BEHAVE_POSTERIOR_PATCH_ROI_FREEZE.json',
             a.out/'CAMERA_QA.json', a.out/'CLOUD_WORLD_VISUAL_QA.json',
             a.behave/'v2_3/report/BEHAVE_V2_FROZEN_TEST_MANIFEST.json']
    paths += sorted((BASE/'code').glob('*.py'))
    paths += [Path(__file__).parent/f for f in ['run_behave_rigid_d.py','behave_v2_io.py','run_cached_point_diagnostics.py']]
    paths += sorted(SAM.rglob('*.py'))
    for date in ['Date03','Date05','Date06','Date01']:
        paths += [a.behave/'data/calibs'/date/'config'/str(k)/'config.json' for k in range(4)]
    for k in range(4):
        paths += [a.behave/'data/calibs/intrinsics'/str(k)/f for f in ['calibration.json','pointcloud_table.npy']]
    files = {str(p):sha(p) for p in paths}
    old = read(BASE/'EXPERIMENT_CONTRACT.json')
    for key,p in [('checkpoint',WEIGHTS/'model.ckpt'),('mhr',WEIGHTS/'assets/mhr_model.pt'),('anchors',ANCHORS)]:
        assert files[str(p)] == old['historical_'+key+'_sha256']
    return files


def sample_idx(count,maximum,key):
    if count <= maximum:return np.arange(count,dtype=np.int64)
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:16],16)
    return np.sort(np.random.default_rng(seed).choice(count,maximum,False))


def cloud(depth,mask,table):
    pix = np.flatnonzero((depth>0)&(mask>127))
    rays = np.dstack([table,np.ones(depth.shape)])
    return rays.reshape(-1,3)[pix]*depth.reshape(-1)[pix,None]/1000.,pix


def prepare_frame(a,spec,rois):
    folder = a.behave/'data/sequences'/spec['sequence']/spec['frame']
    target = a.out/'inputs'/spec['sequence']/spec['frame'];target.mkdir(parents=True,exist_ok=True)
    records=[]
    for k in range(4):
        cam = read_camera(a.behave/'data/calibs',spec['sequence'],k)
        paths = [folder/f'k{k}.{ext}' for ext in ['color.jpg','depth.png','person_mask.jpg']]
        rgb = cv2.cvtColor(cv2.imread(str(paths[0])),cv2.COLOR_BGR2RGB)
        dep,mask = cv2.imread(str(paths[1]),-1),cv2.imread(str(paths[2]),0)
        points,pixels = cloud(dep,mask,cam['pointcloud_table']);assert len(points)>0
        roi = rois.get((spec['sequence'],spec['frame'],f'K{k}'))
        qualified = bool(roi and roi['evaluation_qualified'])
        if roi:
            patch_file = Path(roi['roi_path']);assert sha(patch_file)==roi['roi_sha256']
            patch = cv2.imread(str(patch_file),0)
            posterior = np.flatnonzero(patch.reshape(-1)[pixels]>0) if qualified else np.array([],np.int64)
        else:posterior=np.array([],np.int64)
        # Pure-data selection, performed before any new model result.
        key = spec['sequence']+'/'+spec['frame']+f'/K{k}/seed-0'
        eval_idx = sample_idx(len(points),1500,key+'/whole-person')
        post_idx = posterior[sample_idx(len(posterior),1500,key+'/posterior-patch')]
        y,x = np.where(mask>127)
        bbox = np.array([max(0,x.min()-25),max(0,y.min()-25),min(rgb.shape[1]-1,x.max()+25),min(rgb.shape[0]-1,y.max()+25)],np.float32)
        npz = target/f'K{k}.npz'
        np.savez_compressed(npz,rgb=rgb,K=cam['K'],dist=cam['dist'],points_m=points,original_flat_pixel_idx=pixels,
                            eval_idx=eval_idx,posterior_eval_idx=post_idx,bbox_xyxy=bbox,
                            R_local_to_world=cam['R_local_to_world'],t_local_to_world_m=cam['t_local_to_world_m'])
        records.append(dict(camera=f'K{k}',input_npz=str(npz),sha256=sha(npz),point_count=len(points),
                            posterior_point_count=len(post_idx),posterior_qualified=qualified,
                            original_files=[dict(path=str(p),sha256=sha(p)) for p in paths],
                            calibration=[dict(path=p,sha256=sha(Path(p))) for p in cam['provenance']],
                            reference_status=roi['posterior_visibility'] if roi else 'SMOKE_NO_POSTERIOR_REFERENCE'))
    write(target/'identity.json',dict(spec=spec,cameras=records,input='original RGB + historical mask bbox +/-25 + original K',
        fit='K0 full valid person cloud only; no K1/K2/K3 points enter fits',evaluation='same frozen indices shared by all five methods'))
    return records


def camera_qa(a,specs):
    sys.path.insert(0,str(a.behave/'behave-dataset'))
    from data.kinect_transform import KinectTransform
    rows=[]
    review=read(a.out/'CLOUD_WORLD_VISUAL_QA.json')
    assert review['model_outputs_seen']==0
    reviewed={r['sequence'] for r in review['rows'] if r['world_cloud_visual_sanity']=='PASS'}
    for item in review['images']:assert sha(Path(item['path']))==item['sha256']
    for seq in sorted({r['sequence'] for r in specs}):
        seqroot=a.behave/'data/sequences'/seq
        official=KinectTransform(str(seqroot),no_intrinsics=True)
        cams=[read_camera(a.behave/'data/calibs',seq,k) for k in range(4)]
        pts=np.array([[0.,0.,1.],[.2,-.1,2.],[-.3,.25,3.]])
        comparisons=[]
        for k in [1,2,3]:
            q=transform_between(pts,cams[0],cams[k])
            ref=official.world2local(official.local2world(pts,0),k)
            comparisons.append(float(np.abs(q-ref).max()))
        spec=next(r for r in specs if r['sequence']==seq)
        folder=a.out/'inputs'/seq/spec['frame'];world=[];projection=[]
        for k in range(4):
            z=np.load(folder/f'K{k}.npz');p=z['points_m'][z['eval_idx']];world.append(local_to_world(p,cams[k]))
            uv=cv2.projectPoints(p[:,None],np.zeros(3),np.zeros(3),cams[k]['K'],cams[k]['dist'])[0].reshape(-1,2)
            flat=z['original_flat_pixel_idx'][z['eval_idx']];h,w=z['rgb'].shape[:2]
            projection.append(float(np.percentile(np.linalg.norm(uv-np.c_[flat%w,flat//w],axis=1),95)))
        overlap=[]
        for k in [1,2,3]:
            overlap.append(float((np.median(cKDTree(world[k]).query(world[0])[0])+np.median(cKDTree(world[0]).query(world[k])[0]))/2))
        rows.append(dict(sequence=seq,official_comparison_max_m=comparisons,world_cloud_symmetric_median_m=overlap,
                         distorted_color_reprojection_p95_px=projection,
                         transform_pass=max(comparisons)<1e-9,reprojection_pass=max(projection)<.01,
                         whole_cloud_20cm_warning=max(overlap)>=.20,
                         world_cloud_visual_sanity_pass=seq in reviewed))
    return dict(status='PASS' if all(r['transform_pass'] and r['reprojection_pass'] and r['world_cloud_visual_sanity_pass'] for r in rows) else 'FAIL',rows=rows,
        pre_model_qa_revision='Whole-body nearest-surface median is diagnostic, not a calibration gate: opposite views observe different surfaces and retain depth outliers. Official transform + color reprojection + visual world cloud sanity required.',
        world_cloud_review_sha256=sha(a.out/'CLOUD_WORLD_VISUAL_QA.json'),
        calibrated_physical_accuracy_established=False,
        projection_note='projection reported as data QA, not used to fit camera or choose ROI',
        scope='Official transform numeric comparison + independently observed multiview person cloud overlap')


def prepare(a):
    roi=read(a.out/'BEHAVE_POSTERIOR_PATCH_ROI_FREEZE.json');assert roi['status']=='FROZEN_RGB_ONLY_VISUAL_QA'
    manifest=read(a.behave/'v2_3/report/BEHAVE_V2_FROZEN_TEST_MANIFEST.json')
    specs=[{**r,'fresh':False,'previously_consumed':True} for r in manifest['rows']];assert len(specs)==45
    smseq='Date01_Sub01_stool_sit';smfolder=a.behave/'data/sequences'/smseq
    smframe=sorted(p.name for p in smfolder.glob('t*') if p.is_dir())[0]
    smoke=dict(subject='Sub01',sequence=smseq,frame=smframe,previously_consumed=True,role='SMOKE_ONLY')
    lookup={(r['sequence'],r['frame'],r['camera']):r for r in roi['rows']}
    inputs=[]
    for spec in [*specs,smoke]:
        if a.phase=='refresh':
            records=read(a.out/'inputs'/spec['sequence']/spec['frame']/'identity.json')['cameras']
            for r in records:assert sha(Path(r['input_npz']))==r['sha256']
        else:records=prepare_frame(a,spec,lookup)
        inputs += records
    qa=camera_qa(a,[*specs,smoke]);write(a.out/'CAMERA_QA.json',qa)
    assert qa['status']=='PASS', 'See CAMERA_QA.json; no model was run'
    old=read(BASE/'EXPERIMENT_CONTRACT.json')
    contract=dict(status='FROZEN_BEFORE_NEW_MODEL_OUTPUTS',methods=METHODS,seed=0,frames=specs,smoke=smoke,
        txyz=old['txyz'],o2=old['o2'],rigid=old['rigid'],D=old['D'],roi_sha256=sha(a.out/'BEHAVE_POSTERIOR_PATCH_ROI_FREEZE.json'),
        surface='same fixed 2152 posterior faces; conservative clothed back patches only',
        evaluation_points_max=1500,primary='sensor posterior points -> exact predicted posterior triangles',
        ray='exact continuous geometric ray using pointcloud_table rays; no distorted-pixel-to-pinhole mismatch',
        visualization='distorted original RGB + cv2.projectPoints including distortion; painter image is qualitative, ray metrics independent',
        aggregation='heldout camera median -> frame -> sequence median -> subject median -> equal-subject mean; missing explicit',
        inputs=[dict(path=r['input_npz'],sha256=r['sha256']) for r in inputs],
        camera_qa_sha256=sha(a.out/'CAMERA_QA.json'),
        limits=['previously consumed people','clothed small patch, not whole-back or prone skin','one source camera for fit, heldout 3 cameras only evaluation'])
    write(a.out/'P2_EXECUTION_CONTRACT.json',contract)
    freeze=identity(a);write(a.out/'P2_RUNTIME_FREEZE.json',freeze)
    write(a.out/'P2_PREFLIGHT.json',dict(status='PASS',formal_frames=45,inputs=len(inputs),
        qualified_heldout_views=roi['qualified_heldout_views'],assets_sha256=sha(a.out/'P2_RUNTIME_FREEZE.json'),
        contract_sha256=sha(a.out/'P2_EXECUTION_CONTRACT.json'),code_sha256=sha(Path(__file__))))
    print('PREPARE_PASS',45,len(inputs),flush=True)


def summary(d):
    v=np.asarray(d,float)*1000
    return dict(count=len(v),median_mm=float(np.median(v)) if len(v) else None,
        p95_mm=float(np.percentile(v,95)) if len(v) else None,coverage_50mm=float(np.mean(v<=50)) if len(v) else None,
        max_mm=float(v.max()) if len(v) else None,above_500mm_count=int((v>500).sum()))


def run(a):
    pre=identity(a);assert pre==read(a.out/'P2_RUNTIME_FREEZE.json')
    contract=read(a.out/'P2_EXECUTION_CONTRACT.json');gate=read(a.out/'P2_PREFLIGHT.json')
    assert gate['contract_sha256']==sha(a.out/'P2_EXECUTION_CONTRACT.json')
    assert gate['code_sha256']==sha(Path(__file__))
    if a.phase=='full':assert read(a.out/'SMOKE_GATE.json')['status']=='PASS'
    specs=[contract['smoke']] if a.phase=='smoke' else [r for r in contract['frames'] if r['subject']==a.subject]
    assert specs
    sys.path[:0]=[str(BASE/'code'),str(SAM)]
    import torch
    import baseline_v1 as baseline
    from run_comparison import assert_baseline_constants,parameter_vertices
    from l1_fit import fit_rigid,fit_displacement,mesh_quality
    from metrics_v2 import ray_depth_residual
    from surface_metrics import point_to_triangle_distances
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    assert_baseline_constants(baseline,read(BASE/'EXPERIMENT_CONTRACT.json'))
    model,cfg=load_sam_3d_body(str(WEIGHTS/'model.ckpt'),device='cuda',mhr_path=str(WEIGHTS/'assets/mhr_model.pt'))
    model.eval();est=SAM3DBodyEstimator(model,cfg);faces=np.asarray(est.faces,np.int64)
    expected=read(BASE/'EXPERIMENT_CONTRACT.json')['historical_faces_sha256']
    assert hashlib.sha256(faces.astype('<i4').tobytes()).hexdigest()==expected
    az=np.load(ANCHORS);fi,bary=az['face_index'],az['barycentric'];assert len(fi)==16384
    posterior_faces=faces[np.asarray(read(a.root/'assets/candidate_posterior_mask.json')['face_ids'],np.int64)]
    qa=read(a.out/'CAMERA_QA.json');assert {r['sequence'] for r in specs}<={r['sequence'] for r in qa['rows']}
    runtime=dict(python=sys.version,torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),
        visible_gpu=os.environ.get('CUDA_VISIBLE_DEVICES'),numpy=np.__version__,platform=platform.platform())
    job=a.subject if a.phase=='full' else 'Sub01_smoke';rows=[];ledger=[]
    for spec in specs:
        started=time.time();seq,frame=spec['sequence'],spec['frame'];sid=seq+'/'+frame
        output=a.out/'run'/seq/frame;output.mkdir(parents=True,exist_ok=False)
        folder=a.out/'inputs'/seq/frame;inp=read(folder/'identity.json')
        for r in inp['cameras']:assert sha(Path(r['input_npz']))==r['sha256']
        z=np.load(folder/'K0.npz');rgb=z['rgb'];K=z['K'];box=z['bbox_xyxy'];train=z['points_m']
        torch.manual_seed(0);np.random.seed(0)
        batch=recursive_to(prepare_batch(rgb,est.transform,box[None],None,None),'cuda')
        batch['cam_int']=torch.as_tensor(K[None],device='cuda').to(batch['img']);model._initialize_batch(batch)
        with torch.inference_mode():raw=model.forward_step(batch,decoder_type='body')['mhr']
        # forward_step uses body_pose/shape/etc.; estimator renames these for
        # its public prediction dict. Preserve that exact naming conversion.
        pred={'pred_vertices':raw['pred_vertices'][0].detach().float().cpu().numpy(),
              **{target:raw[state][0].detach().float().cpu().numpy() for state,target in STATE_KEYS.items()}}
        del batch,raw
        vo=np.asarray(pred['pred_vertices'],float)+pred['pred_cam_t'][None]
        reconstructed=parameter_vertices(model,pred,torch)
        reconstruction_mm=float(np.linalg.norm(vo-reconstructed,axis=1).max()*1000);assert reconstruction_mm<.1
        np.savez_compressed(output/'official_prediction.npz',**pred)
        state={k:pred[v] for k,v in STATE_KEYS.items()}
        anc=(vo[faces[fi]]*bary[:,:,None]).sum(1)
        raw_t,trace=baseline.fit_txyz(train,anc);fallback=bool(np.linalg.norm(raw_t)>contract['txyz']['total_norm_bound_m'])
        applied=np.zeros(3) if fallback else raw_t;vt=vo+applied
        vp,pose_state,history,obs=baseline.optimize_pose(model,pred,applied,train,fi,bary,faces,'cuda:0',sid+'/seed-0')
        pose_idx=sample_idx(len(train),1024,sid+'/seed-0-o2-observed');assert np.array_equal(obs,train[pose_idx])
        rc=contract['rigid'];R,t=fit_rigid(vo,faces,train,K,iters=rc['iterations'],trim=rc['trim_fraction']);vr=vo@R.T+t
        dc=contract['D'];vd,delta,info=fit_displacement(vr,faces,train,K,lam=dc['lam'],mu=dc['mu'],tau=dc['tau'],n0=dc['n0'],
            irls=dc['irls'],sigma=dc['sigma_m'],use_conf=dc['use_conf'],use_robust=dc['use_robust'])
        variants=dict(zip(METHODS,[vo,vt,vp,vr,vd]));cameras=[read_camera(a.behave/'data/calibs',seq,k) for k in range(4)]
        metadata=dict(spec=spec,seed=0,input_identity_sha256=sha(folder/'identity.json'),official_prediction_sha256=sha(output/'official_prediction.npz'),
            official_parameter_roundtrip_max_mm=reconstruction_mm,raw_txyz_m=raw_t.tolist(),applied_txyz_m=applied.tolist(),fallback=fallback,
            txyz_trace=trace,pose_history=history,pose_translation_delta_from_txyz_m=(pose_state['pred_cam_t']-pred['pred_cam_t']-applied).tolist(),
            D_info=info,D_mesh_quality=mesh_quality(vr,vd,faces),optimization_camera='K0',evaluation_cameras=['K1','K2','K3'])
        for method,V in variants.items():
            st=pose_state if method=='Official+Txyz+Pose' else {**state,'pred_cam_t':state['pred_cam_t']+applied} if method=='Official+Txyz' else state
            extra={}
            if method in ['Official+Rigid','Official+Rigid+D']:extra.update(rigid_R=R,rigid_t_m=t,effective_cam_t_m=pred['pred_cam_t']@R.T+t)
            if method=='Official+Rigid+D':extra['displacement_m']=delta
            optidx=np.array([],np.int64) if method=='Official' else np.arange(len(train),dtype=np.int64)
            np.savez_compressed(output/(token(method)+'.npz'),vertices_m=V,faces=faces,**st,**extra,
                optimization_point_idx=optidx,pose_point_idx=pose_idx if method=='Official+Txyz+Pose' else np.array([],np.int64),
                translation_raw_m=raw_t,translation_applied_m=applied)
        write(output/'mesh_metadata.json',metadata)
        for k in range(4):
            other=np.load(folder/f'K{k}.npz');pts=other['points_m'];indices=other['posterior_eval_idx'];p=pts[indices]
            all_idx=other['eval_idx'];rays={};dists={}
            for method,V in variants.items():
                local=V if k==0 else transform_between(V,cameras[0],cameras[k])
                if len(p):
                    dists[method]=point_to_triangle_distances(p,local,posterior_faces)
                    rays[method]=ray_depth_residual(p,local,faces)[0]
                else:dists[method]=np.array([]);rays[method]=np.array([])
            common=np.logical_and.reduce([np.isfinite(rays[m]) for m in METHODS])
            for method in METHODS:
                rr=rays[method];meshfile=output/(token(method)+'.npz')
                rows.append(dict(subject=spec['subject'],sequence=seq,frame=frame,camera=f'K{k}',method=method,
                    role='FIT_CAMERA_SAME_SOURCE' if k==0 else 'HELDOUT_SENSOR',reference=inp['cameras'][k]['reference_status'],
                    posterior_point_count=len(p),surface=summary(dists[method]),ray=summary(np.abs(rr[np.isfinite(rr)])),
                    ray_hit_fraction=float(np.isfinite(rr).mean()) if len(p) else None,
                    ray_common_count=int(common.sum()),ray_common=summary(np.abs(rr[common])),
                    mesh_sha256=sha(meshfile),input_sha256=sha(folder/f'K{k}.npz')))
            np.savez_compressed(output/f'K{k}_residual_arrays.npz',posterior_eval_idx=indices,common_hit=common,
                                **{token(m)+'_distance_m':dists[m] for m in METHODS},**{token(m)+'_ray_m':rays[m] for m in METHODS})
        frame_rows=[r for r in rows if r['sequence']==seq and r['frame']==frame]
        write(output/'evaluation.json',frame_rows)
        ledger.append(dict(sequence=seq,frame=frame,official_inferences=1,fit_methods=4,method_camera_records=len(frame_rows),
            elapsed_seconds=time.time()-started,parameter_roundtrip_max_mm=reconstruction_mm))
        write(a.out/f'EXECUTION_LEDGER_{job}.json',dict(status='RUNNING',rows=ledger,runtime=runtime))
        print(job,sid,'CACHED_AND_EVALUATED',len(frame_rows),'seconds',round(time.time()-started,1),flush=True)
    post=identity(a);assert post==pre
    for spec in specs:
        for r in read(a.out/'inputs'/spec['sequence']/spec['frame']/'identity.json')['cameras']:
            assert sha(Path(r['input_npz']))==r['sha256']
            for source in r['original_files']:assert sha(Path(source['path']))==source['sha256']
    write(a.out/f'INTEGRITY_{job}.json',dict(status='PASS',runtime_pre=pre,runtime_post=post,inputs_and_original_data_unchanged=True))
    write(a.out/f'EXECUTION_LEDGER_{job}.json',dict(status='COMPLETE',rows=ledger,runtime=runtime))
    if a.phase=='smoke':write(a.out/'SMOKE_GATE.json',dict(status='PASS',subject='Sub01',formal_subjects_used=0,
        checks=['Official MHR parameter roundtrip','five cached meshes','historical optimizer constants','K0-only fit','cache-only exact evaluation'],
        improvement_required=False))
    print(job,'COMPLETE',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--behave',type=Path,required=True)
    p.add_argument('--phase',choices=['prepare','refresh','smoke','full'],required=True);p.add_argument('--subject');a=p.parse_args()
    a.out=a.root/'p2_behave_crossview'
    prepare(a) if a.phase in ['prepare','refresh'] else run(a)
