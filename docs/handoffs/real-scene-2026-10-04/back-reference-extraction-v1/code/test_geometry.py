"""Small analytic checks for curve extraction, not medical validation."""
import json
from pathlib import Path
import numpy as np
from extract_geometry import extract, continuous_path


def main():
    config = json.loads((Path(__file__).parents[1] / 'CONFIG.json').read_text(encoding='utf-8-sig'))
    x, y = np.meshgrid(np.arange(-.16, .1601, .002), np.arange(-.25, .2501, .002))
    depth = 1.0 + .012 * np.exp(-.5 * ((x - .02) / .009) ** 2)
    points = np.column_stack([x.ravel(), y.ravel(), depth.ravel()])
    curves, _ = extract(points, config)
    assert all(r['status'] == 'COMPLETE' for r in curves.values())
    assert abs(np.median(curves['BOUNDARY_CENTER']['query_xy_m'][:, 0])) < .003
    assert abs(np.median(curves['GROOVE_DP']['query_xy_m'][:, 0]) - .02) < .008
    for row in curves.values():
        np.testing.assert_array_equal(row['curve_m'], points[row['source_point_indices']])
    costs = np.full((5, 9), 100.)
    costs[np.arange(5), np.arange(5) + 1] = 0.
    np.testing.assert_array_equal(continuous_path(costs, config), np.arange(5) + 1)
    print(json.dumps({'status': 'PASS', 'checks': ['analytic_boundary', 'analytic_groove', 'all_methods_execute', 'source_surface_binding', 'DP_path']}))


if __name__ == '__main__': main()
