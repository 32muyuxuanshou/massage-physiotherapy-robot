"""R4: raw Camera Head conditioning and finite-neighbour XYZ attention.

Official heads/decoder/MHR stay frozen. The camera hook modifies (s,tx,ty)
BEFORE official camera_project, including intermediate decoder predictions.
"""
import math
import torch
from torch import nn
from torch.nn import functional as F
from fusion import RGBDBodyAdapter, SpatialDepthFusion, metric_features


def geometry_grid(depth, valid, rays):
    # Camera XYZ is FP32 even when RGB backbone features are BF16.
    depth, rays = depth.float(), rays.float()
    valid = valid.bool() & torch.isfinite(depth) & (depth > 0)
    depth = torch.where(valid, depth, 0)
    weight = F.avg_pool2d(valid.float(), 16, 16)
    xyz = torch.cat((rays * depth, depth), 1) * valid
    xyz = F.avg_pool2d(xyz, 16, 16) / weight.clamp_min(1e-6)
    return xyz, weight > 0


class LocalGeometryFusion(SpatialDepthFusion):
    def __init__(self, channels, hidden=256, heads=8):
        super().__init__(channels, hidden, heads, 'cross_attention')
        self.relative_bias = nn.Sequential(nn.Linear(3, 64), nn.GELU(), nn.Linear(64, heads))
        self.log_sigma = nn.Parameter(torch.tensor(math.log(.15)))
        self.heads = heads
        self.disable_geometry = False

    @staticmethod
    def neighbours(x):
        b, c, h, w = x.shape
        return F.unfold(x, 5, padding=2).reshape(b, c, 25, h*w).permute(0, 3, 2, 1)

    def forward(self, rgb, depth, valid, rays):
        features, valid = metric_features(depth.float(), valid, rays.float())
        d = self.depth_encoder(features)
        xyz, coverage = geometry_grid(depth, valid, rays)
        b, c, h, w = d.shape
        q = self.rgb_projection(rgb).flatten(2).transpose(1, 2)
        kv = self.neighbours(d)
        # Reuse the same MHA projections/heads as G0; neighbourhood has 25 keys.
        weight, bias = self.attention.in_proj_weight, self.attention.in_proj_bias
        q = F.linear(q, weight[:c], bias[:c]).reshape(b, h*w, self.heads, c//self.heads)
        k = F.linear(kv, weight[c:2*c], bias[c:2*c]).reshape(b, h*w, 25, self.heads, c//self.heads)
        v = F.linear(kv, weight[2*c:], bias[2*c:]).reshape_as(k)
        scores = (q[:, :, None] * k).sum(-1) / math.sqrt(c//self.heads)
        relative = self.neighbours(xyz) - xyz.flatten(2).transpose(1, 2)[:, :, None]
        if not self.disable_geometry:
            sigma = self.log_sigma.exp().clamp(.03, .5)
            scores = scores + self.relative_bias(relative) - relative.square().sum(-1, keepdim=True)/(2*sigma.square())
        key_valid = self.neighbours(coverage.float())[..., 0] > 0
        scores = scores.masked_fill(~key_valid[..., None], -1e4)
        attention = scores.softmax(2) * key_valid[..., None]
        attention = attention / attention.sum(2, keepdim=True).clamp_min(1e-6)
        fused = (attention[..., None] * v).sum(2).reshape(b, h*w, c)
        fused = self.attention.out_proj(fused).transpose(1, 2).reshape(b, c, h, w)
        # Missing measured geometry at a query preserves its exact RGB feature.
        delta = self.output_projection(fused) * coverage
        return rgb + self.gate * delta


def metric_statistics(depth, valid, rays, batch):
    """Measured surface summaries, not root/camera ground truth."""
    depth, rays = depth.float(), rays.float()
    valid = valid.bool() & torch.isfinite(depth) & (depth > 0)
    stats = []
    for z, mask, ray in zip(depth[:, 0], valid[:, 0], rays):
        values = z[mask]
        if len(values):
            quantiles = torch.quantile(values, values.new_tensor([.1, .25, .5, .75, .9]))
            xyz = torch.cat((ray[:, mask].T * values[:, None], values[:, None]), 1)
            mean, std = xyz.mean(0), xyz.std(0, unbiased=False)
            s = torch.cat((quantiles, mean, std, (quantiles[-1]-quantiles[0])[None], mask.float().mean()[None]))
        else:
            s = depth.new_zeros(13)
        stats.append(s)
    K = batch['cam_int'].float()
    size = batch['ori_img_size'].reshape(-1, 2).float()
    bbox = batch['bbox_scale'].reshape(-1, 2)[:, :1].float()
    intrinsics = torch.stack((K[:, 0, 0]/size[:, 0], K[:, 1, 1]/size[:, 1],
                             K[:, 0, 2]/size[:, 0], K[:, 1, 2]/size[:, 1]), 1)
    return torch.cat((torch.stack(stats), intrinsics, bbox/size[:, :1]), 1), valid.flatten(1).any(1)


class MetricCamera(nn.Module):
    def __init__(self, token_dim=1024):
        super().__init__()
        self.token = nn.Sequential(nn.LayerNorm(token_dim), nn.Linear(token_dim, 128), nn.GELU())
        self.metric = nn.Sequential(nn.Linear(22, 128), nn.GELU(), nn.Linear(128, 128), nn.GELU())
        self.output = nn.Sequential(nn.Linear(256, 128), nn.GELU(), nn.Linear(128, 3))
        nn.init.zeros_(self.output[-1].weight)
        nn.init.zeros_(self.output[-1].bias)
        self.disabled = False

    def forward(self, token, raw_cam, stats, available, batch, default_scale_factor):
        if self.disabled:
            return raw_cam
        K = batch['cam_int'].float()
        box = batch['bbox_scale'].reshape(-1, 2)[:, 0].float()
        # The official raw scale is negative; sign conversion is performed later.
        tz = 2*K[:, 0, 0]/(-raw_cam[:, 0]*box*default_scale_factor+1e-8)
        metric = torch.cat((stats, raw_cam.float(), (stats[:, 2]-tz)[:, None]), 1)
        change = self.output(torch.cat((self.token(token.float()), self.metric(metric)), 1)).tanh()
        change = change * available[:, None]
        # Bounded raw-parameter residual; never directly override pred_cam_t.
        return torch.stack((raw_cam[:, 0]*torch.exp(.5*change[:, 0]),
                            raw_cam[:, 1]+.15*change[:, 1], raw_cam[:, 2]+.15*change[:, 2]), 1)


class R4Fusion(nn.Module):
    def __init__(self, channels, mode):
        super().__init__()
        self.spatial = (LocalGeometryFusion(channels) if mode in ['g2', 'g3'] else
                        SpatialDepthFusion(channels, mode='cross_attention'))
        self.camera = MetricCamera() if mode in ['g1', 'g3'] else None

    def forward(self, *args):
        return self.spatial(*args)


class R4Adapter(RGBDBodyAdapter):
    def __init__(self, official, mode='g1'):
        super().__init__(official, mode='cross_attention')
        assert mode in ['g0', 'g1', 'g2', 'g3']
        self.mode = mode
        self.fusion = R4Fusion(official.backbone.embed_dims, mode)
        self._metric_context = None
        self._camera_hook = official.head_camera.register_forward_hook(self._condition_camera)

    def _condition_camera(self, module, args, output):
        if self.fusion.camera is None or self._metric_context is None:
            return output
        stats, available, batch = self._metric_context
        return self.fusion.camera(args[0], output, stats, available, batch, module.default_scale_factor)

    def forward(self, batch, depth, valid, rays):
        stats, available = metric_statistics(depth, valid, rays, batch)
        self._metric_context = (stats, available, batch)
        try:
            return super().forward(batch, depth, valid, rays)
        finally:
            self._metric_context = None

    def remove_hooks(self):
        self._hook.remove()
        self._camera_hook.remove()
