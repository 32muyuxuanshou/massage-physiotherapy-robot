"""Fresh Official -> five train-only branches -> cache-only evaluation/figures.

Run on the existing GPU server, in dev then full stages. No training is performed.
"""
import argparse,sys,time,platform
from pathlib import Path
import numpy as np
from data_v2 import load_json,save_json,sha,array_sha,prepare_subject
from cache_v2 import save_mesh,mesh_path,verify_cache,historical_sample_indices
from l1_fit import fit_rigid,fit_displacement

DELIVERY=Path(__file__).resolve().parents[1]
STATE_KEYS={'pred_cam_t':'pred_cam_t','global_rot':'global_rot','body_pose':'body_pose_params',
            'shape':'shape_params','scale':'scale_params','hand':'hand_pose_params','face':'expr_params'}


def delivery_identity():
    manifest=load_json(DELIVERY/'FILES_MANIFEST.json')
    for row in manifest['files']:
        if sha(DELIVERY/row['path'])!=row['sha256']:raise RuntimeError('DELIVERY_FILE_CHANGED '+row['path'])
    return sha(DELIVERY/'FILES_MANIFEST.json')


def source_tree(root):
    return {str(p.relative_to(root)).replace('\\','/'):sha(p) for p in sorted(root.rglob('*.py'))}


def runtime_assets(args,contract):
    record=dict(checkpoint_sha256=sha(args.checkpoint),mhr_sha256=sha(args.mhr),anchors_sha256=sha(args.anchors))
    for name in ['checkpoint','mhr','anchors']:
        assert record[name+'_sha256']==contract['historical_'+name+'_sha256'],name+' frozen hash mismatch'
    record.update(sam_repo=str(args.sam_repo.resolve()),sam_source_files=source_tree(args.sam_repo),
                  python=sys.version,platform=platform.platform())
    return record


def assert_baseline_constants(b,contract):
    t=contract['txyz'];o=contract['o2']
    assert [b.TXYZ_ITERS,b.TXYZ_STEP,b.TRIM,b.TOTAL_TXYZ]==[t['iterations'],t['step_per_axis_m'],t['trim_fraction'],t['total_norm_bound_m']]
    assert [b.O2_ITERS,b.O2_OBSERVED_POINTS,b.O2_ANCHOR_STRIDE,b.O2_HUBER_BETA,
            b.O2_LR_TRANSLATION,b.O2_LR_POSE,b.O2_LAMBDA_TRANSLATION,b.O2_LAMBDA_POSE]==[
            o['iterations'],o['observed_points'],o['anchor_stride'],o['huber_beta_m'],
            o['lr_translation'],o['lr_pose'],o['lambda_translation'],o['lambda_pose']]


def parameter_vertices(model,pred,torch):
    d={key:torch.as_tensor(pred[src],device='cuda',dtype=torch.float32)[None] for key,src in STATE_KEYS.items()}
    with torch.no_grad():
        v=model.head_pose.mhr_forward(global_trans=torch.zeros_like(d['global_rot']),global_rot=d['global_rot'],
            body_pose_params=d['body_pose'],hand_pose_params=d['hand'],scale_params=d['scale'],
            shape_params=d['shape'],expr_params=d['face'])[0]
        v=v.clone();v[...,1:3]*=-1
        return (v+d['pred_cam_t'][:,None])[0].cpu().numpy()


def run_subject(args,subject,model,estimator,faces,fi,bary,torch,baseline,contract):
    root=args.out;inp=root/'inputs'/subject
    inputs=np.load(inp/'input.npz',allow_pickle=False)
    points=inputs['points_m'];K=inputs['K'];rgb=inputs['rgb'];bbox=inputs['bbox_xyxy']
    initial=root/'initial'/subject;initial.mkdir(parents=True,exist_ok=True)
    cache=initial/'official_prediction.npz';identity=initial/'identity.json'
    if cache.exists():
        meta=load_json(identity);assert meta['input_sha256']==sha(inp/'input.npz')
        assert meta['prediction_sha256']==sha(cache)
        pred=dict(np.load(cache,allow_pickle=False))
    else:
        # Exactly one inference per subject. No historical depth-fitted parameters.
        torch.manual_seed(0);np.random.seed(0)
        outs=estimator.process_one_image(rgb,bboxes=bbox[None],
            cam_int=torch.as_tensor(K[None],device='cuda',dtype=torch.float32),inference_type='body')
        assert len(outs)==1
        pred={k:np.asarray(outs[0][k]) for k in ['pred_vertices',*STATE_KEYS.values()]}
        np.savez_compressed(cache,**pred)
        reconstructed=parameter_vertices(model,pred,torch)
        official=np.asarray(pred['pred_vertices'])+pred['pred_cam_t'][None]
        discrepancy=float(np.linalg.norm(reconstructed-official,axis=1).max()*1000)
        meta=dict(input_sha256=sha(inp/'input.npz'),prediction_sha256=sha(cache),
            input_contract='original RGB + historical full bbox + historical K',
            source_status='FRESH_OFFICIAL_NO_DEPTH_FIT',parameter_roundtrip_max_mm=discrepancy,
            depth_points_used_in_initialization=0,full_mhr_parameter_keys=list(STATE_KEYS.values()))
        save_json(identity,meta)
    assert meta['source_status']=='FRESH_OFFICIAL_NO_DEPTH_FIT'
    assert meta['parameter_roundtrip_max_mm']<=contract['official_parameter_roundtrip_max_mm']
    Vo=np.asarray(pred['pred_vertices'],float)+pred['pred_cam_t'][None]
    state={k:pred[src] for k,src in STATE_KEYS.items()}
    anchors=(Vo[faces[fi]]*bary[:,:,None]).sum(1)
    for seed in contract['seeds']:
        paths=[mesh_path(root,subject,seed,m) for m in contract['methods']]
        if all(p.exists() for p in paths):
            for p in paths:verify_cache(p,root,subject,seed)
            continue
        if any(p.exists() for p in paths):raise RuntimeError('PARTIAL_BRANCH_CACHE: use a new output root or remove only the interrupted seed directory')
        split=np.load(inp/f'split_{seed}.npz',allow_pickle=False);idx=split['train_idx'];train=points[idx]
        empty=np.array([],np.int64)
        save_mesh(root,subject,seed,'Official',Vo,faces,Vo,dict(depth_fit=False),state,
                  'FRESH_OFFICIAL_NO_DEPTH_FIT',optimization_point_idx=empty)
        raw,trace=baseline.fit_txyz(train,anchors)
        fallback=bool(np.linalg.norm(raw)>contract['txyz']['total_norm_bound_m'])
        applied=np.zeros(3) if fallback else raw
        Vt=Vo+applied;ts={**state,'pred_cam_t':state['pred_cam_t']+applied}
        save_mesh(root,subject,seed,'Official+Txyz',Vt,faces,Vo,
            dict(depth_fit=True,config=contract['txyz'],raw_translation_m=raw.tolist(),
                 applied_translation_m=applied.tolist(),fallback=fallback,trace=trace),ts,
            'FRESH_OFFICIAL_TRAIN_ONLY',optimization_point_idx=idx,translation_raw_m=raw,translation_applied_m=applied)
        key=f'{subject}-seed-{seed}'
        pose_idx=historical_sample_indices(idx,contract['o2']['observed_points'],key+'-o2-observed')
        Vp,ps,history,observed=baseline.optimize_pose(model,pred,applied,train,fi,bary,faces,'cuda:0',key)
        assert np.array_equal(observed,points[pose_idx])
        save_mesh(root,subject,seed,'Official+Txyz+Pose',Vp,faces,Vt,
            dict(depth_fit=True,config=contract['o2'],txyz_fallback=fallback,history=history,
                 pose_points_n=len(pose_idx),prior_points_idx_from_Txyz='optimization_point_idx',
                 translation_delta_from_txyz_m=(ps['pred_cam_t']-ts['pred_cam_t']).tolist()),ps,
            'FRESH_OFFICIAL_TRAIN_ONLY',optimization_point_idx=idx,pose_point_idx=pose_idx,
            translation_raw_m=raw,translation_applied_m=applied)
        R,t=fit_rigid(Vo,faces,train,K,iters=contract['rigid']['iterations'],trim=contract['rigid']['trim_fraction'])
        Vr=Vo@R.T+t;rs=state;effective_cam_t=state['pred_cam_t']@R.T+t
        rigid_info=dict(depth_fit=True,config=contract['rigid'],R=R.tolist(),t_m=t.tolist(),
            parameter_semantics='original MHR shape/pose + explicit rigid transform; effective camera translation stored')
        save_mesh(root,subject,seed,'Official+Rigid',Vr,faces,Vo,rigid_info,rs,
            'FRESH_OFFICIAL_TRAIN_ONLY',optimization_point_idx=idx,rigid_R=R,rigid_t_m=t,effective_cam_t_m=effective_cam_t)
        cfg=contract['D'];Vd,delta,info=fit_displacement(Vr,faces,train,K,lam=cfg['lam'],mu=cfg['mu'],
            tau=cfg['tau'],n0=cfg['n0'],irls=cfg['irls'],sigma=cfg['sigma_m'],
            use_conf=cfg['use_conf'],use_robust=cfg['use_robust'])
        save_mesh(root,subject,seed,'Official+Rigid+D',Vd,faces,Vr,
            dict(depth_fit=True,config=cfg,rigid=rigid_info,D_info=info,
                 displacement_norm_p95_mm=float(np.percentile(np.linalg.norm(delta,axis=1),95)*1000),
                 parameter_semantics='MHR prior + explicit rigid transform + vector vertex displacement'),rs,
            'FRESH_OFFICIAL_TRAIN_ONLY',optimization_point_idx=idx,rigid_R=R,rigid_t_m=t,displacement_m=delta,effective_cam_t_m=effective_cam_t)
        print(subject,'seed',seed,'five branch meshes cached',flush=True)
    from make_visuals import visualize_subject
    from evaluate_cache import evaluate_subject
    rows=evaluate_subject(subject,DELIVERY,root)
    visualize_subject(subject,DELIVERY,root)
    for row in rows:row['silhouette']=load_json(mesh_path(root,subject,row['seed'],row['method']).with_suffix('.json'))['silhouette']
    save_json(root/'evaluation'/subject/'results.json',rows)
    return rows


def main():
    p=argparse.ArgumentParser()
    for key in ['raw','sam-repo','checkpoint','mhr','anchors','out']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--stage',choices=['dev','full'],required=True);args=p.parse_args()
    contract=load_json(DELIVERY/'EXPERIMENT_CONTRACT.json');pre=delivery_identity()
    args.out.mkdir(parents=True,exist_ok=True)
    asset_pre=runtime_assets(args,contract)
    args_identity={k:str(v.resolve()) if isinstance(v,Path) else v for k,v in vars(args).items() if k!='stage'}
    freeze=dict(delivery_manifest_sha256=pre,arguments=args_identity,assets=asset_pre)
    freeze_path=args.out/'RUN_FREEZE.json'
    if freeze_path.exists():assert load_json(freeze_path)==freeze,'Runtime freeze mismatch'
    else:save_json(freeze_path,freeze)
    todo=contract['dev'] if args.stage=='dev' else contract['subjects']
    if args.stage=='full':
        gate=load_json(args.out/'DEV_STRUCTURAL_GATE.json')
        assert gate['status']=='PASS' and gate['delivery_manifest_sha256']==pre
    # All point partitions for this stage exist before any inference or fit.
    for subject in todo:
        inp=args.out/'inputs'/subject
        if not (inp/'input_manifest.json').exists():prepare_subject(args.raw/subject/'p_select.p',subject,DELIVERY,inp)
        else:
            meta=load_json(inp/'input_manifest.json');assert sha(inp/'input.npz')==meta['input_npz_sha256']
            for s in meta['splits']:assert sha(inp/f"split_{s['seed']}.npz")==s['sha256']
    from camera_qa import camera_audit
    for subject in todo:camera_audit(subject,args.out)
    import torch
    import baseline_v1 as baseline
    assert_baseline_constants(baseline,contract)
    sys.path.insert(0,str(args.sam_repo))
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    model,cfg=load_sam_3d_body(str(args.checkpoint),device='cuda',mhr_path=str(args.mhr));model.eval()
    estimator=SAM3DBodyEstimator(model,cfg);faces=np.asarray(estimator.faces,np.int64)
    assert array_sha(faces.astype('<i4'))==contract['historical_faces_sha256']
    anchor=np.load(args.anchors,allow_pickle=False);fi=anchor['face_index'];bary=anchor['barycentric'].astype(float)
    assert len(fi)==16384
    save_json(args.out/'ENVIRONMENT.json',dict(torch=torch.__version__,cuda=torch.version.cuda,
        gpu=torch.cuda.get_device_name(),device='cuda:0',numpy=np.__version__))
    ledger=[]
    for subject in todo:
        started=time.time();rows=run_subject(args,subject,model,estimator,faces,fi,bary,torch,baseline,contract)
        assert len(rows)==15 and all(r['posterior']['d3d']['n']>0 for r in rows)
        ledger.append(dict(subject=subject,rows=len(rows),elapsed_seconds=time.time()-started))
        save_json(args.out/f'EXECUTION_LEDGER_{args.stage}.json',ledger)
    post=delivery_identity();asset_post=runtime_assets(args,contract)
    assert pre==post and asset_pre==asset_post
    save_json(args.out/f'INTEGRITY_{args.stage}.json',dict(status='PASS',pre_delivery_sha256=pre,
        post_delivery_sha256=post,runtime_assets_unchanged=True))
    from aggregate_results import aggregate
    result=aggregate(args.out,contract,todo)
    from audit_outputs import audit_outputs
    audit_outputs(args.out,contract,todo)
    if args.stage=='dev':
        save_json(args.out/'DEV_STRUCTURAL_GATE.json',dict(status='PASS',subjects=todo,rows=60,
            delivery_manifest_sha256=pre,numerical_improvement_required=False,
            verified=['full parameter reconstruction','train/heldout disjointness','five cached methods','positive evaluation count','cache visuals']))
    if args.stage=='full':assert result['row_count']==contract['expected_rows']
    print(args.stage,'complete;',result['row_count'],'rows; interpret as reconstructed-camera diagnostic',flush=True)


if __name__=='__main__':main()
