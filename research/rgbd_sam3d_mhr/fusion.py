"""Metric Depth encoders and residual spatial RGB-D fusion.

Geometry is metres and aligned to the SAME 512x384 RGB crop. No MHR heads or
free vertex offsets are introduced here. Zero residual gate preserves Official
features initially; depth gradients begin after the gate's first optimizer step.
"""
import torch
from torch import nn
from torch.nn import functional as F


def metric_features(depth_m, valid, rays_xy):
    valid = valid.bool() & torch.isfinite(depth_m) & (depth_m > 0)
    z = torch.where(valid, depth_m, 0)
    center = []
    for zi, vi in zip(z, valid):
        center.append(zi[vi].median() if vi.any() else zi.new_zeros(()))
    center = torch.stack(center)[:, None, None, None]
    relative = torch.where(valid, z-center, 0)
    return torch.cat((z, relative, valid.to(z), rays_xy.to(z)), 1), valid


class SpatialDepthFusion(nn.Module):
    def __init__(self, rgb_channels=1280, hidden=256, heads=8, mode='cross_attention'):
        super().__init__()
        self.mode = mode
        self.depth_encoder = nn.Sequential(nn.Conv2d(5, hidden//2, 4, stride=4), nn.GELU(),
            nn.Conv2d(hidden//2, hidden, 4, stride=4), nn.GELU())
        self.rgb_projection = nn.Conv2d(rgb_channels, hidden, 1)
        self.attention = nn.MultiheadAttention(hidden, heads, batch_first=True, dropout=0)
        self.output_projection = nn.Conv2d(hidden, rgb_channels, 1)
        self.gate = nn.Parameter(torch.zeros(()))

    def forward(self, rgb, depth_m, valid, rays_xy):
        features, valid = metric_features(depth_m, valid, rays_xy)
        depth = self.depth_encoder(features)
        assert depth.shape[-2:] == rgb.shape[-2:], 'RGB_DEPTH_CROP_GRID_MISMATCH'
        coverage = F.avg_pool2d(valid.float(), 16, 16).flatten(1) > 0
        available = coverage.any(1)
        delta = torch.zeros_like(rgb)
        # Missing Depth must preserve RGB behavior and must not create all-masked
        # softmax NaNs. Only the actual available rows enter spatial attention.
        if available.any():
            selected = available.nonzero().flatten()
            d = depth[selected]
            if self.mode == 'cross_attention':
                q = self.rgb_projection(rgb[selected]).flatten(2).transpose(1, 2)
                kv = d.flatten(2).transpose(1, 2)
                fused, _ = self.attention(q, kv, kv, key_padding_mask=~coverage[selected], need_weights=False)
                d = fused.transpose(1, 2).reshape_as(d)
            elif self.mode == 'residual':
                d = d * coverage[selected].view(len(selected), 1, *d.shape[-2:])
            else:
                raise ValueError(self.mode)
            delta = delta.index_copy(0, selected, self.output_projection(d))
        return rgb + self.gate * delta


class RGBDBodyAdapter(nn.Module):
    """Controlled forward hook after the official RGB backbone, before decoder.

    Call with the official prepared batch and already registered/cropped Depth.
    Official source files and MHR representation are not modified.
    """
    def __init__(self, official, mode='cross_attention'):
        super().__init__()
        self.official = official
        self.official.requires_grad_(False)
        self.fusion = SpatialDepthFusion(official.backbone.embed_dims, mode=mode)
        self._depth_inputs = None
        self._hook = official.backbone.register_forward_hook(self._fuse)

    def _fuse(self, module, args, output):
        if self._depth_inputs is None:
            return output
        if isinstance(output, tuple):
            last = output[-1]
            fused = self.fusion(last.float(), *self._depth_inputs).to(last.dtype)
            return (*output[:-1], fused)
        return self.fusion(output.float(), *self._depth_inputs).to(output.dtype)

    def forward(self, batch, depth_m, valid, rays_xy):
        self.official.eval()  # Frozen RGB dropout/statistics remain deterministic.
        self.official._initialize_batch(batch)
        self._depth_inputs = (depth_m, valid, rays_xy)
        try:
            return self.official.forward_step(batch, decoder_type='body')['mhr']
        finally:
            self._depth_inputs = None
