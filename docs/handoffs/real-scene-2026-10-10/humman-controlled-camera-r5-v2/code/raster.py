"""CPU perspective z-buffer at integer pixel centres; both sides of every triangle."""
import math
import numpy as np
from numba import njit


@njit(cache=True)
def render_z(vertices, faces, K, height, width):
    depth = np.full((height, width), np.inf, np.float32)
    face_id = np.full((height, width), -1, np.int32)
    for fid in range(len(faces)):
        tri = vertices[faces[fid]]
        if tri[:, 2].min() <= 0.01:
            continue
        px = K[0, 0] * tri[:, 0] / tri[:, 2] + K[0, 2]
        py = K[1, 1] * tri[:, 1] / tri[:, 2] + K[1, 2]
        x0, x1 = max(0, int(math.ceil(px.min()))), min(width - 1, int(math.floor(px.max())))
        y0, y1 = max(0, int(math.ceil(py.min()))), min(height - 1, int(math.floor(py.max())))
        den = (py[1]-py[2])*(px[0]-px[2])+(px[2]-px[1])*(py[0]-py[2])
        if abs(den) < 1e-12:
            continue
        for y in range(y0, y1+1):
            for x in range(x0, x1+1):
                b0 = ((py[1]-py[2])*(x-px[2])+(px[2]-px[1])*(y-py[2])) / den
                b1 = ((py[2]-py[0])*(x-px[2])+(px[0]-px[2])*(y-py[2])) / den
                b2 = 1-b0-b1
                if min(b0, b1, b2) < -1e-7:
                    continue
                z = 1/(b0/tri[0, 2]+b1/tri[1, 2]+b2/tri[2, 2])
                if z < depth[y, x]:
                    depth[y, x], face_id[y, x] = z, fid
    for y in range(height):
        for x in range(width):
            if face_id[y, x] < 0:
                depth[y, x] = 0
    return depth, face_id


def exact_ray_qa(vertices, faces, K, depth, face_id, count=128):
    y, x = np.nonzero(depth)
    ids = np.linspace(0, len(y)-1, min(count, len(y))).astype(int)
    x, y = x[ids], y[ids]
    rays = np.column_stack(((x-K[0, 2])/K[0, 0], (y-K[1, 2])/K[1, 1], np.ones(len(x))))
    # Independent ray-plane intersection and 3D barycentric containment.
    tri = vertices[faces[face_id[y, x]]].astype(np.float64)
    e0, e1 = tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]
    normal = np.cross(e0, e1)
    z = np.sum(normal*tri[:, 0], axis=1)/np.sum(normal*rays, axis=1)
    q = rays*z[:, None]-tri[:, 0]
    a, b, c = np.sum(e0*e0, 1), np.sum(e0*e1, 1), np.sum(e1*e1, 1)
    d, e = np.sum(q*e0, 1), np.sum(q*e1, 1)
    det = a*c-b*b
    v, w = (c*d-b*e)/det, (a*e-b*d)/det
    error_mm = np.abs(z-depth[y, x])*1000
    return dict(ray_count=len(x), max_z_error_mm=float(error_mm.max()),
                p95_z_error_mm=float(np.quantile(error_mm, .95)),
                min_barycentric=float(np.min(np.column_stack((1-v-w, v, w)))))
