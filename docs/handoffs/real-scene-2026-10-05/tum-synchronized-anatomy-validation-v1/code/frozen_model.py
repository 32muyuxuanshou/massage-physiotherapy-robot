"""Surface encoder controls and an explicitly ordered anatomical query decoder."""
import torch
from torch import nn


class AnatomicalQuery(nn.Module):
    def __init__(self, method):
        super().__init__()
        self.method = method
        channels = [4, 16, 32, 64, 96]
        self.encoder = nn.Sequential(*[nn.Sequential(nn.Conv2d(channels[i], channels[i+1], 3, stride=2, padding=1),
                                                       nn.GroupNorm(4, channels[i+1]), nn.GELU()) for i in range(4)])
        if method == 'GLOBAL_REGRESSION':
            self.head = nn.Linear(96, 10)
        elif method == 'INDEPENDENT_HEATMAP':
            self.head = nn.Conv2d(96, 5, 1)
        elif method == 'ORDERED_QUERY':
            self.query = nn.Parameter(torch.randn(5, 96) * .02)
            self.decoder = nn.TransformerDecoder(nn.TransformerDecoderLayer(96, 4, 192, dropout=0, batch_first=True), 2)
            self.x_head = nn.Linear(96, 1)
            self.gap_head = nn.Linear(96, 1)
            self.bottom_gap = nn.Linear(96, 1)
        else:
            raise ValueError(method)

    def forward(self, image):
        feature = self.encoder(image)
        if self.method == 'GLOBAL_REGRESSION':
            return self.head(feature.mean((2, 3))).sigmoid().reshape(-1, 5, 2)
        if self.method == 'INDEPENDENT_HEATMAP':
            logits = self.head(feature).flatten(2)
            p = logits.softmax(-1)
            h, w = feature.shape[2:]
            yy, xx = torch.meshgrid(torch.linspace(0, 1, h, device=image.device), torch.linspace(0, 1, w, device=image.device), indexing='ij')
            grid = torch.stack([xx.flatten(), yy.flatten()], dim=-1)
            return p @ grid
        query = self.query[None].expand(len(image), -1, -1)
        decoded = self.decoder(query, feature.flatten(2).transpose(1, 2))
        x = self.x_head(decoded).sigmoid().squeeze(-1)
        gaps = torch.nn.functional.softplus(torch.cat([self.gap_head(decoded).squeeze(-1), self.bottom_gap(decoded.mean(1))], dim=1)) + 1e-6
        y = gaps[:, :5].cumsum(1) / gaps.sum(1, keepdim=True)
        return torch.stack([x, y], dim=-1)
