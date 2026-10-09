"""Two separate, native-MHR candidates; no free vertex deformation.

A: DFormerv2-inspired geometric attention bias, extended to calibrated XYZ.
B: UniSH-inspired explicit metric alignment, extended with native MHR queries.
These are our pilot adaptations, not reproductions of those papers.
"""
import math
import torch
from torch import nn
from torch.nn import functional as F
from fusion import RGBDBodyAdapter,SpatialDepthFusion,metric_features


def patch_geometry(depth,valid,rays):
    """Mean measured XYZ per 16x16 patch, in the original RGB camera frame."""
    coverage=F.avg_pool2d(valid.float(),16,16)
    xyz=torch.cat((rays*depth,depth),1)*valid
    xyz=F.avg_pool2d(xyz,16,16)/coverage.clamp_min(1e-6)
    rr=F.avg_pool2d(rays,16,16)
    return xyz.flatten(2).transpose(1,2),rr.flatten(2).transpose(1,2),coverage.flatten(1)>0


class GeometryAttention(SpatialDepthFusion):
    def __init__(self,channels,hidden=256,heads=8):
        super().__init__(channels,hidden,heads,'cross_attention')
        self.geometry_projection=nn.Sequential(nn.Linear(3,hidden),nn.GELU(),nn.Linear(hidden,hidden))
        self.metric_context=nn.Sequential(nn.Linear(6,hidden),nn.GELU(),nn.Linear(hidden,channels))
        self.heads=heads
        self.disable_geometry_bias=False
        self.disable_metric_context=False

    def forward(self,rgb,d,valid,rays):
        features,valid=metric_features(d,valid,rays)
        depth=self.depth_encoder(features)
        xyz,rr,coverage=patch_geometry(d,valid,rays)
        available=coverage.any(1);delta=torch.zeros_like(rgb)
        if available.any():
            ix=available.nonzero().flatten();xyz=xyz[ix];rr=rr[ix];cover=coverage[ix]
            q=self.rgb_projection(rgb[ix]).flatten(2).transpose(1,2)
            kv=depth[ix].flatten(2).transpose(1,2)+self.geometry_projection(xyz)
            if self.disable_geometry_bias:bias=-torch.cdist(rr,rr).square()/(2*.2**2)
            else:
                distance=torch.cdist(xyz,xyz).square()/(2*.15**2)
                # RGB queries without measured depth retain calibrated ray locality.
                distance=distance*cover[:,:,None]
                bias=-distance-torch.cdist(rr,rr).square()/(2*.2**2)
            bias=bias.masked_fill(~cover[:,None,:],float('-inf'))
            bias=bias[:,None].expand(-1,self.heads,-1,-1).reshape(-1,xyz.shape[1],xyz.shape[1])
            fused,_=self.attention(q,kv,kv,attn_mask=bias,need_weights=False)
            fused=fused.transpose(1,2).reshape(len(ix),-1,*rgb.shape[-2:])
            dd=self.output_projection(fused)
            if not self.disable_metric_context:
                count=cover.sum(1,keepdim=True).clamp_min(1)
                mean=(xyz*cover[:,:,None]).sum(1)/count
                var=((xyz-mean[:,None]).square()*cover[:,:,None]).sum(1)/count
                context=self.metric_context(torch.cat((mean,var.sqrt()),1))
                dd=dd+context[:,:,None,None]
            delta=delta.index_copy(0,ix,dd)
        return rgb+self.gate*delta


class MHRGeometryRefinement(nn.Module):
    # Official native mhr70 body landmarks plus four torso interpolants.
    keypoint_ids=[0,5,6,7,8,9,10,11,12,13,14,15,17,18,20,41,62,67,68,69]

    def __init__(self,channels,hidden=256):
        super().__init__()
        self.rgb_projection=nn.Conv2d(channels,hidden,1)
        self.geometry_projection=nn.Sequential(nn.Linear(10,hidden),nn.GELU(),nn.Linear(hidden,hidden))
        self.query_embedding=nn.Parameter(torch.randn(24,hidden)*.02)
        self.structure_attention=nn.MultiheadAttention(hidden,8,batch_first=True)
        self.readout=nn.Sequential(nn.Linear(hidden*24,hidden),nn.GELU(),nn.Linear(hidden,212))
        nn.init.zeros_(self.readout[-1].weight);nn.init.zeros_(self.readout[-1].bias)
        pose_mask=torch.ones(133);pose_mask[124:]=0
        self.register_buffer('pose_update_mask',pose_mask)
        self.disable_correspondence=False
        self.translation_only=False

    def forward(self,base,rgb,d,valid,rays):
        xyz,rr,coverage=patch_geometry(d,valid,rays)
        joints=base['pred_keypoints_3d']+base['pred_cam_t'][:,None]
        query=joints[:,self.keypoint_ids]
        shoulder=(joints[:,5]+joints[:,6])/2;hip=(joints[:,9]+joints[:,10])/2
        query=torch.cat((query,torch.stack((shoulder,hip,.75*shoulder+.25*hip,.25*shoulder+.75*hip),1)),1)
        vertices=base['pred_vertices']+base['pred_cam_t'][:,None]
        # Anatomical query -> nearby frontmost predicted surface anchor. Selection
        # uses native prediction and Camera A only; never observed Camera B.
        vray=vertices[:,:,:2]/vertices[:,:,2:].clamp_min(.05)
        qray=query[:,:,:2]/query[:,:,2:].clamp_min(.05)
        candidates=torch.cdist(qray,vray).topk(32,largest=False).indices
        b=torch.arange(len(vertices),device=vertices.device)[:,None,None]
        front=vertices[b,candidates];chosen=front[:,:,:,2].argmin(-1)
        anchor=front[torch.arange(len(vertices),device=vertices.device)[:,None],
            torch.arange(24,device=vertices.device)[None],chosen]
        aray=anchor[:,:,:2]/anchor[:,:,2:].clamp_min(.05)
        score=-torch.cdist(anchor,xyz).square()/(2*.2**2)-torch.cdist(aray,rr).square()/(2*.2**2)
        score=score.masked_fill(~coverage[:,None],-1e4)
        weight=score.softmax(-1)*coverage[:,None]
        weight=weight/weight.sum(-1,keepdim=True).clamp_min(1e-6)
        if self.disable_correspondence:
            weight=(coverage.float()/coverage.sum(-1,keepdim=True).clamp_min(1))[:,None].expand(-1,24,-1)
        observed=weight@xyz
        projected=self.rgb_projection(rgb).flatten(2).transpose(1,2)
        visual=weight@projected
        residual=observed-anchor
        if self.disable_correspondence:residual=torch.zeros_like(residual)
        distance=(residual.square().sum(-1)+1e-12).sqrt()
        support=(weight.sum(-1)>0).float()
        geometry=torch.cat((anchor,observed,residual,distance[:,:,None]),-1)
        tokens=visual+self.geometry_projection(geometry)+self.query_embedding[None]
        structure,_=self.structure_attention(tokens,tokens,tokens,need_weights=False)
        delta=self.readout((tokens+structure).flatten(1))
        delta=delta*coverage.any(1)[:,None]
        # Native parameter increments, not independent vertex displacements.
        result=dict(base)
        result['pred_cam_t']=base['pred_cam_t']+.1*delta[:,:3]
        if self.translation_only:delta=torch.cat((delta[:,:3],torch.zeros_like(delta[:,3:])),1)
        result['global_rot']=base['global_rot']+.1*delta[:,3:6]
        result['body_pose']=base['body_pose']+.1*delta[:,6:139]*self.pose_update_mask
        result['shape']=base['shape']+.1*delta[:,139:184]
        result['scale']=base['scale']+.05*delta[:,184:212]
        return result


class R31Adapter(RGBDBodyAdapter):
    def __init__(self,official,mode='cross_attention'):
        super().__init__(official,mode='cross_attention' if mode in ['geometry_attention','mhr_refinement'] else mode)
        self.mode=mode
        if mode=='geometry_attention':self.fusion=GeometryAttention(official.backbone.embed_dims)
        elif mode=='mhr_refinement':self.fusion=MHRGeometryRefinement(official.backbone.embed_dims)
        self._rgb_feature=None

    def _fuse(self,module,args,output):
        if self.mode=='mhr_refinement':
            self._rgb_feature=(output[-1] if isinstance(output,tuple) else output).float()
            return output
        return super()._fuse(module,args,output)

    def forward(self,batch,d,valid,rays):
        base=super().forward(batch,d,valid,rays)
        if self.mode!='mhr_refinement':return base
        refined=self.fusion(base,self._rgb_feature,d,valid,rays)
        v,k,j,mp,jr=self.official.head_pose.mhr_forward(global_trans=torch.zeros_like(refined['pred_cam_t']),
            global_rot=refined['global_rot'],body_pose_params=refined['body_pose'],hand_pose_params=refined['hand'],
            scale_params=refined['scale'],shape_params=refined['shape'],expr_params=refined.get('face'),
            return_keypoints=True,return_joint_coords=True,return_model_params=True,return_joint_rotations=True)
        flip=v.new_tensor([1.,-1.,-1.])
        refined['pred_vertices']=v*flip
        refined['pred_keypoints_3d']=k[:,:70]*flip
        refined['pred_joint_coords']=j*flip
        refined['mhr_model_params']=mp
        refined['joint_global_rots']=jr
        self._rgb_feature=None
        return refined
