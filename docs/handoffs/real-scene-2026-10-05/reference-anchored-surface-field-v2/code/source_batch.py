"""Paired CT source, synthetic perspective depth observation, explicit references.

Uses existing frozen 18-level packs. Query and teacher remain on one perspective
ray; this removes unobservable tangential perturbation. Source points are not
first-hit visibility certified. This is radial point-cloud pretraining, not a
fully rendered RGB-D observation or measured sensor depth.
"""
import numpy as np
import torch
from reference_frame import make_frame, to_local, direction_to_local


def sample_pack(path, seed, observed_count=512, query_count=256,
                reference_noise_mm=0.):
    rng = np.random.default_rng(seed)
    with np.load(path) as pack:
        points = pack['points_ras_mm'].copy()
        references = pack['references_ras_mm'].copy()
        assert pack['reference_present'].all(), 'PAIR_NOT_AVAILABLE'
        coordinate = pack['anatomical_coordinates'].copy()
        valid = pack['anatomy_valid'].copy()
    # Depth camera is outside the posterior source skin, looking toward it.
    camera = np.median(points, axis=0) + np.array([0., -1200., 0.])
    rays = points-camera
    rays /= np.linalg.norm(rays, axis=1, keepdims=True)
    observed_index = rng.choice(len(points), observed_count, replace=False)
    remaining = np.setdiff1d(np.arange(len(points)), observed_index)
    query_index = rng.choice(remaining[valid[remaining]], query_count, replace=False)
    references += rng.normal(0., reference_noise_mm, references.shape)
    frame = make_frame(references, [0., -1., 0.], 1.)
    observed_noise = rng.normal(0., 2., (observed_count, 1))
    query_noise = rng.normal(0., 10., (query_count, 1))
    observed = points[observed_index] + observed_noise*rays[observed_index]
    query = points[query_index] + query_noise*rays[query_index]
    # B-cun grade interpolation is unchanged. CT RAS lateral is converted to the
    # physical local lateral using the original grade-conditioned midline point.
    targets = coordinate[query_index].copy()
    clean = to_local(points[query_index], frame)
    midline = points[query_index].copy()
    midline[:, 0] -= coordinate[query_index, 1]*500.
    targets[:, 1] = clean[:, 0]-to_local(midline, frame)[:, 0]
    batch = dict(observed=to_local(observed, frame).astype(np.float32),
                 query=to_local(query, frame).astype(np.float32),
                 references=to_local(references, frame).astype(np.float32),
                 reference_present=np.ones(2, bool),
                 query_rays=direction_to_local(rays[query_index], frame).astype(np.float32),
                 ray_target=(-query_noise[:, 0]/500.).astype(np.float32),
                 anatomical_coordinates=targets.astype(np.float32))
    identity = dict(observed_indices=observed_index, query_indices=query_index,
                    camera_ras_mm=camera, reference_noise_mm=reference_noise_mm,
                    frame=frame, clean_query_local=clean)
    return batch, identity


def stack(items):
    return {k:torch.from_numpy(np.stack([item[k] for item in items])) for k in items[0]}
