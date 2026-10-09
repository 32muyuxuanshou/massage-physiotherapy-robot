"""Use the official RGB crop affine for registered metric Depth and rays."""
import torch
from torch.nn import functional as F


def crop_registered_depth(depth_rgb_z_m, batch, trim_sides=64):
    """depth_rgb_z_m: [B,1,H_rgb,W_rgb], already in RGB camera coordinates.

    HuMMan raw depth is NOT RGB-registered; first use the historical calibrated
    depth->RGB transform and front-surface z-buffer. Keep registration holes zero.
    The actual RGB crop affine is reused, not inferred from bbox a second time.
    """
    B, N, _, H, W = batch['img'].shape
    affine = batch['affine_trans'].reshape(B*N, 2, 3).to(depth_rgb_z_m)
    row = affine.new_tensor([0,0,1]).view(1,1,3).expand(B*N,-1,-1)
    inv = torch.linalg.inv(torch.cat((affine,row),1))
    v,u = torch.meshgrid(torch.arange(H,device=depth_rgb_z_m.device),
                         torch.arange(W,device=depth_rgb_z_m.device),indexing='ij')
    pixels = torch.stack((u,v,torch.ones_like(u)),-1).to(depth_rgb_z_m)
    source = torch.einsum('bij,hwj->bhwi',inv,pixels)[...,:2]
    h0,w0 = depth_rgb_z_m.shape[-2:]
    grid = source.clone()
    grid[...,0] = grid[...,0]*2/(w0-1)-1
    grid[...,1] = grid[...,1]*2/(h0-1)-1
    depth = F.grid_sample(depth_rgb_z_m.repeat_interleave(N,0),grid,mode='nearest',
                          padding_mode='zeros',align_corners=True)
    K = batch['cam_int'].repeat_interleave(N,0).to(source)
    rays = (source-K[:,None,None,:2,2])/torch.stack((K[:,0,0],K[:,1,1]),-1)[:,None,None,:]
    rays = rays.permute(0,3,1,2)
    if trim_sides:
        depth,rays = depth[:,:,:,trim_sides:-trim_sides],rays[:,:,:,trim_sides:-trim_sides]
    return depth,torch.isfinite(depth)&(depth>0),rays
