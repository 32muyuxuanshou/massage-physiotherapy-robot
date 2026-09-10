"""Benchmark a Camera-A-only CUDA mesh-depth residual on consumed selector data.

The runtime timer starts after both candidate meshes exist.  Camera B values from
the consumed feature audit are labels only and never enter the residual.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np
import torch


def read_json(path):
    return json.loads(Path(path).read_text())


def auc(scores, labels):
    scores=np.asarray(scores,float); labels=np.asarray(labels,int)
    pos=scores[labels==1]; neg=scores[labels==0]
    if not len(pos) or not len(neg): return None
    return float(((pos[:,None]>neg[None,:]).sum()+.5*(pos[:,None]==neg[None,:]).sum())/(len(pos)*len(neg)))


def corr(x,y):
    return float(np.corrcoef(np.asarray(x,float),np.asarray(y,float))[0,1])


def sampled_surface(vertices, faces):
    tri=vertices[faces]
    # Vertices plus centroid and edge midpoints give dense, deterministic splats.
    return torch.cat((vertices,tri.mean(1),(tri[:,0]+tri[:,1])*.5,
                      (tri[:,1]+tri[:,2])*.5,(tri[:,2]+tri[:,0])*.5),0)


@torch.inference_mode()
def gpu_depth_residual(points, vertices_oa, faces, K, height, width):
    """Return residual/coverage for O and A using CUDA z-buffer point splats."""
    device=vertices_oa.device; n_pix=height*width
    K=torch.as_tensor(K,device=device,dtype=torch.float32)
    obs=torch.as_tensor(points,device=device,dtype=torch.float32)
    ou=torch.round(K[0,0]*obs[:,0]/obs[:,2]+K[0,2]).long()
    ov=torch.round(K[1,1]*obs[:,1]/obs[:,2]+K[1,2]).long()
    oi=ov*width+ou
    ovalid=(obs[:,2]>0)&(ou>=0)&(ou<width)&(ov>=0)&(ov<height)
    results=[]
    for vertices in vertices_oa:
        surf=sampled_surface(vertices,faces)
        u=torch.round(K[0,0]*surf[:,0]/surf[:,2]+K[0,2]).long()
        v=torch.round(K[1,1]*surf[:,1]/surf[:,2]+K[1,2]).long()
        valid=(surf[:,2]>0)&(u>=0)&(u<width)&(v>=0)&(v<height)
        depth=torch.full((n_pix,),float('inf'),device=device)
        depth.scatter_reduce_(0,(v[valid]*width+u[valid]),surf[valid,2],reduce='amin',include_self=True)
        pred=depth[oi[ovalid]]; covered=torch.isfinite(pred)
        residual=torch.abs(pred[covered]-obs[ovalid,2][covered])*1000
        results.append((float(residual.median().item()) if residual.numel() else None,
                        float(covered.float().mean().item()),int(covered.sum().item())))
    return results


def summarize(rows, split):
    rr=[r for r in rows if r['split']==split]
    exact=[r['exact_delta_mm'] for r in rr]; fast=[r['fast_delta_mm'] for r in rr]
    labels=[int(r['b_winner']=='A') for r in rr]
    return {'frames':len(rr),'pearson_exact_vs_fast':corr(exact,fast),
            'auc_fast_vs_camera_b_winner':auc(fast,labels),
            'auc_exact_vs_camera_b_winner':auc(exact,labels)}


def main():
    p=argparse.ArgumentParser()
    for x in ('sam-repo','selector-code','official','mhr','winner','dev-rows','val-rows','dev-features','val-features','out-dir'):
        p.add_argument('--'+x,type=Path,required=True)
    a=p.parse_args(); out_dir=a.out_dir; out_dir.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(a.sam_repo),str(a.selector_code)]
    from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    from pose_camera_output_freeze import PoseCameraOutputFreeze
    model,cfg=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr)); model.eval()
    estimator=SAM3DBodyEstimator(model,cfg); ctl=PoseCameraOutputFreeze(model)
    faces=model.head_pose.faces.cuda().long()
    sets=[]
    for split,rp,fp in [('DEVELOPMENT',a.dev_rows,a.dev_features),('SELECTOR_VAL',a.val_rows,a.val_features)]:
        features={r['id']:r for r in read_json(fp)['rows']}
        sets += [(split,r,features[r['id']]) for r in read_json(rp)['rows']]
    refs={}; official={}
    with torch.inference_mode():
        for _,r,_ in sets:
            with np.load(r['path']) as z: rgb=z['rgb_a'].copy(); bb=z['bbox_a'].copy(); K=z['K_a'].copy()
            b=recursive_to(prepare_batch(rgb,estimator.transform,bb[None].astype(np.float32),None,None),'cuda')
            b['cam_int']=torch.as_tensor(K[None],device='cuda').to(b['img']); model._initialize_batch(b)
            ctl.begin_reference_capture(); o=model.forward_step(b,decoder_type='body')['mhr']
            refs[r['id']]=[x.cpu() for x in ctl.end_reference_capture()]
            official[r['id']]=(o['pred_vertices']+o['pred_cam_t'][:,None])[0].detach()
    ck=torch.load(a.winner,map_location='cpu',weights_only=False); named=dict(model.named_parameters())
    with torch.no_grad():
        for n,v in ck['model_trainable'].items(): named[n].copy_(v.to(named[n]))
    adapted={}
    with torch.inference_mode():
        for _,r,_ in sets:
            with np.load(r['path']) as z: rgb=z['rgb_a'].copy(); bb=z['bbox_a'].copy(); K=z['K_a'].copy()
            b=recursive_to(prepare_batch(rgb,estimator.transform,bb[None].astype(np.float32),None,None),'cuda')
            b['cam_int']=torch.as_tensor(K[None],device='cuda').to(b['img']); model._initialize_batch(b)
            ctl.use_frozen_output_reference([x.cuda() for x in refs[r['id']]])
            o=model.forward_step(b,decoder_type='body')['mhr']; ctl.clear_frozen_output_reference()
            adapted[r['id']]=(o['pred_vertices']+o['pred_cam_t'][:,None])[0].detach()
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats(); rows=[]; times=[]
    # Warm-up excludes compilation/allocator startup from the latency distribution.
    s,r,f=sets[0]
    with np.load(r['path']) as z: gpu_depth_residual(z['points_a'],torch.stack((official[r['id']],adapted[r['id']])),faces,z['K_a'],*z['rgb_a'].shape[:2])
    torch.cuda.synchronize(); baseline_mem=torch.cuda.memory_allocated()
    for split,r,truth in sets:
        with np.load(r['path']) as z:
            torch.cuda.synchronize(); t=time.perf_counter()
            vals=gpu_depth_residual(z['points_a'],torch.stack((official[r['id']],adapted[r['id']])),faces,z['K_a'],*z['rgb_a'].shape[:2])
            torch.cuda.synchronize(); times.append((time.perf_counter()-t)*1000)
        fo,fa=vals; rows.append({'split':split,'id':r['id'],'subject_id':r['subject_id'],
            'fast_o_mm':fo[0],'fast_a_mm':fa[0],'fast_delta_mm':fo[0]-fa[0],
            'fast_coverage_o':fo[1],'fast_coverage_a':fa[1],'fast_covered_o':fo[2],'fast_covered_a':fa[2],
            'exact_delta_mm':truth['a_point_o']-truth['a_point_a'],
            'exact_coverage_o':truth['coverage_o'],'exact_coverage_a':truth['coverage_a'],
            'b_winner':truth['b_winner']})
    thresholds=[]
    for tau in (0,2,5,10,15):
        pred=[r['fast_delta_mm']>tau and r['fast_coverage_a']>=r['fast_coverage_o']-.02 for r in rows]
        exact_pred=[r['exact_delta_mm']>15 and r['exact_coverage_a']>=r['exact_coverage_o']-.02 for r in rows]
        thresholds.append({'tau_mm':tau,'winner_agreement_with_frozen_exact':float(np.mean(np.asarray(pred)==np.asarray(exact_pred))),
                           'camera_b_winner_accuracy':float(np.mean(np.asarray(pred)==np.asarray([r['b_winner']=='A' for r in rows])))})
    result={'status':'GPU_CAMERA_A_RUNTIME_RESIDUAL_EVALUATED_ON_CONSUMED_DATA','implementation':'CUDA vectorized surface splat z-buffer; vertices + face centroid + edge midpoints; torch.scatter_reduce amin',
      'data_governance':{'splits':['DEVELOPMENT','SELECTOR_VAL'],'new_system_sealed_read':False,'camera_a_only_feature':True,'camera_b_consumed_labels_only':True},
      'metrics':{x:summarize(rows,x) for x in ('DEVELOPMENT','SELECTOR_VAL')},'finite_thresholds':thresholds,
      'latency_ms':{'frames':len(times),'p50':float(np.quantile(times,.5)),'p90':float(np.quantile(times,.9)),'scope':'both candidate meshes already available; Camera-A residual only'},
      'cuda':{'device':torch.cuda.get_device_name(),'peak_allocated_mb':float(torch.cuda.max_memory_allocated()/1024**2),'incremental_peak_over_cached_meshes_mb':float((torch.cuda.max_memory_allocated()-baseline_mem)/1024**2)},'rows':rows}
    (out_dir/'GPU_RUNTIME_RESIDUAL_V1.json').write_text(json.dumps(result,indent=2)+'\n')
    best=max(thresholds,key=lambda x:(x['winner_agreement_with_frozen_exact'],x['camera_b_winner_accuracy'],-x['tau_mm']))
    ready={'status':'READY_AS_APPROXIMATE_RUNTIME_SELECTOR' if best['winner_agreement_with_frozen_exact']>=.9 else 'NOT_READY_AS_APPROXIMATE_RUNTIME_SELECTOR',
      'recommended_threshold':best,'requirements':{'exact_agreement_min':.9},'observed':{'all':summarize(rows,'DEVELOPMENT') if False else {'frames':len(rows),'pearson_exact_vs_fast':corr([r['exact_delta_mm'] for r in rows],[r['fast_delta_mm'] for r in rows]),'auc_fast':auc([r['fast_delta_mm'] for r in rows],[r['b_winner']=='A' for r in rows])}},
      'latency_ms':result['latency_ms'],'cuda':result['cuda'],'limits':['Mesh forward latency excluded','Point-splat depth is an approximation to point-to-triangle distance','HuMMan dataset ROI/depth only']}
    (out_dir/'GPU_SELECTOR_READINESS_V1.json').write_text(json.dumps(ready,indent=2)+'\n')
    print(json.dumps({'result':str(out_dir/'GPU_RUNTIME_RESIDUAL_V1.json'),'readiness':ready},indent=2))

if __name__=='__main__': main()
