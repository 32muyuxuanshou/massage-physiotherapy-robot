"""Reference-lifted coordinate field and ray-only surface displacement.

Exact lifting is an established hard-constraint construction, not a novelty claim.
Network backbone is byte-frozen from V1. Both anatomical outputs are defined in
the supplied rigid body frame; inference requires two references in this V2.
"""
import torch
from frozen_point_field import JointSurfaceField


class AnchoredField(JointSurfaceField):
    def forward(self, observed, query, references, reference_present, query_rays,
                hard=True):
        assert reference_present.all(), 'V2_REQUIRES_TWO_SUPPLIED_REFERENCES'
        combined = torch.cat([query, references], dim=1)
        raw = super().forward(observed, combined, references, reference_present)
        residual = raw['anatomical_coordinates'][:, :-2]
        endpoint = raw['anatomical_coordinates'][:, -2:]
        vector = references[:, 1]-references[:, 0]
        along = ((query-references[:, 0, None])*vector[:, None]).sum(-1)/vector.square().sum(-1)[:, None]
        # In the rigid local frame lateral is physical right divided by 500 mm.
        base = torch.stack([along, query[..., 0]-references[:, 0, None, 0]], dim=-1)
        if hard:
            residual = residual-(1-along[..., None])*endpoint[:, 0, None]-along[..., None]*endpoint[:, 1, None]
        coordinate = base+residual
        # Query moves only along a known camera ray. Tangential correspondence is
        # deliberately absent from the geometry objective.
        ray_delta = (raw['surface_delta'][:, :-2]*query_rays).sum(-1)
        return dict(anatomical_coordinates=coordinate, ray_delta=ray_delta,
                    surface_delta=ray_delta[..., None]*query_rays,
                    raw_endpoint_residual=endpoint)
