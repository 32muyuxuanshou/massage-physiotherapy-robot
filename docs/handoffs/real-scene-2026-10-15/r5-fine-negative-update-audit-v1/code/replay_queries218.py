"""Replay the frozen Full Last on 218 and capture its actual 256-query input.

Local-MLP hooks observe tensors. --frozen-coarse additionally substitutes the
historical Coarse intermediate for diagnostic replay consistency. It is not a
new model or primary score. No training, changed weights, Camera B input, new
sampling, revised mask, or alternative fitting is introduced.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import torch
from torch.nn import functional as F
from frozen_model import GeometryCamera
from frozen_render_losses import MeshRenderer

BASE=Path('/raid5/xuhd/rgbd_sam3d')
WORK=BASE/'r5_fine_negative_update_audit_v1'
G=WORK/'previous/geometry'
CHECKPOINTS={11:'c4b141ede98c8405804e920401ebac982c874cf8f0e542a6e496f09dccdfc750',
    23:'2cb095cf3cfb594e97d8ce589e621b432b6009a8a5c68ba10dae69b99fc4577c',
    37:'a76926323b1d54d7840cff68f6af1f7fec47f9683614fa940438c23550c3bf2c'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def cache_path(t):
    if t['dataset']=='behave':return WORK/'cache/behave'/('s'+str(t['seed']))/(t['key']+'.pt')
    sub='native_scale_v2' if t['dataset']=='native' else 'humman_development_v1'
    return WORK/'cache'/sub/(t['key']+'.pt')


def values(x):
    if not len(x):return None
    return dict(count=len(x),median=float(np.median(x)),mean=float(np.mean(x)),
        std=float(np.std(x)),p95=float(np.quantile(x,.95)),
        mad=float(np.median(np.abs(x-np.median(x)))))


def run(a):
    torch.set_num_threads(4);torch.manual_seed(a.seed)
    checkpoint=BASE/'r5_complete_comparison_v1/checkpoints'/('full_s%d_e50_last.pt'%a.seed)
    assert sha(checkpoint)==CHECKPOINTS[a.seed]
    state=torch.load(checkpoint,map_location='cpu',weights_only=False)
    for name,relative in [('frozen_model.py','r5_complete/model.py'),('frozen_render_losses.py','render_losses.py')]:
        assert sha(WORK/'code'/name)==state['identity']['training_code_sha256'][relative],name
    faces=torch.from_numpy(np.load(G/'assets/faces.npy')).cuda()
    with np.load(G/'assets/anchors.npz') as z:
        ix=np.linspace(0,len(z['face_index'])-1,256,dtype=np.int64)
        af=torch.from_numpy(z['face_index'][ix]).cuda();bc=torch.from_numpy(z['barycentric'][ix]).cuda()
    renderer=MeshRenderer(faces)
    model=GeometryCamera(faces,af,bc,renderer,fine=True).cuda().eval()
    model.load_state_dict(state['model'],strict=True)
    tasks=[t for t in json.loads((G/'MANIFEST.json').read_text())['tasks'] if t['seed']==a.seed and t['dataset'] in a.datasets.split(',')]
    if a.key:tasks=[t for t in tasks if t['key']==a.key]
    if a.pilot:
        selected=[]
        for d in a.datasets.split(','):selected.append(next(t for t in tasks if t['dataset']==d))
        if a.seed==11 and 'real' in a.datasets.split(','):
            selected += [next(t for t in tasks if t['dataset']=='real' and t['identity']==identity) for identity in ['p001195','p001196']]
        tasks=selected
    scope='query_replay_frozen_coarse' if a.frozen_coarse else 'query_replay'
    out=WORK/('probe' if a.key else 'pilot' if a.pilot else scope)/('s'+str(a.seed));out.mkdir(parents=True,exist_ok=True)
    captured={}
    def pre(module,args):captured['input']=args[0].detach().clone()
    def post(module,args,result):captured['token']=result.detach().clone()
    before=model.local.register_forward_pre_hook(pre);after=model.local.register_forward_hook(post)
    records=[];started=time.monotonic()
    with torch.no_grad():
        for i,t in enumerate(tasks):
            path=cache_path(t);cache_hash=sha(path);rec=torch.load(path,map_location='cpu',weights_only=False)
            with np.load(G/t['prediction']) as z:gold={k:z[k] for k in z.files}
            np.testing.assert_array_equal(rec['official']['pred_vertices'].numpy().reshape(-1,3),gold['body_m'])
            expected_camera=gold.get('original_camera',np.array(t.get('original_camera'))).reshape(3)
            np.testing.assert_array_equal(rec['official']['pred_cam_t'].numpy().reshape(3),expected_camera)
            batch={k:rec['batch'][k].cuda() for k in ['cam_int','ori_img_size','bbox_scale','affine_trans']}
            official={k:rec['official'][k].cuda() for k in ['pred_vertices','pred_cam_t']}
            feature,depth,valid,rays=[rec[k].cuda() for k in ['backbone','depth','valid','rays']]
            coarse_hook=None
            if a.frozen_coarse:
                fixed=torch.from_numpy(gold['coarse_camera'].reshape(1,3)).cuda()
                coarse_hook=model.coarse.register_forward_hook(lambda module,args,result:fixed)
            camera,tr=model(feature,depth,valid,rays,official,batch)
            if coarse_hook is not None:coarse_hook.remove()
            error={name:float(np.max(np.abs(tr[name].cpu().numpy().reshape(-1)-gold[name].reshape(-1))))
                for name in ['coarse_camera','fine_delta','fine_raw_delta','eigenvalues']}
            error['final_camera']=float(np.max(np.abs(camera.cpu().numpy().reshape(3)-gold['camera_m'].reshape(3))))
            coordinate_error=max(error[k] for k in ['coarse_camera','fine_delta','fine_raw_delta','final_camera'])
            numeric_pass=coordinate_error<.0001
            geo=captured['input'][0,:,64:];token=captured['token'][0]
            observed=geo[:,-1]>.5;grid=geo[:,15:17]
            h,w=depth.shape[-2:]
            offset=grid.new_tensor([[dx*2/(w-1),dy*2/(h-1)] for dy in range(-2,3) for dx in range(-2,3)])
            neighborhood_grid=grid[None,:,None,:]+offset[None,None,:,:]
            nz=F.grid_sample(depth.float(),neighborhood_grid,mode='nearest',align_corners=True)[0,0]
            nv=F.grid_sample(valid.float(),neighborhood_grid,mode='nearest',align_corners=True)[0,0]>.5
            wins=torch.zeros(256,dtype=torch.int64,device='cuda')
            if observed.any():
                indices=observed.nonzero().flatten();owners=indices[token[observed].argmax(0)]
                wins=torch.bincount(owners,minlength=256)
            q=geo.cpu().numpy();obs=observed.cpu().numpy();nza=nz.cpu().numpy();nva=nv.cpu().numpy()
            spread=np.array([float(v.max()-v.min()) if len(v) else np.nan for v in [z[m] for z,m in zip(nza,nva)]])
            target=out/(t['dataset']+'_'+t['key']+'.npz')
            np.savez_compressed(target,geometry=q,observed=obs,neighborhood_z_m=nza,neighborhood_valid=nva,
                max_pool_wins=wins.cpu().numpy(),neighborhood_range_m=spread,
                replay_coarse_m=tr['coarse_camera'].cpu().numpy(),replay_final_m=camera.cpu().numpy())
            normals=q[:,9:12];residual=q[:,6:9]
            row={k:t[k] for k in ['dataset','seed','key','identity','role']}
            old_count=int(gold['visible_queries'].reshape(-1)[0]);count=int(obs.sum())
            row.update(source_cache_file=str(path),source_cache_sha256=cache_hash,
                output_file=str(target),output_sha256=sha(target),reproduction_max_abs=error,
                observed_queries=count,historical_observed_queries=old_count,query_count_equal=count==old_count,
                eigen_reproduction_error=error['eigenvalues'],
                coordinate_reproduction_error_m=coordinate_error,numeric_reproduction_pass=numeric_pass,
                trace_eligible=numeric_pass and count==old_count and error['eigenvalues']<.0001,
                signed_z_mm=values(q[obs,14]*1000),point_plane_mm=values(np.sum(residual[obs]*normals[obs],axis=1)*1000),
                neighbor_range_mm=values(spread[obs & np.isfinite(spread)]*1000),
                top1_max_pool_channel_fraction=float(wins.max()/128),
                top5_max_pool_channel_fraction=float(wins.sort(descending=True).values[:5].sum()/128))
            records.append(row)
            if (i+1)%20==0 or i+1==len(tasks):
                (out/'RESULTS.json').write_text(json.dumps(dict(status='RUNNING',records=records),indent=2))
                print('QUERY_REPLAY',a.seed,len(records),len(tasks),round(time.monotonic()-started,1),flush=True)
    before.remove();after.remove()
    report=dict(status='PILOT_COMPLETE' if a.pilot else 'QUERY_REPLAY_COMPLETE',records=records,
        checkpoint_sha256=CHECKPOINTS[a.seed],torch=torch.__version__,cuda=torch.version.cuda,GPU=torch.cuda.get_device_name(),
        original_weights_and_science_code_unchanged=True,training=False,camera_B_model_input=False,
        query_count_equal=sum(r['query_count_equal'] for r in records),
        numeric_reproduction_pass=sum(r['numeric_reproduction_pass'] for r in records),
        trace_eligible=sum(r['trace_eligible'] for r in records),
        frozen_historical_coarse=a.frozen_coarse,
        query_trace_scope='Replayed actual local-MLP input; original per-query masks were not stored, count equality alone is not historical per-query identity proof',
        peak_GPU_memory_bytes=torch.cuda.max_memory_allocated(),seconds=time.monotonic()-started)
    (out/'RESULTS.json').write_text(json.dumps(report,indent=2));print(report['status'],a.seed,len(records),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True)
    p.add_argument('--datasets',default='native,real,behave');p.add_argument('--pilot',action='store_true')
    p.add_argument('--key');p.add_argument('--frozen-coarse',action='store_true');run(p.parse_args())
