"""Actual native forward/backward checks; four TRAIN samples, no TEST/B input."""
import os
os.environ.setdefault('MOMENTUM_ENABLED', '0')
os.environ.setdefault('PYOPENGL_PLATFORM', 'egl')
import argparse, copy, json, time
from pathlib import Path
import numpy as np
import torch
from fusion import RGBDBodyAdapter
from fusion_r4 import R4Adapter, geometry_grid
from r3_common import load_official, read_cache, combine, cached_forward, sha
from render_losses import MeshRenderer, loss_components
from check_native_r1 import parameter_hashes


def camera_qa(output, batch, factor):
    K = batch['cam_int']
    s, tx, ty = output['pred_cam'].unbind(-1)
    denominator = -s*batch['bbox_scale'][:, 0, 0]*factor+1e-8
    center = batch['bbox_center'][:, 0]
    camera = torch.stack((tx+2*(center[:, 0]-K[:, 0, 2])/denominator,
                          -ty+2*(center[:, 1]-K[:, 1, 2])/denominator,
                          2*K[:, 0, 0]/denominator), 1)
    errors = {'camera_parameter_to_translation_max_m': float((camera-output['pred_cam_t']).abs().max())}
    for key, target in [('pred_keypoints_3d', 'pred_keypoints_2d'), ('pred_vertices', 'pred_keypoints_2d_verts')]:
        p = output[key]+camera[:, None]
        uv = torch.stack((K[:, 0, 0, None]*p[..., 0]/p[..., 2]+K[:, 0, 2, None],
                          K[:, 1, 1, None]*p[..., 1]/p[..., 2]+K[:, 1, 2, None]), -1)
        errors[target+'_max_px'] = float((uv-output[target]).abs().max())
    uv = output['pred_keypoints_2d']
    hom = torch.cat((uv, torch.ones_like(uv[..., :1])), -1)
    crop = hom @ batch['affine_trans'][:, 0].transpose(-1, -2)
    crop = crop/batch['img_size'][:, 0, None]-.5
    errors['crop_keypoint_max'] = float((crop-output['pred_keypoints_2d_cropped']).abs().max())
    assert errors['camera_parameter_to_translation_max_m'] < 2e-6
    assert errors['pred_keypoints_2d_max_px'] < .002 and errors['pred_keypoints_2d_verts_max_px'] < .002
    assert errors['crop_keypoint_max'] < 2e-6
    return errors


def main():
    p=argparse.ArgumentParser();p.add_argument('--root', type=Path, required=True);p.add_argument('--out', type=Path, required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);torch.set_num_threads(2)
    cache=a.root/'datasets/cache/native_scale_v2';manifest=json.loads((cache/'CACHE_MANIFEST.json').read_text());rows=manifest['records']
    train={r['identity'] for r in rows if r['role']=='TRAIN'};val={r['identity'] for r in rows if r['role']=='VAL'}
    assert not train & val and not any(r['role']=='TEST' for r in rows)
    selected=[r for r in rows if r['role']=='TRAIN'][::8][:4]
    b,f,d,v,rays,gt,target,mask,K=combine([read_cache(str(cache/r['cache_file'])) for r in selected])
    official,_=load_official(a.root);before=parameter_hashes(official);renderer=MeshRenderer(official.head_pose.faces)
    baseline=RGBDBodyAdapter(official).cuda()
    with torch.no_grad():reference=cached_forward(baseline,b,f,d,v,rays)
    baseline._hook.remove();reports={}
    # Independently recompute camera rays from original K and inverse RGB affine.
    affine=b['affine_trans'][:,0];bottom=affine.new_tensor([0,0,1]).reshape(1,1,3).expand(len(b['img']),1,3)
    inverse=torch.linalg.inv(torch.cat((affine,bottom),1))
    yy,xx=torch.meshgrid(torch.arange(512,device='cuda'),torch.arange(64,448,device='cuda'),indexing='ij')
    pixels=torch.stack((xx,yy,torch.ones_like(xx)),-1).float()
    source=torch.einsum('bij,hwj->bhwi',inverse,pixels)[...,:2]
    expected=(source-b['cam_int'][:,None,None,:2,2])/torch.stack((b['cam_int'][:,0,0],b['cam_int'][:,1,1]),1)[:,None,None]
    ray_error=float((expected.permute(0,3,1,2)-rays).abs().max());assert ray_error<1e-6
    invalid=torch.full_like(d,float('nan'));xyz,cover=geometry_grid(invalid,torch.zeros_like(v),rays)
    assert torch.isfinite(xyz).all() and not cover.any()
    cfg=json.loads((Path(__file__).parent/'R3_SCALE_CONFIG_V1.json').read_text())
    for mode in ['g1','g2','g3']:
        torch.manual_seed(11);model=R4Adapter(official,mode).cuda()
        with torch.no_grad():zero=cached_forward(model,b,f,d,v,rays)
        equal={k:float((zero[k]-reference[k]).abs().max()) for k in ['pred_cam','pred_cam_t','pred_vertices','pred_keypoints_2d']}
        assert equal['pred_vertices']<2e-6 and equal['pred_cam_t']<2e-6
        params=[p for p in model.fusion.parameters() if p.requires_grad]
        opt=torch.optim.AdamW(params,lr=3e-4,weight_decay=1e-4);losses=[];times=[]
        grads={}
        for step in range(16):
            started=time.monotonic();opt.zero_grad(set_to_none=True)
            output=cached_forward(model,b,f,d,v,rays)
            comp=loss_components(output,gt,target,mask,K,renderer);loss=sum(cfg['loss_weights'][k]*x for k,x in comp.items())
            assert torch.isfinite(loss);loss.backward()
            if step==15:
                for name,param in model.fusion.named_parameters():
                    if param.requires_grad and param.grad is not None:
                        assert torch.isfinite(param.grad).all(), name
                        grads[name]=float(param.grad.norm())
            torch.nn.utils.clip_grad_norm_(params,1);opt.step();losses.append(float(loss));times.append(time.monotonic()-started)
        assert losses[-1]<losses[0],f'FOUR_SAMPLE_LOSS_DID_NOT_DECREASE {mode}'
        if mode in ['g1','g3']:
            assert grads['camera.metric.0.weight']>0 and grads['camera.token.1.weight']>0
        if mode in ['g2','g3']:
            assert grads['spatial.relative_bias.0.weight']>0 and grads['spatial.log_sigma']>0
        with torch.no_grad():
            output=cached_forward(model,b,f,d,v,rays)
            missing=cached_forward(model,b,f,d,torch.zeros_like(v),rays)
        missing_error=float((missing['pred_vertices']-reference['pred_vertices']).abs().max())
        missing_cam_error=float((missing['pred_cam_t']-reference['pred_cam_t']).abs().max())
        assert missing_error<2e-6 and missing_cam_error<2e-6
        report=dict(status='PASS',zero_initial_max_abs=equal,missing_vertices_m=missing_error,missing_camera_m=missing_cam_error,
                    loss_curve=losses,internal_grad_norms=grads,camera_projection=camera_qa(output,b,official.head_camera.default_scale_factor),
                    trainable_parameters=sum(p.numel() for p in params),steady_four_sample_seconds=float(np.mean(times[4:])))
        model.remove_hooks();reports[mode]=report;print('QA_PASS',mode,losses[0],losses[-1],flush=True)
    assert before==parameter_hashes(official),'OFFICIAL_WEIGHT_CHANGED'
    # Existing R3 adapter + checkpoint must still match its saved real native mesh.
    real=a.root/'datasets/cache/humman_development_v1';rr=json.loads((real/'CACHE_MANIFEST.json').read_text())['records'][0]
    rb,rf,rd,rv,rray,*_=combine([read_cache(str(real/rr['cache_file']))])
    old=RGBDBodyAdapter(official).cuda();checkpoint=a.root/'runs/r3_multiseed_v1/formal/cells/cross_attention_seed11/run/best.pt'
    old.fusion.load_state_dict(torch.load(checkpoint,weights_only=False)['fusion'])
    with torch.no_grad():output=cached_forward(old,rb,rf,rd,rv,rray)
    saved=np.load(checkpoint.parent.parent/'real'/(Path(rr['cache_file']).stem+'.npz'))
    regression=float(np.max(np.abs((output['pred_vertices']+output['pred_cam_t'][:,None]).cpu().numpy()[0]-saved['vertices_camera_A'])))
    assert regression<1e-5,regression;old._hook.remove()
    report=dict(status='PASS',modes=reports,source_files=selected,ray_reconstruction_max=ray_error,
                official_weights_unchanged=True,old_R3_checkpoint_regression_max_m=regression,
                test_loaded=False,camera_B_read=False,peak_memory_bytes=torch.cuda.max_memory_allocated())
    (a.out/'NATIVE_SELF_REVIEW_QA.json').write_text(json.dumps(report,indent=2));print('R4_NATIVE_QA_COMPLETE',flush=True)


if __name__=='__main__':main()
