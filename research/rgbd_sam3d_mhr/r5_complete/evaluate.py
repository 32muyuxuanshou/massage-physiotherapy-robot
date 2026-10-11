"""Freeze raw predictions and dataset-specific metrics; never fit new models."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0');os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,hashlib,json,time,sys
from pathlib import Path
import numpy as np
import torch
from data import rows,batch
from engine import Engine
from r3_common import metrics as native_metrics,output_change,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'r5_camera_only'))
from evaluate_scan import group as scan_group

BODY_KEYS=['pred_pose_raw','global_rot','body_pose','shape','scale','hand','face',
    'pred_keypoints_3d','pred_vertices','pred_joint_coords','joint_global_rots','mhr_model_params']

def surface_rows(depth,sil,x,reference_depth):
    values=[]
    for i in range(len(depth)):
        mask=x['target_mask'][i].bool();target=x['target_depth'][i]
        hit=mask&(depth[i]>0);common=hit&(reference_depth[i]>0)
        def distance(where):
            d=(depth[i][where]-target[where]).abs()*1000
            return dict(median_mm=float(d.median()),p95_mm=float(torch.quantile(d,.95))) if len(d) else None
        all_error=distance(mask);inter=(sil[i]*mask).sum();union=(sil[i]+mask-sil[i]*mask).sum()
        values.append(dict(full_mask_median_mm=all_error['median_mm'],full_mask_p95_mm=all_error['p95_mm'],
            hit_rate=float(hit.sum()/mask.sum()),silhouette_iou=float(inter/union.clamp_min(1)),
            own_hit=distance(hit),common_hit=distance(common),
            official_on_common_hit=(dict(median_mm=float(((reference_depth[i]-target)[common].abs()*1000).median()),
                p95_mm=float(torch.quantile((reference_depth[i]-target)[common].abs()*1000,.95))) if common.any() else None),
            common_points=int(common.sum()),total_person_points=int(mask.sum())))
    return values

def native_group(records):
    ids=sorted({r['identity'] for r in records});per={}
    for identity in ids:
        rr=[r['metrics'] for r in records if r['identity']==identity]
        per[identity]={k:float(np.mean([v[k] for v in rr if v[k] is not None])) if any(v[k] is not None for v in rr) else None for k in rr[0]}
    return dict(per_identity=per,identity_equal_mean={k:float(np.mean([v[k] for v in per.values() if v[k] is not None])) if any(v[k] is not None for v in per.values()) else None for k in next(iter(per.values()))})

def run(a):
    torch.set_num_threads(2);paths=json.loads(a.paths.read_text());cache=paths[a.dataset+'_cache']
    records=rows(cache,a.dataset)
    if a.dataset!='real':records=[r for r in records if r['role']=='VAL']
    expected={'native':400,'scan':768,'real':232};assert len(records)==expected[a.dataset]
    engine=Engine('coarse' if a.mode=='official' else a.mode,paths);engine.eval()
    checkpoint_sha=None
    if a.mode!='official':
        state=torch.load(a.checkpoint,map_location='cpu',weights_only=False)
        assert state['identity']['mode']==a.mode and state['identity']['seed']==a.seed
        engine.load_checkpoint_state(state['model']);checkpoint_sha=sha(a.checkpoint)
    out=a.out;out.mkdir(parents=True,exist_ok=True);pred=out/'predictions';pred.mkdir(exist_ok=True)
    np.save(out/'faces.npy',engine.renderer.faces.cpu().numpy());results=[]
    with torch.no_grad():
        for start in range(0,len(records),a.batch):
            rr=records[start:start+a.batch];x=batch(rr);torch.cuda.synchronize();tick=time.monotonic()
            o,tr=(x['official'],{}) if a.mode=='official' else engine(x)
            torch.cuda.synchronize();seconds=time.monotonic()-tick
            if a.dataset=='native':values=native_metrics(o,x['truth'],x['target_depth'],x['target_mask'],x['K'],engine.renderer)
            elif a.dataset=='scan':
                d,s=engine.renderer(o['pred_vertices'].float()+o['pred_cam_t'].float()[:,None],x['K'])
                reference_depth,_=engine.renderer(x['official']['pred_vertices'].float()+x['official']['pred_cam_t'].float()[:,None],x['K'])
                values=surface_rows(d,s,x,reference_depth)
            else:values=[{} for _ in rr]
            for i,row in enumerate(rr):
                sample=Path(row['cache_file']).stem;K=x['K'][i].cpu().numpy();camera=o['pred_cam_t'][i].float().cpu().numpy()
                body=o['pred_vertices'][i].float().cpu().numpy();vc=body+camera
                keys={k:o[k][i:i+1].cpu().numpy() for k in BODY_KEYS}
                kp=o['pred_keypoints_3d'][i].float().cpu().numpy()+camera
                projection=lambda points:(points@K.T)[:,:2]/points[:,2:]
                target=pred/(sample+'.npz')
                diag={k:v[i].cpu().numpy() for k,v in tr.items() if torch.is_tensor(v) and v.ndim>0}
                np.savez_compressed(target,**keys,vertices_camera_A=vc,pred_cam_t=camera[None],K=K,
                    pred_keypoints_2d=projection(kp)[None],pred_keypoints_2d_verts=projection(vc)[None],
                    original_camera=x['official']['pred_cam_t'][i].cpu().numpy(),**diag)
                oo={k:o[k][i:i+1] for k in BODY_KEYS+['pred_cam_t']}
                ref={k:x['official'][k][i:i+1] for k in BODY_KEYS+['pred_cam_t']}
                change=output_change(oo,ref)
                reference_world=x['official']['pred_vertices'][i]+x['official']['pred_cam_t'][i]
                change['vertex_camera_change_mm']=float(((o['pred_vertices'][i]+o['pred_cam_t'][i])-reference_world).norm(dim=-1).mean()*1000)
                body_equal=all(torch.equal(o[k][i],x['official'][k][i]) for k in BODY_KEYS)
                if a.mode in ['pooled_mlp','coarse','full']:assert body_equal,'BODY_ISOLATION_BROKEN'
                item=dict(sample_id=sample,identity=row['identity'],role=row['role'],metrics=values[i],changes=change,
                    body_exact_equal=body_equal,camera_xyz_m=camera.tolist(),prediction_file=str(target),
                    prediction_sha256=sha(target),cache_file=row['cache_file'],
                    cached_head_seconds_per_image=seconds/len(rr),positive_vertex_fraction=float(np.mean(vc[:,2]>0)),
                    diagnostics={k:np.asarray(v).tolist() for k,v in diag.items()})
                if a.dataset=='scan':item.update(asset_id=row['asset_id'],camera_group=row['view']['group'],view=row['view'],truncated=row['image_truncated'],**values[i])
                if a.dataset=='real':item.update(sequence=row['sequence'],frame=row['frame'])
                results.append(item)
            if start%128==0:print('PREDICTIONS',a.mode,a.seed,a.dataset,len(results),flush=True)
    aggregate=native_group(results) if a.dataset=='native' else scan_group(results) if a.dataset=='scan' else None
    report=dict(status='RAW_PREDICTION_COMPLETE',mode=a.mode,seed=a.seed,dataset=a.dataset,
        checkpoint_sha256=checkpoint_sha,records=results,aggregated=aggregate,TEST_read=False,camera_B_read=False,
        new_model_Txyz=False,timing_scope='cached head only; Official RGB backbone omitted, camera-only also uses cached Official Body; not full pipeline speed',
        metric_scope='native corresponding GT; scan visible clean axial Z/silhouette without MHR root GT; real raw outputs awaiting frozen Camera B evaluation')
    (out/'RESULTS.json').write_text(json.dumps(report,indent=2));engine.close();print('EVALUATION_COMPLETE',a.mode,a.dataset,len(results),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['paths','checkpoint','out']:p.add_argument('--'+n,type=Path,required=n!='checkpoint')
    p.add_argument('--dataset',choices=['native','scan','real'],required=True);p.add_argument('--mode',required=True)
    p.add_argument('--seed',type=int,default=0);p.add_argument('--batch',type=int,default=16);run(p.parse_args())
