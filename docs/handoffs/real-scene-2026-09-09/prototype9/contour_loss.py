"""Piecewise differentiable sparse silhouette sections, not dense rendering.

Coordinates, reference bands and bbox_width are original-image pixels. Each
forward dynamically chooses intersecting edges and the union interval containing
anchor_x (2700 by default). Discrete edge/interval decisions use detached values;
the selected endpoints are recomputed from live uv tensors. Gradients therefore
apply locally while that selection is stable, not through topology changes.
This loss sees the projected triangle union, without depth/occlusion supervision.
"""
import torch
import torch.nn.functional as F


def section(uv, faces, y, anchor_x=2700.0, merge_tolerance=1e-4):
    """Return live [left, right] x coordinates, or None if no anchored section.

    uv: [V,2] floating tensor; faces: [F,3] integer tensor on the same device.
    The half-open edge test and union tolerance match LOCAL_GEOMETRY/analyze.py.
    """
    edge_pairs = ((0, 1), (1, 2), (2, 0))
    with torch.no_grad():
        tri = uv.detach()[faces]
        starts = tri[:, [0, 1, 2]]
        ends = tri[:, [1, 2, 0]]
        valid = ((starts[..., 1] <= y) & (ends[..., 1] > y)) | (
            (ends[..., 1] <= y) & (starts[..., 1] > y))
        face_ids = torch.nonzero(valid.sum(1) == 2, as_tuple=False).flatten()
        if face_ids.numel() == 0:
            return None
        chosen_edges = torch.nonzero(valid[face_ids], as_tuple=False)[:, 1].reshape(-1, 2)
        aa = starts[face_ids[:, None], chosen_edges]
        bb = ends[face_ids[:, None], chosen_edges]
        xs = aa[..., 0] + (y - aa[..., 1]) / (bb[..., 1] - aa[..., 1]) * (bb[..., 0] - aa[..., 0])
        order = xs.argsort(dim=1)
        xs = xs.gather(1, order).cpu().tolist()
        edges = chosen_edges.gather(1, order).cpu().tolist()
        ids = face_ids.cpu().tolist()
        intervals = sorted((pair[0], pair[1], (fid, edge[0]), (fid, edge[1]))
                           for pair, fid, edge in zip(xs, ids, edges))
        merged = []
        for lo, hi, left, right in intervals:
            if merged and lo <= merged[-1][1] + merge_tolerance:
                if hi > merged[-1][1]:
                    merged[-1][1], merged[-1][3] = hi, right
            else:
                merged.append([lo, hi, left, right])
        selected = next((item for item in merged if item[0] <= anchor_x <= item[1]), None)
    if selected is None:
        return None
    endpoints = []
    for face_id, edge_id in selected[2:]:
        i, j = edge_pairs[edge_id]
        a, b = uv[faces[face_id, i]], uv[faces[face_id, j]]
        endpoints.append(a[0] + (y - a[1]) / (b[1] - a[1]) * (b[0] - a[0]))
    return torch.stack(endpoints)


def contour_loss(uv, faces, samples, bbox_width, anchor_x=2700.0, beta=0.01):
    """Mean band-insensitive smooth L1 on normalized endpoint residuals.

    samples: nonempty list of dicts with y, side (0=left/1=right),
    reference_x, uncertainty_px; optional per-reference anchor_x.
    beta is in bbox-width-normalized units. Missing anchored intervals raise,
    so failed sections cannot silently reduce the training objective.
    Returns (scalar loss, live endpoint vector) for loss and diagnostics.
    """
    predictions = []
    for reference in samples:
        endpoints = section(uv, faces, reference['y'], reference.get('anchor_x', anchor_x))
        if endpoints is None:
            raise ValueError(f"No contour interval at y={reference['y']} containing anchor")
        predictions.append(endpoints[reference['side']])
    predictions = torch.stack(predictions)
    targets = uv.new_tensor([r['reference_x'] for r in samples])
    bands = uv.new_tensor([r['uncertainty_px'] for r in samples])
    residual = (predictions - targets).abs().sub(bands).clamp_min(0) / bbox_width
    loss = F.smooth_l1_loss(residual, torch.zeros_like(residual), beta=beta)
    return loss, predictions


def _finite_difference_check():
    # y=3 stays away from vertices; both endpoint errors exceed the bands.
    # Perturbation leaves active triangle edges and interval union unchanged.
    uv = torch.tensor([[0., 0.], [10., 0.], [10., 10.], [0., 10.]],
                      dtype=torch.float64, requires_grad=True)
    faces = torch.tensor([[0, 1, 2], [0, 2, 3]])
    refs = [dict(y=3., side=0, reference_x=-1., uncertainty_px=.2),
            dict(y=3., side=1, reference_x=12., uncertainty_px=.3)]
    loss, endpoints = contour_loss(uv, faces, refs, 10., anchor_x=5., beta=.2)
    gradient, = torch.autograd.grad(loss, uv)
    eps = 1e-5
    finite = torch.zeros_like(uv)
    for i in range(uv.shape[0]):
        for j in range(2):
            plus, minus = uv.detach().clone(), uv.detach().clone()
            plus[i, j] += eps
            minus[i, j] -= eps
            high = contour_loss(plus, faces, refs, 10., anchor_x=5., beta=.2)[0]
            low = contour_loss(minus, faces, refs, 10., anchor_x=5., beta=.2)[0]
            finite[i, j] = (high - low) / (2 * eps)
    assert loss.item() > 0
    assert gradient.abs().sum().item() > 0
    torch.testing.assert_close(endpoints, uv.new_tensor([0., 10.]))
    torch.testing.assert_close(gradient, finite, rtol=1e-5, atol=1e-7)
    print({'status': 'PASS', 'loss': loss.item(),
           'max_gradient_error': (gradient - finite).abs().max().item(),
           'scope': 'CPU synthetic local finite differences; not model training validation'})


if __name__ == '__main__':
    _finite_difference_check()
