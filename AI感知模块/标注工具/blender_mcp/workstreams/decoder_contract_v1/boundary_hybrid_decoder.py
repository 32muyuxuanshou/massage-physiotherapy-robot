from __future__ import annotations

import numpy as np
import torch


WIDTH, HEIGHT = 1280, 1024


def to_original(x: np.ndarray, y: np.ndarray, w: int, h: int) -> np.ndarray:
    return np.stack(((x + 0.5) / w * WIDTH, (y + 0.5) / h * HEIGHT), axis=2).astype(np.float32)


def expectation_from_logits(logits: torch.Tensor) -> np.ndarray:
    b, p, h, w = logits.shape
    prob = torch.softmax(logits.flatten(2), dim=2).reshape(b, p, h, w)
    gx = torch.arange(w, dtype=torch.float32).view(1, 1, 1, w)
    gy = torch.arange(h, dtype=torch.float32).view(1, 1, h, 1)
    x = (prob * gx).sum((2, 3)); y = (prob * gy).sum((2, 3))
    return to_original(x.numpy(), y.numpy(), w, h)


def _fit(values: np.ndarray, center: int, length: int, curvature_epsilon: float) -> tuple[float, float, int]:
    if center <= 0: indices = np.asarray([0.0, 1.0, 2.0])
    elif center >= length - 1: indices = np.asarray([length - 3.0, length - 2.0, length - 1.0])
    else: indices = np.asarray([center - 1.0, center, center + 1.0])
    selected = values[indices.astype(int)]
    if not np.isfinite(selected).all(): return float(center), float("nan"), 1
    matrix = np.stack((indices * indices, indices, np.ones(3)), axis=1)
    try: a, b, _ = np.linalg.solve(matrix, selected)
    except np.linalg.LinAlgError: return float(center), float("nan"), 2
    if not np.isfinite(a) or not np.isfinite(b) or a >= -curvature_epsilon:
        return float(center), float(a), 3
    vertex = float(-b / (2.0 * a))
    if not np.isfinite(vertex) or not (-0.5 <= vertex < length - 0.5):
        return float(center), float(a), 4
    return vertex, float(a), 0


def decode_guarded(logits: np.ndarray, boundary_cells: int = 4, curvature_epsilon: float = 1e-8,
                   min_correction_original_px: float = 12.0) -> dict[str, np.ndarray]:
    if logits.ndim != 4 or not np.isfinite(logits).all():
        raise ValueError("logits must be finite BxPxHxW")
    tensor = torch.from_numpy(logits.astype(np.float32, copy=False))
    expectation = expectation_from_logits(tensor)
    b, p, h, w = logits.shape
    flat = logits.reshape(b, p, -1).argmax(axis=2)
    peak_x, peak_y = flat % w, flat // w
    requested = (peak_x < boundary_cells) | (peak_x >= w - boundary_cells) | (peak_y < boundary_cells) | (peak_y >= h - boundary_cells)
    x_log = torch.logsumexp(tensor, dim=2).numpy(); y_log = torch.logsumexp(tensor, dim=3).numpy()
    x = np.empty((b, p), np.float64); y = np.empty((b, p), np.float64)
    ax = np.empty((b, p), np.float64); ay = np.empty((b, p), np.float64)
    x_codes = np.zeros((b, p), np.uint8); y_codes = np.zeros((b, p), np.uint8)
    for i in range(b):
        for j in range(p):
            xv, xa, xc = _fit(x_log[i, j], int(peak_x[i, j]), w, curvature_epsilon)
            yv, ya, yc = _fit(y_log[i, j], int(peak_y[i, j]), h, curvature_epsilon)
            x[i, j], y[i, j], ax[i, j], ay[i, j] = xv, yv, xa, ya
            x_codes[i, j] = xc; y_codes[i, j] = yc
    requested_x = (peak_x < boundary_cells) | (peak_x >= w - boundary_cells)
    requested_y = (peak_y < boundary_cells) | (peak_y >= h - boundary_cells)
    accepted_x = requested_x & (x_codes == 0); accepted_y = requested_y & (y_codes == 0)
    accepted_before_magnitude = accepted_x | accepted_y
    quadratic = to_original(x, y, w, h)
    full_vector = np.where((requested & (x_codes == 0) & (y_codes == 0))[..., None], quadratic, expectation).astype(np.float32)
    hybrid = expectation.copy()
    hybrid[..., 0] = np.where(accepted_x, quadratic[..., 0], expectation[..., 0])
    hybrid[..., 1] = np.where(accepted_y, quadratic[..., 1], expectation[..., 1])
    correction = np.linalg.norm(hybrid - expectation, axis=2)
    magnitude_ok = correction >= float(min_correction_original_px)
    accepted = accepted_before_magnitude & magnitude_ok
    hybrid = np.where(accepted[..., None], hybrid, expectation)
    combined_codes = np.where(requested_x & (x_codes != 0), x_codes, 0).astype(np.uint8)
    combined_codes = np.where((combined_codes == 0) & requested_y & (y_codes != 0), 10 + y_codes, combined_codes).astype(np.uint8)
    combined_codes = np.where((combined_codes == 0) & accepted_before_magnitude & ~magnitude_ok, 20, combined_codes).astype(np.uint8)
    return {
        "expectation": expectation, "quadratic": quadratic, "hybrid_full_vector": full_vector, "hybrid": hybrid.astype(np.float32),
        "branch_requested": requested.astype(np.uint8), "branch_used": accepted.astype(np.uint8),
        "branch_requested_x": requested_x.astype(np.uint8), "branch_requested_y": requested_y.astype(np.uint8),
        "branch_used_x": accepted_x.astype(np.uint8), "branch_used_y": accepted_y.astype(np.uint8),
        "correction_magnitude_original_px": correction.astype(np.float32),
        "fallback_code": combined_codes, "fallback_code_x": x_codes, "fallback_code_y": y_codes,
        "peak_x": peak_x.astype(np.int16), "peak_y": peak_y.astype(np.int16),
        "curvature_x": ax.astype(np.float32), "curvature_y": ay.astype(np.float32),
    }
