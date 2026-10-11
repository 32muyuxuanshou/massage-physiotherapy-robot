"""Hard RGB Body isolation; learned coarse and one-pass visible-geometry Camera.

No MHR parameter head, free vertex displacement or iterative Txyz is trained.
"""
import torch
from torch import nn
from torch.nn import functional as F


def sampled_geometry(depth, valid, rays, count=2048):
    """Deterministic fixed-budget valid-point sample; masks exclude padding."""
    xyz = torch.cat((rays.float()*depth.float(), depth.float()), 1)
    result, masks = [], []
    for p, ray, v in zip(xyz, rays, valid[:, 0]):
        index = v.flatten().nonzero().flatten()
        used = min(count, len(index))
        selected = index[torch.linspace(0, max(len(index)-1, 0), used, device=p.device).long()]
        q = p.flatten(1)[:, selected].T
        r = ray.flatten(1)[:, selected].T.float()
        center = q.mean(0) if used else q.new_zeros(3)
        features = torch.cat((q, q-center, r), 1)
        result.append(F.pad(features, (0, 0, 0, count-used)))
        masks.append(torch.arange(count, device=p.device) < used)
    return torch.stack(result), torch.stack(masks)


def masked_pool(features, mask):
    mean = (features*mask[..., None]).sum(1)/mask.sum(1).clamp_min(1)[:, None]
    maximum = features.masked_fill(~mask[..., None], -torch.inf).amax(1)
    maximum = torch.where(mask.any(1)[:, None], maximum, torch.zeros_like(maximum))
    return torch.cat((mean, maximum), -1)


def directional_filter(delta, normals, valid, epsilon=.01):
    """Suppress only weakly observed normal directions, not the entire vector."""
    matrix = torch.einsum('bni,bnj,bn->bij', normals, normals, valid.float())
    matrix = matrix/valid.sum(1).clamp_min(1)[:, None, None]
    eigenvalues, axes = torch.linalg.eigh(matrix.detach())
    weights = eigenvalues.clamp_min(0)/(eigenvalues.clamp_min(0)+epsilon)
    return torch.einsum('bij,bj,bkj,bk->bi', axes, weights, axes, delta), eigenvalues


class CoarseCamera(nn.Module):
    def __init__(self, point_count=2048):
        super().__init__()
        self.point_count = point_count
        self.points = nn.Sequential(nn.Linear(8, 64), nn.GELU(), nn.Linear(64, 128), nn.GELU())
        self.rgb = nn.Sequential(nn.LayerNorm(1280), nn.Linear(1280, 128), nn.GELU())
        self.head = nn.Sequential(nn.Linear(256+128+29, 128), nn.GELU(), nn.Linear(128, 3))
        nn.init.zeros_(self.head[-1].weight); nn.init.zeros_(self.head[-1].bias)

    def forward(self, feature, depth, valid, rays, official, batch):
        points, mask = sampled_geometry(depth, valid, rays, self.point_count)
        weight = mask[..., None]
        count = weight.sum(1).clamp_min(1)
        center = (points[..., :3]*weight).sum(1)/count
        std = (((points[..., :3]-center[:, None]).square()*weight).sum(1)/count).sqrt()
        body = official['pred_vertices'].float().detach()
        body_mean, body_std = body.mean(1), body.std(1, unbiased=False)
        quartile = torch.quantile(body, body.new_tensor([.25, .5, .75]), dim=1).permute(1,0,2).flatten(1)
        K = batch['cam_int'].float(); size = batch['ori_img_size'].reshape(-1,2).float()
        intrinsics = torch.stack((K[:,0,0]/size[:,0],K[:,1,1]/size[:,1],
            K[:,0,2]/size[:,0],K[:,1,2]/size[:,1],batch['bbox_scale'].reshape(-1,2)[:,0]/size[:,0]),1)
        t0 = official['pred_cam_t'].float().detach()
        context = torch.cat((center,std,t0,quartile,body_mean,body_std,intrinsics),1)
        value = torch.cat((masked_pool(self.points(points),mask), self.rgb(feature.float().mean((2,3))), context),1)
        delta = self.head(value)
        return torch.where(mask.any(1)[:,None], t0+delta, t0)


class GeometryCamera(nn.Module):
    def __init__(self, faces, anchor_faces, barycentric, renderer, fine=True, gating=True):
        super().__init__()
        self.coarse = CoarseCamera()
        self.fine_enabled = fine
        self.gating = gating
        self.renderer = renderer
        self.register_buffer('faces', faces.long())
        self.register_buffer('anchor_faces', anchor_faces.long())
        self.register_buffer('barycentric', barycentric.float())
        self.rgb_local = nn.Conv2d(1280,64,1)
        self.local = nn.Sequential(nn.Linear(82,128),nn.GELU(),nn.Linear(128,128),nn.GELU())
        self.fine_head = nn.Sequential(nn.Linear(256,128),nn.GELU(),nn.Linear(128,3))
        nn.init.zeros_(self.fine_head[-1].weight); nn.init.zeros_(self.fine_head[-1].bias)
        if not fine:
            self.rgb_local.requires_grad_(False); self.local.requires_grad_(False); self.fine_head.requires_grad_(False)

    def forward(self, feature, depth, valid, rays, official, batch, enable_fine=True):
        coarse = self.coarse(feature,depth,valid,rays,official,batch)
        stats = dict(coarse_camera=coarse, fine_delta=torch.zeros_like(coarse))
        if not self.fine_enabled or not enable_fine:
            return coarse, stats
        body = official['pred_vertices'].float().detach()
        triangles = (body+coarse[:,None])[:,self.faces[self.anchor_faces]]
        query = (triangles*self.barycentric[None,:,:,None]).sum(2)
        normal = F.normalize(torch.cross(triangles[:,:,1]-triangles[:,:,0],
                                        triangles[:,:,2]-triangles[:,:,0],dim=-1),dim=-1)
        K = batch['cam_int'].float(); size=batch['ori_img_size'].reshape(-1,2).float()
        projection = torch.einsum('bij,bnj->bni',K,query)
        uv = projection[...,:2]/query[...,2:].clamp_min(.001)
        affine = batch['affine_trans'].reshape(-1,2,3).float()
        cropped = torch.einsum('bij,bnj->bni',affine,torch.cat((uv,torch.ones_like(uv[...,:1])),2))
        cropped[...,0] -= 64  # actual official 512->384 side trim
        h,w=depth.shape[-2:]
        grid = torch.stack((2*cropped[...,0]/(w-1)-1,2*cropped[...,1]/(h-1)-1),2)
        source_z = F.grid_sample(depth.float(),grid[:,:,None],mode='nearest',align_corners=True)[:,0,:,0]
        source_valid = F.grid_sample(valid.float(),grid[:,:,None],mode='nearest',align_corners=True)[:,0,:,0] > .5
        # Rasterizer uses a fixed physical viewport; scale K from original RGB.
        render_K=K.clone();render_K[:,0,:] *= self.renderer.width/size[:,0,None]
        render_K[:,1,:] *= self.renderer.height/size[:,1,None]
        rendered,_ = self.renderer(body+coarse[:,None],render_K)
        render_grid=torch.stack((2*(uv[...,0]+.5)/size[:,0,None]-1,
                                 2*(uv[...,1]+.5)/size[:,1,None]-1),2)
        surface_z=F.grid_sample(rendered[:,None],render_grid[:,:,None],mode='nearest',align_corners=False)[:,0,:,0]
        inside=(grid.abs()<=1).all(2)&(query[...,2]>.05)
        observed=source_valid&inside&(surface_z>0)&((surface_z-query[...,2]).abs()<.02)
        ray=(uv-K[:,None,:2,2])/torch.stack((K[:,0,0],K[:,1,1]),1)[:,None]
        measured=torch.cat((ray*source_z[...,None],source_z[...,None]),2)
        local_rgb=F.grid_sample(self.rgb_local(feature.float()),grid[:,:,None],align_corners=True)[:,:,:,0].transpose(1,2)
        geo=torch.cat((query,measured,measured-query,normal,ray,
                       (source_z-query[...,2])[...,None],grid,observed[...,None].float()),2)
        token=self.local(torch.cat((local_rgb,geo),2))
        raw_delta=self.fine_head(masked_pool(token,observed))
        if self.gating:
            delta,eigen=directional_filter(raw_delta,normal,observed)
        else:
            delta=raw_delta; eigen=raw_delta.new_zeros((len(raw_delta),3))
        delta=torch.where(observed.any(1)[:,None],delta,torch.zeros_like(delta))
        stats.update(fine_delta=delta, fine_raw_delta=raw_delta, eigenvalues=eigen,
                     visible_queries=observed.sum(1), query_count=observed.shape[1])
        return coarse+delta,stats


def replace_camera(official,camera):
    # Caller regenerates projections from original K. Body tensor identity persists.
    return dict(official,pred_cam_t=camera)
