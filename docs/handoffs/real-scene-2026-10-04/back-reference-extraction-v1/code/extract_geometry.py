"""XYZ-only curve candidates. No marker/line/atlas arguments are accepted."""
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree


def smooth_supported(z, valid, sigma):
    numerator = gaussian_filter(np.where(valid, z, 0.), sigma)
    denominator = gaussian_filter(valid.astype(float), sigma)
    return numerator / np.maximum(denominator, 1e-12)


def geometry_grid(points, config):
    dx, dy = config['grid_x_m'], config['grid_y_m']
    ymin, ymax = np.quantile(points[:, 1], config['y_quantiles'])
    xs = np.arange(points[:, 0].min(), points[:, 0].max() + dx / 2, dx)
    ys = np.arange(ymin, ymax + dy / 2, dy)
    xx, yy = np.meshgrid(xs, ys)
    dist, index = cKDTree(points[:, :2]).query(np.column_stack([xx.ravel(), yy.ravel()]))
    valid = dist.reshape(xx.shape) <= config['support_radius_m']
    z = points[index, 2].reshape(xx.shape)
    center = []
    for y in ys:
        local = points[np.abs(points[:, 1] - y) <= dy, 0]
        q = np.quantile(local, config['boundary_quantiles'])
        center.append(q.mean())
    center = np.asarray(center)
    smoothed = smooth_supported(z, valid, config['smooth_sigma'])
    detrended = smoothed.copy()
    for i in range(len(ys)):
        keep = valid[i]
        slope, intercept = np.polyfit(xs[keep], smoothed[i, keep], 1)
        detrended[i] -= slope * xs + intercept
    candidates = valid & (np.abs(xx - center[:, None]) <= config['search_halfwidth_m'])
    return xs, ys, valid, smoothed, detrended, center, candidates


def continuous_path(cost, config):
    """First-order dynamic programming, every valid output row retained."""
    limit = int(round(config['max_step_m'] / config['grid_x_m']))
    nrows, ncols = cost.shape
    previous = cost[0].copy()
    back = np.zeros((nrows, ncols), dtype=np.int32)
    offsets = np.arange(-limit, limit + 1)
    penalties = config['step_weight'] * (offsets * config['grid_x_m'] / config['step_scale_m']) ** 2
    for i in range(1, nrows):
        options = np.full((len(offsets), ncols), np.inf)
        for k, shift in enumerate(offsets):
            dst = np.arange(max(0, -shift), min(ncols, ncols - shift))
            options[k, dst] = previous[dst + shift] + penalties[k]
        best = np.argmin(options, axis=0)
        previous = cost[i] + options[best, np.arange(ncols)]
        back[i] = np.arange(ncols) + offsets[best]
    if not np.isfinite(previous).any():
        return None
    path = np.empty(nrows, dtype=np.int32)
    path[-1] = np.argmin(previous)
    for i in range(nrows - 1, 0, -1):
        path[i - 1] = back[i, path[i]]
    return path


def extract(points, config):
    xs, ys, valid, z, detrended, center, candidates = geometry_grid(points, config)
    nrows, ncols = z.shape
    mirror = np.zeros_like(z)
    pairs = np.zeros_like(z, dtype=int)
    for offset in config['mirror_offsets_m']:
        step = int(round(offset / config['grid_x_m']))
        for j in range(step, ncols - step):
            keep = valid[:, j - step] & valid[:, j + step]
            mirror[:, j] += np.where(keep, np.abs(detrended[:, j - step] - detrended[:, j + step]), 0.)
            pairs[:, j] += keep
    mirror /= np.maximum(pairs, 1)
    background = smooth_supported(z, valid, config['background_sigma'])
    groove = -(z - background)
    central = config['center_weight'] * ((xs[None, :] - center[:, None]) / config['search_halfwidth_m']) ** 2
    costs = {
        'SYMMETRY_DP': np.where(candidates & (pairs >= config['minimum_mirror_pairs']), mirror / config['data_scale_m'] + central, np.inf),
        'GROOVE_DP': np.where(candidates, groove / config['data_scale_m'] + central, np.inf),
    }
    xy_tree = cKDTree(points[:, :2])
    result = {}
    paths = {'BOUNDARY_CENTER': np.column_stack([center, ys])}
    for name, cost in costs.items():
        path = continuous_path(cost, config)
        if path is not None:
            paths[name] = np.column_stack([xs[path], ys])
        else:
            result[name] = {'status': 'NO_CONTINUOUS_SUPPORTED_PATH'}
    for name, xy in paths.items():
        distance, indices = xy_tree.query(xy)
        result[name] = {'status': 'COMPLETE', 'query_xy_m': xy, 'curve_m': points[indices],
                        'source_point_indices': indices, 'xy_snap_distance_m': distance,
                        'query_y_m': ys}
    grid = {'xs_m': xs, 'ys_m': ys, 'depth_m': z, 'valid': valid,
            'boundary_center_m': center, 'symmetry_cost': mirror, 'groove_cost': groove}
    return result, grid
