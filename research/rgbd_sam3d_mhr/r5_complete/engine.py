"""Existing adapters stay unchanged; one concrete common experiment entry."""
import copy,json,sys
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'r5_camera_only'))
import roma
from fusion import RGBDBodyAdapter
from fusion_r4 import R4Adapter
from r3_common import load_official,cached_forward
from render_losses import MeshRenderer
from camera_head import CameraHead
from model import GeometryCamera,replace_camera
from data import compact_features


class Engine(nn.Module):
    def __init__(self,mode,paths,device='cuda'):
        super().__init__();self.mode=mode
        faces=torch.from_numpy(np.load(paths['faces'])).to(device)
        self.renderer=MeshRenderer(faces)
        if mode in ['rgb_only','residual','cross_attention','g1']:
            official,_=load_official(Path(paths['official_root']))
            self.model=(R4Adapter(official,'g1') if mode=='g1' else RGBDBodyAdapter(official,mode))
        elif mode=='pooled_mlp':
            normalizer=json.loads(Path(paths['normalizer']).read_text())
            self.model=CameraHead(normalizer['mean'],normalizer['std'],'metric_xyz')
        else:
            assert mode in ['coarse','full']
            with np.load(paths['anchors']) as z:
                index=np.linspace(0,len(z['face_index'])-1,256,dtype=np.int64)
                af=torch.from_numpy(z['face_index'][index]).to(device)
                bc=torch.from_numpy(z['barycentric'][index]).to(device)
            self.model=GeometryCamera(faces,af,bc,self.renderer,fine=mode=='full')
        self.to(device)

    def forward(self,x,enable_fine=True):
        if self.mode in ['rgb_only','residual','cross_attention','g1']:
            o=cached_forward(self.model,x['batch'],x['feature'],x['depth'],x['valid'],x['rays'])
            return o,dict(coarse_camera=o['pred_cam_t'],fine_delta=torch.zeros_like(o['pred_cam_t']))
        if self.mode=='pooled_mlp':
            b=x['batch'];t0=x['official']['pred_cam_t'].float()
            c=self.model(x['feature'].float().mean((2,3)),compact_features(x),t0,
                b['cam_int'].float(),b['bbox_center'].reshape(-1,2).float(),
                b['bbox_scale'].reshape(-1,2).float(),x['valid'].flatten(1).any(1))
            trace=dict(coarse_camera=c,fine_delta=torch.zeros_like(c))
        else:
            c,trace=self.model(x['feature'],x['depth'],x['valid'],x['rays'],x['official'],x['batch'],enable_fine)
        return replace_camera(x['official'],c),trace

    def trainable(self):
        return [p for p in self.parameters() if p.requires_grad]

    def checkpoint_state(self):
        if self.mode in ['rgb_only','residual','cross_attention','g1']:
            return self.model.fusion.state_dict()
        return self.model.state_dict()

    def official_reference(self,x):
        """Same-batch Official; avoids comparing batch GEMMs to old single-frame cache."""
        if self.mode not in ['rgb_only','residual','cross_attention','g1']:
            return x['official']
        official=self.model.official
        backbone=official.backbone;original=backbone.forward
        backbone.forward=lambda image,**kwargs:x['feature']
        try:
            b=copy.deepcopy(x['batch']);official._initialize_batch(b)
            return official.forward_step(b,decoder_type='body')['mhr']
        finally:backbone.forward=original

    def load_checkpoint_state(self,state):
        if self.mode in ['rgb_only','residual','cross_attention','g1']:
            self.model.fusion.load_state_dict(state)
        else:self.model.load_state_dict(state)

    def close(self):
        if self.mode in ['rgb_only','residual','cross_attention','g1']:self.model.remove_hooks() if self.mode=='g1' else self.model._hook.remove()


def surface_components(engine,o,x):
    rendered,sil=engine.renderer(o['pred_vertices'].float()+o['pred_cam_t'].float()[:,None],x['K'].float())
    mask=x['target_mask'].bool()
    lz=(F.smooth_l1_loss(rendered,x['target_depth'].float(),beta=.02,reduction='none')*mask).sum((1,2))/mask.sum((1,2)).clamp_min(1)
    intersection=(sil*mask).sum((1,2));union=(sil+mask-sil*mask).sum((1,2))
    weight=x['surface_weight']
    return dict(rendered_depth=(lz*weight).mean(),silhouette=((1-intersection/union.clamp_min(1))*weight).mean())


def loss(engine,o,trace,x,cfg,weak_weights,enable_fine=True):
    components=surface_components(engine,o,x)
    if not x['truth']:
        value=sum(weak_weights[k]*v for k,v in components.items())
        return value,components
    gt=x['truth']
    components.update(vertices=F.smooth_l1_loss(o['pred_vertices'],gt['pred_vertices'],beta=.02),
        joints=F.smooth_l1_loss(o['pred_joint_coords'],gt['pred_joint_coords'],beta=.02),
        camera=F.smooth_l1_loss(o['pred_cam_t'],gt['pred_cam_t'],beta=.05),
        body_pose=(1-torch.cos(o['body_pose']-gt['body_pose'])).mean(),
        global_rotation=F.mse_loss(roma.euler_to_rotmat('xyz',o['global_rot']),roma.euler_to_rotmat('xyz',gt['global_rot'])),
        shape=F.mse_loss(o['shape'],gt['shape']),scale=F.mse_loss(o['scale'],gt['scale']),
        hand=F.mse_loss(o['hand'],gt['hand']))
    value=sum(cfg['loss_weights'][k]*v for k,v in components.items())
    if engine.mode=='full' and enable_fine:
        components['coarse_camera_aux']=F.smooth_l1_loss(trace['coarse_camera'],gt['pred_cam_t'],beta=.05)
        value=value+cfg['coarse_camera_aux_weight']*components['coarse_camera_aux']
    return value,components


def native_values(o,x):
    gt=x['truth'];body=o['pred_vertices'].float();target=gt['pred_vertices'].float()
    d=body-target;camera=o['pred_cam_t'].float();tc=gt['pred_cam_t'].float()
    return dict(vertex_camera_mm=(d+(camera-tc)[:,None]).norm(dim=2).mean(1)*1000,
        vertex_body_mm=d.norm(dim=2).mean(1)*1000,
        vertex_translation_removed_mm=(d-d.mean(1,keepdim=True)).norm(dim=2).mean(1)*1000,
        camera_mm=(camera-tc).norm(dim=1)*1000,
        joint_camera_mm=(o['pred_joint_coords']+camera[:,None]-gt['pred_joint_coords']-tc[:,None]).norm(dim=2).mean(1)*1000)
