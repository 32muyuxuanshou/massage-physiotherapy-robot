"""Differentiable perspective mesh Z and antialiased silhouette, metres/OpenCV.

Nvdiffrast API/camera convention: https://nvlabs.github.io/nvdiffrast/
Projection matches pyrender IntrinsicsCamera, no mesh-driven camera adjustment.
"""
import torch
import roma
import nvdiffrast.torch as dr
from torch.nn import functional as F


class MeshRenderer:
    def __init__(self, faces, height=480, width=640):
        self.ctx=dr.RasterizeCudaContext()
        self.faces=faces.to(dtype=torch.int32,device='cuda').contiguous()
        self.height,self.width=height,width

    def __call__(self, vertices_camera, K):
        x,y,z=vertices_camera.float().unbind(-1)
        near,far=.05,20.
        h,w=self.height,self.width
        # OpenCV y-down -> OpenGL y-up; w_clip = positive camera Z.
        # CV integer (u,v) pixel centres -> viewport half-integer centres.
        clip=torch.stack((2*K[:,0,0,None]/w*x+(2*(K[:,0,2,None]+.5)/w-1)*z,
                         -2*K[:,1,1,None]/h*y+(1-2*(K[:,1,2,None]+.5)/h)*z,
                         (far+near)/(far-near)*z-2*far*near/(far-near),z),-1).contiguous()
        rast,_=dr.rasterize(self.ctx,clip,self.faces,resolution=[h,w],grad_db=False)
        depth,_=dr.interpolate(vertices_camera[...,2:3].float().contiguous(),rast,self.faces)
        coverage=(rast[...,3:]>0).float()
        silhouette=dr.antialias(coverage, rast, clip, self.faces)
        # Nvdiffrast rows start at bottom. Return ordinary top-down images.
        return depth[...,0].flip(1),silhouette[...,0].flip(1)


def loss_components(output, truth, depth, mask, K, renderer):
    # All targets are native MHR. No SMPL -> MHR pseudo-label substitution.
    vertices=output['pred_vertices']
    rendered,silhouette=renderer(vertices+output['pred_cam_t'][:,None],K)
    visible=mask.bool()
    depth_loss=F.smooth_l1_loss(rendered[visible],depth[visible],beta=.02)
    intersection=(silhouette*mask).sum()
    union=(silhouette+mask-silhouette*mask).sum()
    c={
        'vertices':F.smooth_l1_loss(vertices,truth['pred_vertices'],beta=.02),
        'joints':F.smooth_l1_loss(output['pred_joint_coords'],truth['pred_joint_coords'],beta=.02),
        'camera':F.smooth_l1_loss(output['pred_cam_t'],truth['pred_cam_t'],beta=.05),
        'body_pose':(1-torch.cos(output['body_pose']-truth['body_pose'])).mean(),
        'global_rotation':F.mse_loss(roma.euler_to_rotmat('ZYX',output['global_rot']),
                                    roma.euler_to_rotmat('ZYX',truth['global_rot'])),
        'shape':F.mse_loss(output['shape'],truth['shape']),
        'scale':F.mse_loss(output['scale'],truth['scale']),
        'hand':F.mse_loss(output['hand'],truth['hand']),
        'rendered_depth':depth_loss,
        'silhouette':1-intersection/union.clamp_min(1),
    }
    return c
