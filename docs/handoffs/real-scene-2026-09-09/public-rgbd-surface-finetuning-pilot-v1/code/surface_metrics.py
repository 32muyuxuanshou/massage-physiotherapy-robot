"""Independent surface metrics for PUBLIC_RGBD_SURFACE_FINETUNING_PILOT_V1.

All public functions accept geometry in metres and report distance in millimetres.
Camera coordinates use OpenCV convention: +X right, +Y down, +Z forward.
"""
from __future__ import annotations

import os
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

import numpy as np
from scipy.spatial import cKDTree


def camera_to_world(points_camera_m: np.ndarray, R_world_to_camera: np.ndarray,
                    T_world_to_camera_m: np.ndarray) -> np.ndarray:
    return (np.asarray(points_camera_m) - T_world_to_camera_m) @ R_world_to_camera


def world_to_camera(points_world_m: np.ndarray, R_world_to_camera: np.ndarray,
                    T_world_to_camera_m: np.ndarray) -> np.ndarray:
    return np.asarray(points_world_m) @ R_world_to_camera.T + T_world_to_camera_m


def _summary(distance_m: np.ndarray, name: str) -> dict:
    d = np.asarray(distance_m, np.float64).reshape(-1) * 1000.0
    if not len(d):
        return {"metric": name, "sample_count": 0, "status": "NO_VALID_OVERLAP"}
    return {"metric": name, "sample_count": int(len(d)), "unit": "mm",
            "mean_mm": float(d.mean()), "median_mm": float(np.median(d)),
            "p90_mm": float(np.percentile(d, 90)),
            "p95_mm": float(np.percentile(d, 95)), "max_mm": float(d.max())}


def legacy_point_to_vertex(observed_m: np.ndarray, vertices_m: np.ndarray) -> dict:
    """The V1 one-sided observed-point to nearest MHR vertex metric."""
    d = cKDTree(np.asarray(vertices_m, np.float64)).query(
        np.asarray(observed_m, np.float64), workers=-1)[0]
    return _summary(d, "legacy_observed_to_nearest_vertex")


def _point_triangle_distance_squared(points: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Exact distance for paired/broadcastable points (...,3), triangles (...,3,3).

    This is the region-test algorithm from Real-Time Collision Detection. Degenerate
    triangles fall back to their three line segments.
    """
    p = np.asarray(points, np.float64)
    tri = np.asarray(triangles, np.float64)
    a, b, c = tri[..., 0, :], tri[..., 1, :], tri[..., 2, :]
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = np.sum(ab * ap, -1), np.sum(ac * ap, -1)
    bp = p - b
    d3, d4 = np.sum(ab * bp, -1), np.sum(ac * bp, -1)
    cp = p - c
    d5, d6 = np.sum(ab * cp, -1), np.sum(ac * cp, -1)
    out = np.full(np.broadcast_shapes(p.shape[:-1], tri.shape[:-2]), np.inf, np.float64)

    def assign(mask, value):
        nonlocal out
        out = np.where(mask, value, out)

    assign((d1 <= 0) & (d2 <= 0), np.sum(ap * ap, -1))
    assign((d3 >= 0) & (d4 <= d3), np.sum(bp * bp, -1))
    vc = d1 * d4 - d3 * d2
    mask = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    v = d1 / np.where(np.abs(d1 - d3) > 1e-15, d1 - d3, 1)
    q = a + v[..., None] * ab
    assign(mask, np.sum((p - q) ** 2, -1))
    assign((d6 >= 0) & (d5 <= d6), np.sum(cp * cp, -1))
    vb = d5 * d2 - d1 * d6
    mask = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    w = d2 / np.where(np.abs(d2 - d6) > 1e-15, d2 - d6, 1)
    q = a + w[..., None] * ac
    assign(mask, np.sum((p - q) ** 2, -1))
    va = d3 * d6 - d5 * d4
    denom = (d4 - d3) + (d5 - d6)
    mask = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    w = (d4 - d3) / np.where(np.abs(denom) > 1e-15, denom, 1)
    q = b + w[..., None] * (c - b)
    assign(mask, np.sum((p - q) ** 2, -1))
    face = np.isinf(out)
    denom_face = va + vb + vc
    v = vb / np.where(np.abs(denom_face) > 1e-15, denom_face, 1)
    w = vc / np.where(np.abs(denom_face) > 1e-15, denom_face, 1)
    q = a + ab * v[..., None] + ac * w[..., None]
    assign(face, np.sum((p - q) ** 2, -1))

    # Degenerate fallback: minimum distance to the three closed segments.
    normal2 = np.sum(np.cross(ab, ac) ** 2, -1)
    degenerate = normal2 < 1e-20
    if np.any(degenerate):
        seg_best = np.full_like(out, np.inf)
        for s0, s1 in ((a, b), (b, c), (c, a)):
            edge = s1 - s0
            t = np.sum((p - s0) * edge, -1) / np.maximum(np.sum(edge * edge, -1), 1e-20)
            q = s0 + np.clip(t, 0, 1)[..., None] * edge
            seg_best = np.minimum(seg_best, np.sum((p - q) ** 2, -1))
        out = np.where(degenerate, seg_best, out)
    return out


def point_to_triangle_distances(observed_m: np.ndarray, vertices_m: np.ndarray,
                                faces: np.ndarray) -> np.ndarray:
    """Exact point-to-mesh distance using a conservative centroid-sphere BVH.

    For each query, all triangles whose centroid sphere can beat the current best
    are tested. This is exact; the tree only removes triangles with a proven lower
    bound above the incumbent distance.
    """
    points = np.asarray(observed_m, np.float64)
    triangles = np.asarray(vertices_m, np.float64)[np.asarray(faces, np.int64)]
    centroids = triangles.mean(1)
    radii = np.linalg.norm(triangles - centroids[:, None], axis=2).max(1)
    tree = cKDTree(centroids)
    nearest_centroid = tree.query(points, k=1, workers=-1)[1]
    incumbent = np.sqrt(_point_triangle_distance_squared(points, triangles[nearest_centroid]))
    max_radius = float(radii.max())
    candidates = tree.query_ball_point(points, incumbent + max_radius, workers=-1)
    answer = np.empty(len(points), np.float64)
    for i, ids in enumerate(candidates):
        ids = np.asarray(ids, np.int64)
        lower_bound = np.linalg.norm(centroids[ids] - points[i], axis=1) - radii[ids]
        ids = ids[lower_bound <= incumbent[i] + 1e-12]
        q = np.broadcast_to(points[i], (len(ids), 3))
        answer[i] = np.sqrt(_point_triangle_distance_squared(q, triangles[ids]).min())
    return answer


def point_to_triangle(observed_m: np.ndarray, vertices_m: np.ndarray,
                      faces: np.ndarray) -> dict:
    return _summary(point_to_triangle_distances(observed_m, vertices_m, faces),
                    "observed_to_exact_triangle_surface")


def render_depth(vertices_m: np.ndarray, faces: np.ndarray, K: np.ndarray,
                 height: int, width: int) -> np.ndarray:
    """Render metric Z-depth with an OpenCV-camera to OpenGL-camera transform."""
    import pyrender
    import trimesh
    faces = np.asarray(faces, np.int32)
    # DEPTH_ONLY may ignore the material's doubleSided flag on some EGL drivers.
    # Explicit reverse faces make the visibility contract deterministic.
    faces_two_sided = np.concatenate((faces, faces[:, ::-1]), axis=0)
    mesh = trimesh.Trimesh(vertices=np.asarray(vertices_m, np.float32),
                           faces=faces_two_sided, process=False)
    material = pyrender.MetallicRoughnessMaterial(doubleSided=True)
    scene = pyrender.Scene(bg_color=np.zeros(4), ambient_light=np.ones(3))
    scene.add(pyrender.Mesh.from_trimesh(mesh, material=material, smooth=False))
    camera = pyrender.IntrinsicsCamera(float(K[0, 0]), float(K[1, 1]),
                                      float(K[0, 2]), float(K[1, 2]), znear=0.05, zfar=10.0)
    pose = np.diag([1.0, -1.0, -1.0, 1.0])
    scene.add(camera, pose=pose)
    renderer = pyrender.OffscreenRenderer(viewport_width=width, viewport_height=height)
    try:
        depth = renderer.render(scene, flags=pyrender.RenderFlags.DEPTH_ONLY)
    finally:
        renderer.delete()
    return np.asarray(depth, np.float32)


def rendered_depth(observed_m: np.ndarray, vertices_m: np.ndarray, faces: np.ndarray,
                   K: np.ndarray, height: int, width: int) -> dict:
    """Compare held-out observed Z with rendered mesh Z at the same color pixels."""
    depth = render_depth(vertices_m, faces, K, height, width)
    p = np.asarray(observed_m, np.float64)
    u = np.rint(K[0, 0] * p[:, 0] / p[:, 2] + K[0, 2]).astype(np.int64)
    v = np.rint(K[1, 1] * p[:, 1] / p[:, 2] + K[1, 2]).astype(np.int64)
    inside = (p[:, 2] > 0) & (u >= 0) & (u < width) & (v >= 0) & (v < height)
    rendered = np.zeros(len(p), np.float32)
    rendered[inside] = depth[v[inside], u[inside]]
    overlap = inside & (rendered > 0)
    result = _summary(np.abs(rendered[overlap] - p[overlap, 2]),
                      "heldout_rendered_depth_absolute_z_residual")
    result.update({"observed_point_count": int(len(p)),
                   "in_image_count": int(inside.sum()), "overlap_count": int(overlap.sum()),
                   "mesh_coverage_of_observed_points": float(overlap.sum() / max(inside.sum(), 1)),
                   "signed_mean_mm": None if not overlap.any() else float(
                       ((rendered[overlap] - p[overlap, 2]) * 1000).mean()),
                   "depth_definition": "OpenCV camera +Z metric z-depth"})
    return result
