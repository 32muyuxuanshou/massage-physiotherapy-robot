"""The original Fine modules with an immutable, precomputed Coarse context."""
from pathlib import Path
from functools import lru_cache
import json,hashlib
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from frozen_model import masked_pool,directional_filter

BASE=Path('/raid5/xuhd/rgbd_sam3d')
WORK=BASE/'r51_fine_supervision_ablation_v1'
OLD=BASE/'r5_fine_negative_update_audit_v1'
G=OLD/'previous/geometry'
CFG=json.loads((WORK/'EXPERIMENT.json').read_text())


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    return h.hexdigest()


class FineOnly(nn.Module):
    def __init__(self,parent):
        super().__init__()
        self.rgb_local=parent.rgb_local;self.local=parent.local;self.fine_head=parent.fine_head

    def forward(self,x):
        # 1x1 affine projection commutes with in-bounds bilinear sampling.
        rgb=F.linear(x['rgb_queries'].float(),self.rgb_local.weight[:,:,0,0],self.rgb_local.bias)
        geometry=x['geometry'].float();observed=geometry[:,:,-1]>.5
        raw=self.fine_head(masked_pool(self.local(torch.cat((rgb,geometry),-1)),observed))
        delta,eigen=directional_filter(raw,geometry[:,:,9:12],observed)
        delta=torch.where(observed.any(1)[:,None],delta,torch.zeros_like(delta))
        return x['coarse']+delta,delta


def load_parent(seed,renderer):
    from frozen_model import GeometryCamera
    faces=torch.from_numpy(np.load(G/'assets/faces.npy')).cuda()
    with np.load(G/'assets/anchors.npz') as z:
        ix=np.linspace(0,len(z['face_index'])-1,256,dtype=np.int64)
        fi=torch.from_numpy(z['face_index'][ix]).cuda();bc=torch.from_numpy(z['barycentric'][ix]).cuda()
    p=BASE/'r5_complete_comparison_v1/checkpoints'/('full_s%d_e50_last.pt'%seed)
    expected={11:'c4b141ede98c8405804e920401ebac982c874cf8f0e542a6e496f09dccdfc750',23:'2cb095cf3cfb594e97d8ce589e621b432b6009a8a5c68ba10dae69b99fc4577c',37:'a76926323b1d54d7840cff68f6af1f7fec47f9683614fa940438c23550c3bf2c'}
    assert sha(p)==expected[seed]
    state=torch.load(p,map_location='cpu',weights_only=False)
    for name,relative in [('frozen_model.py','r5_complete/model.py'),('frozen_render_losses.py','render_losses.py')]:
        assert sha(WORK/'code'/name)==state['identity']['training_code_sha256'][relative]
    model=GeometryCamera(faces,fi,bc,renderer).cuda().eval();model.load_state_dict(state['model'])
    model.coarse.requires_grad_(False)
    return model


@lru_cache(maxsize=3072)
def read_prepared(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}


def batch(rows,seed,device='cuda'):
    arrays=[read_prepared(str(WORK/'prepared'/('s%d'%seed)/r['domain']/(r['key']+'.npz'))) for r in rows]
    names=['rgb_queries','geometry','coarse','body','target_depth','target_mask','K']
    if rows[0]['domain']=='native':names+=['gt_camera','gt_body']
    x={k:torch.from_numpy(np.stack([a[k] for a in arrays])).to(device) for k in names}
    x['surface_weight']=torch.tensor([r.get('surface_weight',1.) for r in rows],device=device)
    return x


def objective(model,renderer,x,domain,arm,l2_lambda=0.):
    camera,delta=model(x);rendered,sil=renderer(x['body']+camera[:,None],x['K'])
    mask=x['target_mask'].bool();weight=x['surface_weight']
    z=(F.smooth_l1_loss(rendered,x['target_depth'],beta=.02,reduction='none')*mask).sum((1,2))/mask.sum((1,2))
    inter=(sil*mask).sum((1,2));union=(sil+mask-sil*mask).sum((1,2))
    terms=dict(z=(z*weight).mean(),sil=((1-inter/union.clamp_min(1))*weight).mean(),l2=delta.square().sum(1).mean())
    wz,ws=(.2,.2) if domain=='native' else (CFG['scan_depth_weight'],CFG['scan_silhouette_weight'])
    camera_loss=F.smooth_l1_loss(camera,x['gt_camera'],beta=.05) if domain=='native' else camera.sum()*0
    terms['camera']=camera_loss
    weighted=dict(camera=arm['camera_weight']*camera_loss,z=wz*terms['z'],sil=ws*terms['sil'],l2=l2_lambda*terms['l2'])
    return sum(weighted.values()),weighted,terms,camera,delta


def gradients(model,weighted):
    params=list(model.fine_head[-1].parameters())
    vectors={}
    for k,v in weighted.items():
        grads=torch.autograd.grad(v,params,retain_graph=True,allow_unused=False)
        vectors[k]=torch.cat([g.flatten() for g in grads])
    cam=vectors['camera'];surface=vectors['z']+vectors['sil']
    value={k:float(v.norm()) for k,v in vectors.items()}
    value.update(surface=float(surface.norm()),camera_surface_cosine=float(F.cosine_similarity(cam[None],surface[None])) if cam.norm()>0 and surface.norm()>0 else None)
    return value


def aggregate(rows,domain):
    fields=['full_mask_median_mm','full_mask_p95_mm','hit_rate','iou','common_median_mm','common_p95_mm']
    if domain=='native':fields+=['camera_mm','vertex_camera_mm','orthogonal_mm']
    def mean(items):return {k:float(np.mean([r[k] for r in items if r[k] is not None])) if any(r[k] is not None for r in items) else None for k in fields}
    identities={}
    for identity in sorted({r['identity'] for r in rows}):
        rr=[r for r in rows if r['identity']==identity]
        if domain=='native':identities[identity]=mean(rr)
        else:
            assets=[]
            for asset in sorted({r['asset_id'] for r in rr}):
                ar=[r for r in rr if r['asset_id']==asset]
                assets.append(mean([mean([r for r in ar if r['camera_group']==g]) for g in sorted({r['camera_group'] for r in ar})]))
            identities[identity]=mean(assets)
    return dict(equal_mean=mean(list(identities.values())),per_identity=identities)


@torch.no_grad()
def evaluate(model,renderer,rows,seed):
    results=[];model.eval()
    for offset in range(0,len(rows),4):
        rr=rows[offset:offset+4];x=batch(rr,seed);camera,delta=model(x)
        depth,sil=renderer(x['body']+camera[:,None],x['K'])
        initial=torch.from_numpy(np.stack([read_prepared(str(WORK/'prepared'/('s%d'%seed)/r['domain']/(r['key']+'.npz')))['initial_camera'] for r in rr])).cuda()
        baseline,_=renderer(x['body']+initial[:,None],x['K'])
        for i,r in enumerate(rr):
            mask=x['target_mask'][i].bool();hit=mask&(depth[i]>0);common=hit&(baseline[i]>0)
            error=(depth[i]-x['target_depth'][i]).abs()*1000
            d=dict(key=r['key'],identity=r['identity'],asset_id=r.get('asset_id'),camera_group=r.get('camera_group'),
                full_mask_median_mm=float(error[mask].median()),full_mask_p95_mm=float(torch.quantile(error[mask],.95)),
                hit_rate=float(hit.sum()/mask.sum()),iou=float((sil[i]*mask).sum()/(sil[i]+mask-sil[i]*mask).sum().clamp_min(1)),
                common_median_mm=float(error[common].median()) if common.any() else None,
                common_p95_mm=float(torch.quantile(error[common],.95)) if common.any() else None,
                camera_m=camera[i].cpu().tolist(),fine_delta_m=delta[i].cpu().tolist())
            if r['domain']=='native':
                need=x['gt_camera'][i]-x['coarse'][i];projection=(delta[i]*need).sum()/need.square().sum().clamp_min(1e-20)
                d.update(camera_mm=float((camera[i]-x['gt_camera'][i]).norm()*1000),
                    vertex_camera_mm=float((x['body'][i]+camera[i]-x['gt_body'][i]-x['gt_camera'][i]).norm(dim=1).mean()*1000),
                    orthogonal_mm=float((delta[i]-projection*need).norm()*1000))
            results.append(d)
    return dict(records=results,aggregate=aggregate(results,rows[0]['domain']))
