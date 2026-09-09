"""Nine development images; sparse-contour gradient and checkpoint prototype only."""
import os
os.environ['PYOPENGL_PLATFORM']='egl'
import json,sys,time,hashlib
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from contour_loss import contour_loss, _finite_difference_check

O=Path(__file__).resolve().parent;P=Path('/raid5/xuhd/sam3d_s01_pilot_20260906')
sys.path.insert(0,str(P/'sam-3d-body'))
from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
from sam_3d_body.data.utils.prepare_batch import prepare_batch
from sam_3d_body.utils import recursive_to

torch.manual_seed(20260908);np.random.seed(20260908)
_finite_difference_check()
cfg_run=json.loads((O/'protocol.json').read_text());records=json.loads((O/'samples.json').read_text())
refs=json.loads((O/'fixed_references.json').read_text())['samples']
model,cfg=load_sam_3d_body(str(P/'weights/model.ckpt'),device='cuda',mhr_path=str(P/'weights/assets/mhr_model.pt'))
model.eval();model.requires_grad_(False)
heads={'pose':model.head_pose.proj,'camera':model.head_camera.proj}
for h in heads.values():h.requires_grad_(True)
params=[p for p in model.parameters() if p.requires_grad]
initial={k:{n:t.detach().cpu().clone() for n,t in h.state_dict().items()} for k,h in heads.items()}
est=SAM3DBodyEstimator(model,cfg);faces=torch.as_tensor(est.faces,dtype=torch.long,device='cuda')
pelvis=model.pelvis_idx
capture=False;raw=[]
def hook(module,inputs,output):
    if capture and output.requires_grad:output.retain_grad();raw.append(output)
handle=model.head_pose.proj.register_forward_hook(hook)
def batch_for(r):
    src=Path(r['source']);assert hashlib.sha256(src.read_bytes()).hexdigest()==r['sha256']
    rgb=np.asarray(Image.open(src).convert('RGB')).copy()
    b=prepare_batch(rgb,est.transform,np.asarray([r['bbox']],np.float32),None,None)
    b=recursive_to(b,'cuda');b['cam_int']=torch.tensor([r['K']],device='cuda').to(b['img'])
    model._initialize_batch(b);return b
batches={r['id']:batch_for(r) for r in records}
def forward(r):return model.forward_step(batches[r['id']],decoder_type='body')['mhr']
def uv_for(out,r):
    v=out['pred_vertices'][0].float()+out['pred_cam_t'][0].float()
    p=v@v.new_tensor(r['K']).T
    assert torch.isfinite(p).all() and (p[:,2]>0).all()
    return p[:,:2]/p[:,2:]
def generic_loss(out,r):
    t2=out['pred_keypoints_2d'].new_tensor(r['target2'])[None,:,:2]
    t3=out['pred_keypoints_3d'].new_tensor(r['target3'])[None]
    p2=out['pred_keypoints_2d'];p3=out['pred_keypoints_3d']
    size=p2.new_tensor(r['wh'])
    p3=p3-p3[:,pelvis].mean(1,keepdim=True);t3=t3-t3[:,pelvis].mean(1,keepdim=True)
    return F.smooth_l1_loss(p2/size,t2/size)+F.smooth_l1_loss(p3,t3)
target=next(r for r in records if r['kind']=='contour');generic=[r for r in records if r['kind']=='mhr_joints']
with torch.no_grad():teacher={k:v.detach().clone() for k,v in forward(target).items() if k in ['shape','scale','pred_keypoints_3d','pred_cam_t']}
def target_loss(out):
    edge,x=contour_loss(uv_for(out,target),faces,refs,target['bbox'][2]-target['bbox'][0])
    prior=sum(F.mse_loss(out[k].float(),teacher[k].float()) for k in teacher)
    return cfg_run['edge_weight']*edge+cfg_run['prior_weight']*prior,edge,prior,x
def evaluate(tag):
    result=[]
    with torch.no_grad():
        for r in records:
            out=forward(r)
            if r['kind']=='contour':
                total,edge,prior,x=target_loss(out);errors=(x-x.new_tensor([v['reference_x'] for v in refs])).abs()
                result.append(dict(id=r['id'],edge_loss=float(edge),prior=float(prior),mean_contour_px=float(errors.mean()),contour_errors_px=errors.cpu().tolist()))
                np.savez_compressed(O/(tag+'_N1.npz'),vertices_camera=(out['pred_vertices'][0]+out['pred_cam_t'][0]).cpu().numpy(),K=np.array(r['K']),contour_x=x.cpu().numpy())
            else:result.append(dict(id=r['id'],joint_loss=float(generic_loss(out,r))))
    (O/(tag+'_metrics.json')).write_text(json.dumps(result,indent=2));return result
start=time.time();torch.cuda.reset_peak_memory_stats();before=evaluate('before')
# Probe only the real sparse edge loss, not priors or generic joint supervision.
capture=True;raw.clear();out=forward(target);edge=target_loss(out)[1];edge.backward();capture=False
groups={'rotation':(0,6),'body':(6,266),'shape':(266,311),'scale':(311,339),'hands':(339,447)}
norms={name:float(sum(t.grad[...,a:b].float().square().sum() for t in raw if t.grad is not None).sqrt()) for name,(a,b) in groups.items()}
norms['camera_head']=float(sum(p.grad.float().square().sum() for p in heads['camera'].parameters() if p.grad is not None).sqrt())
assert all(np.isfinite(v) for v in norms.values())
assert all(norms[k]>0 for k in ['shape','scale','camera_head'])
assert not any(p.grad is not None for p in model.parameters() if not p.requires_grad)
(O/'gradient_probe.json').write_text(json.dumps(dict(status='REAL_SPARSE_CONTOUR_BACKWARD_PASSED',norms=norms,trainable_parameters=sum(p.numel() for p in params),raw_head_widths=[t.shape[-1] for t in raw]),indent=2))
print('GRADIENT_PASS',norms,flush=True)
del out,edge;raw.clear();model.zero_grad(set_to_none=True)
opt=torch.optim.AdamW(params,lr=cfg_run['lr'],weight_decay=0.0);history=[]
for step in range(cfg_run['steps']):
    r=target if step%2==0 else generic[(step//2)%len(generic)]
    opt.zero_grad(set_to_none=True);out=forward(r)
    if r['kind']=='contour':loss,edge,prior,x=target_loss(out);details=dict(edge=float(edge.detach()),prior=float(prior.detach()))
    else:loss=generic_loss(out,r);details={}
    assert torch.isfinite(loss);loss.backward()
    gn=torch.nn.utils.clip_grad_norm_(params,1.0);assert torch.isfinite(gn)
    opt.step();history.append(dict(step=step+1,id=r['id'],loss=float(loss.detach()),gradient_norm=float(gn),**details))
    (O/'history.json').write_text(json.dumps(history,indent=2));print('STEP',history[-1],flush=True)
    del out,loss
after=evaluate('after')
checkpoint=dict(status='PROTOTYPE_NOT_VALIDATED_FOR_DEPLOYMENT',heads={k:{n:t.detach().cpu() for n,t in h.state_dict().items()} for k,h in heads.items()},optimizer=opt.state_dict(),protocol=cfg_run,base_checkpoint_sha256=hashlib.sha256((P/'weights/model.ckpt').read_bytes()).hexdigest())
torch.save(checkpoint,O/'prototype_heads.pt')
# Restore original heads first, then load saved heads into the same frozen base.
for k,h in heads.items():h.load_state_dict(initial[k],strict=True)
saved=torch.load(O/'prototype_heads.pt',map_location='cpu',weights_only=False)
for k,h in heads.items():h.load_state_dict(saved['heads'][k],strict=True)
reloaded=evaluate('reloaded');a=np.load(O/'after_N1.npz');b=np.load(O/'reloaded_N1.npz');maxdiff=float(np.abs(a['vertices_camera']-b['vertices_camera']).max())
assert maxdiff<1e-6
report=dict(status='PROTOTYPE_TRAIN_SAVE_RELOAD_COMPLETE',images=len(records),steps=len(history),seed=20260908,seconds=time.time()-start,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,reload_vertex_max_abs_m=maxdiff,gradient_norms=norms,before=before,after=after,scope='Training/development samples only; 8 official joint targets + 1 image with 6 sparse contour references. No dense renderer or generalization claim.',checkpoint_sha256=hashlib.sha256((O/'prototype_heads.pt').read_bytes()).hexdigest())
(O/'report.json').write_text(json.dumps(report,indent=2));print('COMPLETE',json.dumps(report),flush=True)
