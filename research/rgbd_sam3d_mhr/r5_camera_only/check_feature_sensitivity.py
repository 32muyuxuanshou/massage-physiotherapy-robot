"""CPU sensitivity diagnostic, not a replacement prediction or a new model.

Only channel 12 changes. A native TRAIN median is used without Camera B,
and the counterfactual does not represent a physically resampled depth image.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from camera_head import CameraHead


def run(root, out):
    torch.set_num_threads(2)
    source = root/'assets/compact_real'
    rows = json.loads((source/'MANIFEST.json').read_text())['records']
    keys = ['rgb', 'metric', 'original_camera', 'K', 'bbox_center', 'bbox_scale', 'available']
    data = {k: [] for k in keys}
    for row in rows:
        with np.load(source/row['compact_file']) as z:
            for k in keys:
                data[k].append(z[k])
    data = {k: torch.as_tensor(np.stack(v)) for k, v in data.items()}
    distributions = json.loads((out/'CACHE_CAMERA_AND_FEATURE_AUDIT.json').read_text())['feature_distributions']
    reference = distributions[12]['native']['median']
    reports = []
    for mode in ['native_only', 'mixed']:
        for seed in [11, 23, 37]:
            state = torch.load(root/f'continuation/{mode}_s{seed}/best.pt', map_location='cpu', weights_only=False)
            model = CameraHead(state['head']['metric_mean'], state['head']['metric_std'], 'metric_xyz')
            model.load_state_dict(state['head']); model.eval()
            with torch.no_grad():
                before = model(data['rgb'], data['metric'], data['original_camera'], data['K'],
                               data['bbox_center'], data['bbox_scale'], data['available']).numpy()
                changed = data['metric'].clone(); changed[:, 12] = reference
                after = model(data['rgb'], changed, data['original_camera'], data['K'],
                              data['bbox_center'], data['bbox_scale'], data['available']).numpy()
            saved = np.stack([np.load(root/f'real_predictions/repaired__continuation__{mode}_s{seed}'/r['compact_file'])['pred_cam_t'].reshape(3) for r in rows])
            assert np.max(np.abs(before-saved)) < 2e-6
            delta = (after-before)*1000
            reports.append(dict(mode=mode, seed=seed, native_TRAIN_valid_fraction_reference=reference,
                                actual_prediction_match_max_m=float(np.max(np.abs(before-saved))),
                                mean_delta_xyz_mm=delta.mean(0).tolist(), median_delta_xyz_mm=np.median(delta, axis=0).tolist(),
                                median_delta_norm_mm=float(np.median(np.linalg.norm(delta, axis=1))),
                                records=[dict(key=Path(r['compact_file']).stem, identity=r['identity'], role=r['role'],
                                              original_feature=float(data['metric'][i, 12]),
                                              response_xyz_mm=delta[i].tolist(), response_norm_mm=float(np.linalg.norm(delta[i])))
                                         for i, r in enumerate(rows)]))
            print('FEATURE_SENSITIVITY', mode, seed, reports[-1]['median_delta_xyz_mm'], flush=True)
    result = dict(status='EXECUTED_CPU', feature='valid_fraction_only', replacement_source='native TRAIN median',
                  Camera_B_read=False, TEST_read=False, fitting=False, training=False,
                  interpretation='feature sensitivity only; no claim that this is a valid deployment fix, or that B error improves',
                  records=reports)
    (out/'VALID_FRACTION_SENSITIVITY.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); run(a.root, a.out)
