"""Historical Rigid/D algorithms, unchanged. D is a 3D vector displacement
with soft tangential penalty and graph-Laplacian regularization; not strict normal-only.
Ray evaluation is replaced by the independently tested metrics_v2 implementation.
"""
from __future__ import annotations
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

from bed_io import height_above_bed, to_world


# ----------------------------------------------------------------------------- geometry
def vertex_normals(V, F):
    tri = V[F]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])       # area weighted
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    return vn


def edges(F):
    e = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e = np.sort(e, 1)
    return np.unique(e, axis=0)


def graph_laplacian(n, E):
    i, j = E[:, 0], E[:, 1]
    A = sp.coo_matrix((np.ones(len(E)), (i, j)), shape=(n, n))
    A = (A + A.T).tocsr()
    D = sp.diags(np.asarray(A.sum(1)).ravel())
    return (D - A).tocsr()


def project_px(P, K):
    return np.c_[K[0, 0] * P[:, 0] / P[:, 2] + K[0, 2], K[1, 1] * P[:, 1] / P[:, 2] + K[1, 2]]


def visible_mask(V, vn, K, cell_px=3.0, slack=0.015):
    """Z-buffer visibility on a pixel grid + camera-facing normals."""
    uv = project_px(V, K)
    ray = V / np.linalg.norm(V, axis=1, keepdims=True)
    facing = (vn * ray).sum(1) < -0.15                  # normal points back toward camera
    g = np.floor(uv / cell_px).astype(np.int64)
    key = g[:, 0] * 100003 + g[:, 1]
    order = np.argsort(key)
    k_sorted = key[order]
    zmin = np.empty(len(V))
    starts = np.r_[0, np.nonzero(np.diff(k_sorted))[0] + 1]
    ends = np.r_[starts[1:], len(V)]
    for s, e in zip(starts, ends):
        zmin[order[s:e]] = V[order[s:e], 2].min()
    return facing & (V[:, 2] <= zmin + slack)


# ----------------------------------------------------------------------------- rigid
def fit_rigid(V, F, cloud, K, iters=30, trim=0.2):
    """Trimmed point-to-plane ICP, 6-DoF, visible vertices only, no step/total bound."""
    R = np.eye(3); t = np.zeros(3)
    tree_c = cKDTree(cloud)
    for it in range(iters):
        W = V @ R.T + t
        vn = vertex_normals(W, F)
        vis = visible_mask(W, vn, K)
        src, nrm = W[vis], vn[vis]
        # init far away: first iterations use point-to-point on cloud->src
        tree_s = cKDTree(src)
        dist, j = tree_s.query(cloud, workers=-1)
        keep = dist <= np.quantile(dist, 1 - trim)
        p, q, n = cloud[keep], src[j[keep]], nrm[j[keep]]
        if it < 4:                                      # coarse: translation only
            dt = np.median(p - q, axis=0)
            t = t + dt
            continue
        r = ((p - q) * n).sum(1)
        A = np.c_[np.cross(q, n), n]                    # [omega, dt]
        x, *_ = np.linalg.lstsq(A, r, rcond=None)
        w = x[:3]
        th = np.linalg.norm(w)
        if th > 1e-12:
            k = w / th
            Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
            dR = np.eye(3) + np.sin(th) * Kx + (1 - np.cos(th)) * Kx @ Kx
        else:
            dR = np.eye(3)
        R = dR @ R; t = dR @ t + x[3:]
        if np.linalg.norm(x[3:]) < 1e-5 and th < 1e-5:
            break
    return R, t


# ----------------------------------------------------------------------------- data term
def ray_targets(W, vn, vis, cloud, K, rho_px=2.5, min_n=3, max_abs=0.10):
    """Point-to-plane distance s_i along the vertex normal to the cloud on the vertex's ray."""
    uv_c = project_px(cloud, K)
    tree = cKDTree(uv_c)
    idx = np.nonzero(vis)[0]
    nb = tree.query_ball_point(project_px(W[idx], K), rho_px, workers=-1)
    s = np.zeros(len(W)); cnt = np.zeros(len(W))
    for a, ix in zip(idx, nb):
        if len(ix) < min_n:
            continue
        p = cloud[ix]
        # nearest layer along the ray (dorsal surface), robust
        zc = np.percentile(p[:, 2], 25)
        p = p[np.abs(p[:, 2] - zc) < 0.02]
        if len(p) < min_n:
            continue
        sv = ((p - W[a]) * vn[a]).sum(1)
        v = float(np.median(sv))
        if abs(v) > max_abs:
            continue
        s[a] = v; cnt[a] = len(p)
    return s, cnt


def fit_displacement(V, F, cloud, K, *, lam=2.0, mu=1e-4, tau=0.05, n0=6.0, irls=4,
                     sigma=0.012, use_conf=True, use_robust=True, bed=None, max_sink=None,
                     w_bed=5.0):
    """Smooth vector displacement field delta (n,3), metres.

    data   : w_i (n_i . delta_i - s_i)^2      point-to-plane along the vertex normal
    smooth : lam * sum_xyz delta^T L delta     membrane prior -> no folding, fills gaps
    slide  : tau * |(I - n n^T) delta_i|^2     discourages tangential sliding (index drift)
    ridge  : mu * |delta_i|^2
    bed    : w_bed (b . delta_i - g_i)^2 on vertices sunk deeper than max_sink into the
             mattress (b = bed normal toward camera, camera frame)
    """
    n = len(V)
    E = edges(F); L = graph_laplacian(n, E)
    vn = vertex_normals(V, F)
    vis = visible_mask(V, vn, K)
    ray = V / np.linalg.norm(V, axis=1, keepdims=True)
    agree = np.clip(-(vn * ray).sum(1), 0, 1)
    delta = np.zeros((n, 3))
    I3 = np.eye(3)
    Lbig = sp.kron(L, sp.eye(3)).tocsr()               # interleaved xyz ordering
    info = {}
    if bed is not None:
        Rw, Cw, pl = bed
        nb_w = np.array([pl[0], pl[1], -1.0]); nb_w /= np.linalg.norm(nb_w)   # toward camera (-z world)
        b = Rw @ nb_w                                       # camera frame
    for it in range(irls):
        W = V + delta
        s_inc, cnt = ray_targets(W, vn, vis, cloud, K)
        has = cnt > 0
        tgt = (delta * vn).sum(1) + s_inc
        w = (cnt / (cnt + n0)) * agree ** 2 if use_conf else has.astype(float)
        if use_robust and it > 0:
            w = w * (sigma ** 2 / (sigma ** 2 + s_inc ** 2)) ** 2
        w = np.where(has, w, 0.0)
        # per-vertex 3x3 blocks
        nnT = vn[:, :, None] * vn[:, None, :]
        Bk = w[:, None, None] * nnT + tau * (I3[None] - nnT) + mu * I3[None]
        rk = (w * tgt)[:, None] * vn
        if bed is not None and max_sink is not None:
            h = height_above_bed(to_world(W, Rw, Cw), pl)
            viol = h < -max_sink
            g = (delta @ b) + (-max_sink - h)            # required displacement along b
            bbT = np.outer(b, b)
            Bk = Bk + np.where(viol, w_bed, 0.0)[:, None, None] * bbT[None]
            rk = rk + (np.where(viol, w_bed * g, 0.0))[:, None] * b[None]
            info[f"bed_violators_it{it}"] = int(viol.sum())
        rows = np.repeat(np.arange(n) * 3, 9) + np.tile(np.repeat(np.arange(3), 3), n)
        cols = np.repeat(np.arange(n) * 3, 9) + np.tile(np.tile(np.arange(3), 3), n)
        Bd = sp.csr_matrix((Bk.reshape(-1), (rows, cols)), shape=(3 * n, 3 * n))
        A = (Bd + lam * Lbig).tocsc()
        delta = spsolve(A, rk.reshape(-1)).reshape(n, 3)
        info[f"n_data_it{it}"] = int(has.sum())
    d_normal = (delta * vn).sum(1)
    d_tan = np.linalg.norm(delta - d_normal[:, None] * vn, axis=1)
    info["tangential_p50_mm"] = float(np.median(d_tan) * 1000)
    info["tangential_p95_mm"] = float(np.percentile(d_tan, 95) * 1000)
    return V + delta, delta, info


def hard_projection(V, cloud, radius=0.005, min_n=3):
    """Baseline (fig_sagittal_depth_projected.py): replace camera Z with cloud P5 Z."""
    tree = cKDTree(cloud[:, :2])
    nb = tree.query_ball_point(V[:, :2], radius, workers=-1)
    out = V.copy()
    for i, ix in enumerate(nb):
        if len(ix) >= min_n:
            out[i, 2] = np.percentile(cloud[ix, 2], 5)
    return out


def mesh_quality(V0, V1, F):
    """Face-normal flips and edge-length distortion relative to the input mesh."""
    def fn(V):
        tri = V[F]; n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-15)
    flip = float(np.mean((fn(V0) * fn(V1)).sum(1) < 0))
    E = edges(F)
    l0 = np.linalg.norm(V0[E[:, 0]] - V0[E[:, 1]], axis=1)
    l1 = np.linalg.norm(V1[E[:, 0]] - V1[E[:, 1]], axis=1)
    rel = np.abs(l1 - l0) / (l0 + 1e-12)
    return dict(face_flip_frac=flip, edge_strain_p50=float(np.median(rel)),
                edge_strain_p99=float(np.percentile(rel, 99)))


from metrics_v2 import ray_depth_residual
