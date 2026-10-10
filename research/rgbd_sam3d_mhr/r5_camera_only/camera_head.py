"""Post-decode Camera-only pilot; no Body parameters or decoder are trainable.

Pooled RGB backbone is a documented pilot variant, not the old final pose token.
Both output parameterizations use identical data, supervision, and tiny encoders.
"""
import torch
from torch import nn


class CameraHead(nn.Module):
    def __init__(self, metric_mean, metric_std, mode):
        super().__init__()
        self.mode = mode
        self.register_buffer('metric_mean', torch.as_tensor(metric_mean).float())
        self.register_buffer('metric_std', torch.as_tensor(metric_std).float().clamp_min(1e-4))
        # TRAIN-constant channels have no learned effect; never amplify unseen
        # principal-point changes through the arbitrary standard-deviation floor.
        self.register_buffer('metric_active', torch.as_tensor(metric_std)>0)
        self.rgb = nn.Sequential(nn.LayerNorm(1280), nn.Linear(1280, 128), nn.GELU())
        self.metric = nn.Sequential(nn.Linear(len(metric_mean), 128), nn.GELU(), nn.Linear(128, 128), nn.GELU())
        self.output = nn.Sequential(nn.Linear(256, 128), nn.GELU(), nn.Linear(128, 3))
        nn.init.zeros_(self.output[-1].weight)
        nn.init.zeros_(self.output[-1].bias)

    def forward(self, rgb, metric, original_camera, K, center, box, available):
        g = (metric-self.metric_mean)/self.metric_std
        g = torch.where(self.metric_active, g, torch.zeros_like(g))
        if self.mode == 'rgb_only_xyz':
            g = g*0  # actual absence of measured-Depth features, not a renamed RGB-D model
        change = self.output(torch.cat((self.rgb(rgb), self.metric(g)), -1))
        if self.mode == 'raw_bounded':
            change = change.tanh()
            original_z = original_camera[:, 2]
            offset = (center-K[:, :2, 2])*original_z[:, None]/K[:, 0, 0, None]
            # The default scale factor cancels in z' = z * exp(-delta_scale).
            raw_xy = torch.stack((original_camera[:, 0]-offset[:, 0],
                                  -original_camera[:, 1]+offset[:, 1]), -1)
            z = original_z*torch.exp(-.5*change[:, 0])
            final_offset = (center-K[:, :2, 2])*z[:, None]/K[:, 0, 0, None]
            moved = raw_xy+.15*change[:, 1:]
            final = torch.stack((moved[:, 0]+final_offset[:, 0],
                                 -moved[:, 1]+final_offset[:, 1], z), -1)
        else:
            final = original_camera+change  # learned metre-valued final XYZ residual
        # Missing Depth must preserve Official, including in held-out diagnostics.
        return torch.where(available[:, None], final, original_camera)


def apply_camera(official, camera):
    """Full native Body stays identical. 2D projection is regenerated downstream."""
    return dict(official, pred_cam_t=camera,
                vertices_camera_A=official['pred_vertices']+camera[:, None])
