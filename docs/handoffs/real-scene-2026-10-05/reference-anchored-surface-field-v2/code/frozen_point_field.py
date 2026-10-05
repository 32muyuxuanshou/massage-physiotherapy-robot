"""Prototype: observed point geometry + typed references -> surface/anatomy field.

Original PyTorch implementation of local relative-position attention. This is
not a reproduction of the cited authors' CUDA implementations or a new claim
about Point Transformer. CT pretraining does not supply SAM/MHR or RGB features.
"""
import torch
from torch import nn


def gather(points, index):
    batch = torch.arange(points.shape[0], device=points.device)
    return points[batch[:, None, None], index]


class LocalPointAttention(nn.Module):
    def __init__(self, channels, neighbors=16):
        super().__init__()
        self.neighbors = neighbors
        self.q = nn.Linear(channels, channels)
        self.k = nn.Linear(channels, channels)
        self.v = nn.Linear(channels, channels)
        self.position = nn.Sequential(nn.Linear(3, channels), nn.GELU(), nn.Linear(channels, channels))
        self.weight = nn.Sequential(nn.Linear(channels, channels), nn.GELU(), nn.Linear(channels, channels))
        self.out = nn.Sequential(nn.LayerNorm(channels), nn.Linear(channels, channels), nn.GELU())

    def forward(self, xyz, feature):
        index = torch.cdist(xyz, xyz).topk(self.neighbors, largest=False).indices
        relative = xyz[:, :, None] - gather(xyz, index)
        positional = self.position(relative)
        weight = self.weight(self.q(feature)[:, :, None] - gather(self.k(feature), index) + positional)
        attention = weight.softmax(dim=2)
        update = (attention * (gather(self.v(feature), index) + positional)).sum(dim=2)
        return feature + self.out(update)


class JointSurfaceField(nn.Module):
    def __init__(self, channels=64, neighbors=16):
        super().__init__()
        self.neighbors = neighbors
        self.stem = nn.Sequential(nn.Linear(3, channels), nn.GELU(), nn.Linear(channels, channels))
        self.encoder = nn.ModuleList([LocalPointAttention(channels, neighbors) for _ in range(2)])
        self.query_position = nn.Sequential(nn.Linear(3, channels), nn.GELU(), nn.Linear(channels, channels))
        self.query_weight = nn.Sequential(nn.Linear(channels, channels), nn.GELU(), nn.Linear(channels, channels))
        self.reference_type = nn.Embedding(2, channels)
        self.reference_xyz = nn.Linear(3, channels)
        self.reference_null = nn.Parameter(torch.zeros(channels))
        self.reference_attn = nn.MultiheadAttention(channels, 4, batch_first=True)
        self.fusion = nn.Sequential(nn.Linear(3 * channels + 3, 128), nn.GELU(), nn.Linear(128, channels), nn.GELU())
        self.surface_head = nn.Linear(channels, 3)
        self.coordinate_head = nn.Linear(channels, 2)

    def forward(self, observed, query, references, reference_present):
        feature = self.stem(observed)
        for block in self.encoder:
            feature = block(observed, feature)
        index = torch.cdist(query, observed).topk(self.neighbors, largest=False).indices
        relative = query[:, :, None] - gather(observed, index)
        positional = self.query_position(relative)
        neighbor = gather(feature, index)
        weights = self.query_weight(self.stem(query)[:, :, None] - neighbor + positional).softmax(dim=2)
        local = ((neighbor + positional) * weights).sum(dim=2)
        global_code = feature.max(dim=1).values[:, None].expand(-1, query.shape[1], -1)
        types = torch.arange(2, device=query.device)
        reference_tokens = self.reference_xyz(references) + self.reference_type(types)[None]
        null = self.reference_null[None, None].expand(query.shape[0], 1, -1)
        reference_tokens = torch.cat([reference_tokens, null], dim=1)
        # The always-available null token represents the explicitly unprompted mode.
        padding = torch.cat([~reference_present, torch.zeros(query.shape[0], 1, dtype=torch.bool, device=query.device)], dim=1)
        reference_code = self.reference_attn(local, reference_tokens, reference_tokens, key_padding_mask=padding)[0]
        fused = self.fusion(torch.cat([local, global_code, reference_code, query], dim=-1))
        return dict(surface_delta=self.surface_head(fused), anatomical_coordinates=self.coordinate_head(fused))
