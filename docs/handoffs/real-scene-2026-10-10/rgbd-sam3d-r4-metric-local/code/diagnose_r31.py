"""Fixed-mask Depth interventions and historical Cheap Txyz on frozen A/B views."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import torch
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
from torch.nn import functional as F
from fusion import RGBDBodyAdapter,metric_features
from r3_common import load_official,read_cache,combine,cached_forward,metrics,aggregate,output_change,sha
from render_losses import MeshRenderer
from humman_geometry import transform_camera
from evaluate_r3_humman import aggregate_real


def depth_features(d,valid,rays,condition,seed,donor=None):
    """Intervene on values/channels; original validity and camera rays never change."""
    features,checked=metric_features(d,valid,rays)
    assert torch.equal(checked,valid.bool())
    z,relative=features[:,0:1],features[:,1:2]
    center=(z-relative)*valid
    if condition=='mask_rays_only':features[:,:2]=0
    elif condition=='absolute_only':features[:,1:2]=0
    elif condition=='relative_only':features[:,0:1]=0
    elif condition=='flat_center':features[:,0:1]=center;features[:,1:2]=0
    elif condition in ['lowpass_shape','highpass_shape']:
        smooth=F.avg_pool2d(z,31,1,15)/F.avg_pool2d(valid.float(),31,1,15).clamp_min(1e-6)
        zz=smooth if condition=='lowpass_shape' else center+z-smooth
        features[:,0:1]=torch.where(valid,zz,0);features[:,1:2]=torch.where(valid,zz-center,0)
    elif condition.startswith('offset_'):
        features[:,0:1]=torch.where(valid,z+float(condition[7:]),0)
    elif condition.startswith('noise_'):
        g=torch.Generator(device=d.device).manual_seed(seed)
        zz=z+torch.randn(z.shape,generator=g,device=z.device)*float(condition[6:])
        features[:,0:1]=torch.where(valid,zz,0)
        features[:,1:2]=torch.where(valid,zz-center,0)
    elif condition=='local_shuffle_fixed_mask':
        zz=z.clone();g=torch.Generator(device=d.device).manual_seed(seed)
        for i in range(len(z)):
            for y in range(0,z.shape[-2],16):
                for x in range(0,z.shape[-1],16):
                    v=valid[i,0,y:y+16,x:x+16];patch=zz[i,0,y:y+16,x:x+16]
                    values=patch[v];patch[v]=values[torch.randperm(len(values),generator=g,device=z.device)]
        features[:,0:1]=zz;features[:,1:2]=torch.where(valid,zz-center,0)
    elif condition=='cross_identity_fixed_mask':
        dd,dv=donor
        filled=[]
        for di,vi in zip(dd,dv):
            a=di[0].cpu().numpy();v=vi[0].cpu().numpy().astype(bool)
            assert v.any()
            ix=distance_transform_edt(~v,return_distances=False,return_indices=True)
            filled.append(a[tuple(ix)])
        zz=torch.from_numpy(np.stack(filled)[:,None]).to(d)
        zz=torch.where(valid,zz,0)
        features,_=metric_features(zz,valid,rays)
    elif condition!='correct':raise ValueError(condition)
    assert torch.equal(features[:,2:3].bool(),valid.bool())
    assert torch.equal(features[:,3:],rays.to(features))
    return features


def intervention_forward(model,b,feature,d,valid,rays,condition,seed,donor=None):
    features=depth_features(d,valid,rays,condition,seed,donor)
    h=model.fusion.depth_encoder.register_forward_pre_hook(lambda module,args:(features,))
    try:return cached_forward(model,b,feature,d,valid,rays)
    finally:h.remove()


def depth_diagnostic(root,out,config):
    official,_=load_official(root);model=RGBDBodyAdapter(official).cuda()
    synth=root/'datasets/cache/native_scale_v2';real=root/'datasets/cache/humman_development_v1'
    renderer=MeshRenderer(official.head_pose.faces)
    report={}
    for seed in [config['diagnostic_seed']]+config['confirmation_seeds']:
        ck=root/config['existing_run']/f'formal/cells/cross_attention_seed{seed}/run/best.pt'
        model.fusion.load_state_dict(torch.load(ck,map_location='cuda',weights_only=False)['fusion'])
        conditions=config['depth_conditions'] if seed==config['diagnostic_seed'] else config['confirmation_conditions']
        for domain,cache in [('synthetic_VAL',synth),('real_TRAIN_VAL',real)]:
            rows=json.loads((cache/'CACHE_MANIFEST.json').read_text())['records']
            if domain=='synthetic_VAL':rows=[r for r in rows if r['role']=='VAL']
            assert all(r['role']!='TEST' for r in rows)
            refs={};results={}
            # Native parameter responses use identical identity-equal aggregation;
            # only synthetic has corresponding native mesh truth.
            for condition in conditions:
                records=[]
                for start in range(0,len(rows),16):
                    chunk=rows[start:start+16];rec=[read_cache(str(cache/r['cache_file'])) for r in chunk]
                    b,f,d,v,rays,gt,target,mask,K=combine(rec)
                    donors=None
                    if condition=='cross_identity_fixed_mask':
                        dd=[read_cache(str(cache/next(x for x in rows if x['identity']!=r['identity'])['cache_file'])) for r in chunk]
                        donors=(torch.cat([x['depth'] for x in dd]).cuda(),torch.cat([x['valid'] for x in dd]).cuda())
                    with torch.no_grad():o=intervention_forward(model,b,f,d,v,rays,condition,seed*10000+start,donors)
                    values=metrics(o,gt,target,mask,K,renderer) if gt else None
                    for j,r in enumerate(chunk):
                        key=r['cache_file'];single={k:x[j:j+1] for k,x in o.items() if torch.is_tensor(x)}
                        if condition=='correct':refs[key]={k:x.cpu() for k,x in single.items()}
                        ref={k:x.cuda() for k,x in refs[key].items()}
                        response=output_change(single,ref)
                        response['global_rotation_parameter_change_rad']=float((single['global_rot']-ref['global_rot']).norm())
                        records.append(dict(identity=r['identity'],sequence=r.get('sequence'),frame=r.get('frame'),file=key,
                            role=r['role'],response=response,metrics=values[j] if values else None))
                response={role:{k:np.asarray(np.mean([np.mean([r['response'][k] for r in records if r['identity']==i],axis=0)
                    for i in sorted({r['identity'] for r in records if r['role']==role})],axis=0)).tolist()
                    for k in records[0]['response']} for role in sorted({r['role'] for r in records})}
                results[condition]=dict(responses=response,synthetic=aggregate(records) if values else None,records=records)
                report[f'{domain}_seed{seed}']=dict(checkpoint_sha256=sha(ck),conditions=results)
                (out/'DEPTH_SOURCE_DIAGNOSTIC.json').write_text(json.dumps(report,indent=2))
                print('DEPTH_DIAG',domain,seed,condition,response,flush=True)
    model._hook.remove()


def freeze_anchors(faces,out):
    rng=np.random.default_rng(20260910)
    fi=rng.choice(len(faces),16384,replace=False).astype(np.int64)
    bc=rng.dirichlet(np.ones(3),16384).astype(np.float32)
    import hashlib
    assert hashlib.sha256(fi.tobytes()).hexdigest()=='288d658dfc791fae63e81b704170b678d8e9c68f199e5b9bdb84229f3e095b0c'
    assert hashlib.sha256(bc.tobytes()).hexdigest()=='23054af1ce137268a516d30c25b1c7f27f1fbf87e59080fa1c9f060b7cdbac56'
    np.savez(out/'FROZEN_ANCHORS.npz',face_index=fi,barycentric=bc)
    return fi,bc


def fit_txyz(points,anchors):
    t=np.zeros(3);trace=[]
    for i in range(6):
        dist,near=cKDTree(anchors+t).query(points,workers=1);keep=dist<=np.quantile(dist,.8)
        step=np.clip(np.median(points[keep]-(anchors+t)[near[keep]],axis=0),-.05,.05);t+=step
        trace.append(dict(iteration=i+1,step_m=step.tolist(),raw_t_m=t.tolist()))
    fallback=bool(np.linalg.norm(t)>.17788820176363325)
    return t,np.zeros(3) if fallback else t,trace,fallback


def txyz_baseline(root,out,config):
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing
    base=root/config['existing_run'];faces=np.load(base/'real/official/faces.npy');fi,bc=freeze_anchors(faces,out)
    rows=json.loads((root/'datasets/cache/humman_development_v1/CACHE_MANIFEST.json').read_text())['records']
    pointroot=root/'datasets/heldout/humman_r3_k1_v1'
    methods={'official':base/'real/official'}
    for mode in ['rgb_only','cross_attention']:
        for seed in [11,23,37]:methods[f'{mode}_seed{seed}']=base/f'formal/cells/{mode}_seed{seed}/real'
    frozen=[]
    for r in rows:
        source=root/'datasets/registered_v1'/r['views']['kinect_000']['file']
        p=np.load(source)['points_color'];key=f"{r['sequence']}_{r['frame']:06d}"
        rng=np.random.default_rng(int(__import__('hashlib').sha256(('R31_A:'+key).encode()).hexdigest()[:16],16))
        ix=np.sort(rng.choice(len(p),min(5000,len(p)),False));frozen.append(dict(file=key,source_sha256=sha(source),indices=ix.tolist()))
    (out/'CAMERA_A_FIT_INDICES.json').write_text(json.dumps(frozen))
    tasks=[]
    for name,directory in methods.items():
        target=out/'txyz'/name;target.mkdir(parents=True,exist_ok=True)
        for r,index in zip(rows,frozen):
            key=index['file'];input_path=directory/(key+'.npz');z=np.load(input_path)
            vo=z['vertices_camera_A'];anchors=(vo[faces[fi]]*bc[:,:,None]).sum(1)
            raw_path=root/'datasets/registered_v1'/r['views']['kinect_000']['file']
            a=np.load(raw_path);points=a['points_color'][index['indices']]
            raw,applied,trace,fallback=fit_txyz(points,anchors)
            b=np.load(root/'datasets/registered_v1'/r['views']['kinect_001']['file'])
            vb=transform_camera(vo+applied,{k:a[k] for k in ['R','T']},{k:b[k] for k in ['R','T']})
            path=target/(key+'.npz');np.savez_compressed(path,vertices_camera_A=vo+applied,vertices_camera_B=vb,
                raw_translation_m=raw,applied_translation_m=applied,pred_cam_t=z['pred_cam_t']+applied,
                **{k:z[k] for k in ['global_rot','body_pose','shape','scale']})
            tasks.append(dict(method=name,identity=r['identity'],sequence=r['sequence'],frame=r['frame'],role=r['role'],
                file=str(path),points=str(pointroot/(key+'.npz')),raw_translation_m=raw.tolist(),applied_translation_m=applied.tolist(),
                fallback=fallback,trace=trace,input_mesh_sha256=sha(input_path)))
        print('TXYZ_PREDICTED',name,len(rows),flush=True)
    from evaluate_r3_humman import triangle_worker
    metric_root=str(root/'project_snapshot/docs/handoffs/real-scene-2026-09-09/public-rgbd-surface-finetuning-pilot-v1/code')
    with ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('spawn')) as pool:
        jobs=[(r['file'],r['points'],str(base/'real/official/faces.npy'),metric_root) for r in tasks]
        for i,(r,result) in enumerate(zip(tasks,pool.map(triangle_worker,jobs))):
            r['triangle']=result
            if i%232==0:print('TXYZ_EVAL',i,'/',len(tasks),flush=True)
    summaries={}
    for name,directory in methods.items():
        original=json.loads((directory/'HUMMAN_RESULTS.json').read_text())
        rr=[r for r in tasks if r['method']==name]
        summaries[name]=dict(before=original['results'],after={role:aggregate_real([r for r in rr if r['role']==role]) for role in ['TRAIN','VAL']},
            fallback_count=sum(r['fallback'] for r in rr))
    (out/'CHEAP_TXYZ_COMPARISON.json').write_text(json.dumps(dict(methods=summaries,records=tasks,
        primary='frozen exact Camera B point-to-triangle; no B data enters fitting',
        heldout_manifest_sha256=sha(pointroot/'MANIFEST.json'),config=config['txyz']),indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--task',choices=['depth','txyz'],required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);cfg=json.loads(a.config.read_text())
    (depth_diagnostic if a.task=='depth' else txyz_baseline)(a.root,a.out,cfg)
    (a.out/(a.task.upper()+'_COMPLETE.json')).write_text(json.dumps(dict(status='COMPLETE',test_used=False)))


if __name__=='__main__':main()
