"""Exact camera-ray evaluation. Geometry is metres, +Z forward, no distortion."""
import numpy as np
from scipy.spatial import cKDTree


def ray_depth_residual(points, vertices, faces, K=None):
    """First positive intersection minus observed Z, at the exact continuous ray.

    K is accepted for compatibility: normalized coordinates cancel the pinhole K.
    This evaluator does not apply lens distortion; camera contract must say so.
    A conservative maximum centroid radius prevents discarding large triangles.
    """
    p = np.asarray(points, float)
    tri = np.asarray(vertices, float)[np.asarray(faces, np.int64)]
    if np.any(tri[:, :, 2] <= 0) or np.any(p[:, 2] <= 0):
        raise ValueError('Positive-Z geometry required for projected triangle evaluation')
    uv = tri[:, :, :2] / tri[:, :, 2, None]
    q = p[:, :2] / p[:, 2, None]
    centroids = uv.mean(1)
    radius = np.linalg.norm(uv-centroids[:, None], axis=2).max(1)
    candidates = cKDTree(centroids).query_ball_point(q, float(radius.max())+1e-12, workers=-1)
    residual = np.full(len(p), np.nan)
    for i, ids in enumerate(candidates):
        ids = np.asarray(ids, np.int64)
        ids = ids[np.linalg.norm(centroids[ids]-q[i], axis=1) <= radius[ids]+1e-12]
        a, b, c = uv[ids, 0], uv[ids, 1], uv[ids, 2]
        e1, e2, v = b-a, c-a, q[i]-a
        den = e1[:, 0]*e2[:, 1]-e1[:, 1]*e2[:, 0]
        nondegenerate = np.abs(den) > 1e-14
        denom = np.where(nondegenerate, den, 1.)
        w1 = (v[:, 0]*e2[:, 1]-e2[:, 0]*v[:, 1])/denom
        w2 = (e1[:, 0]*v[:, 1]-v[:, 0]*e1[:, 1])/denom
        inside = nondegenerate & (w1 >= -1e-9) & (w2 >= -1e-9) & (w1+w2 <= 1+1e-9)
        if inside.any():
            inv_z = ((1-w1-w2)/tri[ids, 0, 2]+w1/tri[ids, 1, 2]+w2/tri[ids, 2, 2])
            residual[i] = (1/inv_z[inside]).min()-p[i, 2]
    return residual, np.isfinite(residual)


def distance_summary(values_m):
    v = np.asarray(values_m, float)
    v = v[np.isfinite(v)]*1000
    return dict(n=len(v), median_mm=float(np.median(v)) if len(v) else None,
                p95_mm=float(np.percentile(v, 95)) if len(v) else None)


def common_hit_mask(hit_masks):
    return np.logical_and.reduce(hit_masks)
