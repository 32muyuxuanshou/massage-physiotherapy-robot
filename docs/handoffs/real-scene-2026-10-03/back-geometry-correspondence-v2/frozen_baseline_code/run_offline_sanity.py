"""S107 CPU sanity, legacy RGB-only Official cache; never formal experiment rows."""
import argparse,time
from pathlib import Path
import numpy as np
from data_v2 import prepare_subject,load_json,save_json,sha,array_sha
from cache_v2 import save_mesh,mesh_path,verify_cache
from l1_fit import fit_rigid,fit_displacement
from evaluate_cache import evaluate_subject
from make_visuals import visualize_subject
from aggregate_results import aggregate


def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True)
    p.add_argument('--legacy-official',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    delivery=Path(__file__).resolve().parents[1];contract=load_json(delivery/'EXPERIMENT_CONTRACT.json')
    subject='S107';seed=0;names=['Official','Official+Rigid','Official+Rigid+D'];started=time.time()
    inp_root=a.out/'inputs'/subject
    if not (inp_root/'input_manifest.json').exists():prepare_subject(a.raw,subject,delivery,inp_root)
    else:assert sha(inp_root/'input.npz')==load_json(inp_root/'input_manifest.json')['input_npz_sha256']
    inp=np.load(a.out/'inputs'/subject/'input.npz',allow_pickle=False);points=inp['points_m'];K=inp['K']
    old=np.load(a.legacy_official,allow_pickle=False);Vo=old['Official_vertices'].astype(float);F=old['faces'].astype(np.int64)
    assert array_sha(F.astype('<i4'))==contract['historical_faces_sha256']
    assert np.array_equal(K,old['K']) and np.array_equal(inp['bbox_xyxy'],old['bbox_xyxy'])
    state=dict(pred_cam_t=old['Official_cam_t'],global_rot=old['Official_global_rot'],body_pose=old['Official_body_pose'])
    src='OFFLINE_SANITY_LEGACY_RGB_ONLY_OFFICIAL_INCOMPLETE_MHR_PARAMETERS'
    split=np.load(a.out/'inputs'/subject/f'split_{seed}.npz',allow_pickle=False);idx=split['train_idx'];train=points[idx]
    path=mesh_path(a.out,subject,seed,'Official+Rigid+D')
    if not path.exists():
        print('S107 train-only rigid fit',len(train),'points',flush=True)
        save_mesh(a.out,subject,seed,names[0],Vo,F,Vo,dict(depth_fit=False),state,src)
        R,t=fit_rigid(Vo,F,train,K,iters=contract['rigid']['iterations'],trim=contract['rigid']['trim_fraction'])
        Vr=Vo@R.T+t;rs=state;effective_cam_t=state['pred_cam_t']@R.T+t
        save_mesh(a.out,subject,seed,names[1],Vr,F,Vo,dict(depth_fit=True,config=contract['rigid'],R=R.tolist(),t_m=t.tolist()),rs,src,
                  optimization_point_idx=idx,rigid_R=R,rigid_t_m=t,effective_cam_t_m=effective_cam_t)
        cfg=contract['D'];print('S107 train-only D fit',flush=True)
        Vd,delta,info=fit_displacement(Vr,F,train,K,lam=cfg['lam'],mu=cfg['mu'],tau=cfg['tau'],n0=cfg['n0'],
            irls=cfg['irls'],sigma=cfg['sigma_m'],use_conf=cfg['use_conf'],use_robust=cfg['use_robust'])
        save_mesh(a.out,subject,seed,names[2],Vd,F,Vr,dict(depth_fit=True,config=cfg,D_info=info),rs,src,
                  optimization_point_idx=idx,rigid_R=R,rigid_t_m=t,displacement_m=delta,effective_cam_t_m=effective_cam_t)
    for name in names:verify_cache(mesh_path(a.out,subject,seed,name),a.out,subject,seed)
    print('S107 cached-mesh exact evaluation',flush=True)
    rows=evaluate_subject(subject,delivery,a.out,names,[seed])
    visual=visualize_subject(subject,delivery,a.out,names,[seed])
    for r in rows:r['silhouette']=load_json(mesh_path(a.out,subject,seed,r['method']).with_suffix('.json'))['silhouette']
    save_json(a.out/'evaluation'/subject/'results.json',rows)
    result=aggregate(a.out,contract,[subject],names,[seed])
    from audit_outputs import audit_outputs
    audit_outputs(a.out,contract,[subject],names,[seed])
    save_json(a.out/'SANITY_EXECUTION.json',dict(status='LOCAL_SANITY_COMPLETE_FORMAL_PENDING',formal_rows=0,
        local_rows=len(rows),subjects=1,seeds=[0],methods=names,source_status=src,
        missing=['fresh Official inference','complete MHR shape/scale/hand/face','official anchors asset','Txyz on real anchors','GPU O2'],
        legacy_asset_sha256=sha(a.legacy_official),raw_sha256=sha(a.raw),visualizations=len(visual),seconds=time.time()-started))
    print('OFFLINE ONLY',result['row_count'],'rows; no formal conclusion',flush=True)


if __name__=='__main__':main()
