"""CPU-only check of this public delivery's actual inputs and predictions."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def surface(uv, data):
    height = data['surface_height_mm'].astype(np.float64); valid = data['surface_valid']; h, w = height.shape
    u, v = map(float, uv); x = u*(w-1); y = v*(h-1)
    x0 = int(np.floor(x)); y0 = int(np.floor(y)); x1 = min(x0+1, w-1); y1 = min(y0+1, h-1)
    if not (0 <= x0 < w and 0 <= y0 < h) or not valid[y0:y1+1, x0:x1+1].all():
        return None
    a = x-x0; b = y-y0
    depth = ((1-a)*height[y0, x0]+a*height[y0, x1])*(1-b)+((1-a)*height[y1, x0]+a*height[y1, x1])*b
    xmin, xmax, zmin, zmax = data['xz_bounds_mm']
    return np.array([xmin+u*(xmax-xmin), depth, zmax-v*(zmax-zmin)])


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True); args = parser.parse_args()
    root = args.root
    manifest = {r['subject']: r for r in json.loads((root/'CASE_MANIFEST.json').read_text()) if r['eligible']}
    rows = json.loads((root/'PER_CASE_RESULTS.json').read_text()); values = {}
    for subject, record in manifest.items():
        path = root/'inputs'/(subject+'.npz'); assert sha(path) == record['input_sha256']
        values[subject] = dict(np.load(path))
    valid_targets = 0
    for row in rows:
        path = root/'predictions'/row['role']/Path(row['path']).name
        assert sha(path) == row['cache_sha256']
        pred = dict(np.load(path)); data = values[row['subject']]
        assert np.array_equal(pred['target_valid'], data['target_valid'])
        assert np.array_equal(pred['target_xyz_mm'], data['target_xyz_mm'])
        scale = np.diff(data['xz_bounds_mm'].reshape(2, 2), axis=1).ravel()
        error = np.linalg.norm((pred['pred_uv']-data['target_uv'])*scale, axis=1)
        assert np.allclose(error, pred['xz_error_mm'], rtol=0, atol=1e-6)
        assert abs(error[data['target_valid']].mean()-row['mean_xz_mm']) < 1e-6
        for i, uv in enumerate(pred['pred_uv']):
            xyz = surface(uv, data)
            assert bool(pred['surface_hit'][i]) == (xyz is not None)
            if xyz is not None:
                assert np.allclose(xyz, pred['pred_xyz_mm'][i], rtol=0, atol=1e-6)
        valid_targets += int(data['target_valid'].sum())
    result = dict(status='PASS', actual_inputs=len(manifest), actual_predictions=len(rows), valid_target_evaluations=valid_targets,
                  scope='CPU replay of actual public NPZ/hash/XZ/native surface interpolation; no model execution or fitting')
    (root/'DELIVERY_REPLAY.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
