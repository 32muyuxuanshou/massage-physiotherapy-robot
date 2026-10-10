"""Read existing Camera-only caches; no inference, fitting, or training."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


BODY_FIELDS = ['pred_vertices', 'global_rot', 'body_pose', 'shape', 'scale',
               'hand', 'face', 'pred_pose_raw', 'mhr_model_params',
               'pred_joint_coords', 'joint_global_rots', 'pred_keypoints_3d']
FEATURES = ['z_q10_m', 'z_q25_m', 'z_q50_m', 'z_q75_m', 'z_q90_m',
            'xyz_mean_x_m', 'xyz_mean_y_m', 'xyz_mean_z_m',
            'xyz_std_x_m', 'xyz_std_y_m', 'xyz_std_z_m', 'z_q90_q10_m',
            'valid_fraction', 'fx_over_width', 'fy_over_height',
            'cx_over_width', 'cy_over_height', 'bbox_over_width',
            'official_cam_x_m', 'official_cam_y_m', 'official_cam_z_m']
FEATURES += [f'body_q{q}_{axis}_m' for q in [25, 50, 75] for axis in 'xyz']
FEATURES += [f'body_mean_{axis}_m' for axis in 'xyz']
FEATURES += [f'body_std_{axis}_m' for axis in 'xyz']


def statistics(a):
    return dict(mean=float(a.mean()), std=float(a.std()), min=float(a.min()),
                q01=float(np.quantile(a, .01)), q05=float(np.quantile(a, .05)),
                median=float(np.median(a)), q95=float(np.quantile(a, .95)),
                q99=float(np.quantile(a, .99)), max=float(a.max()))


def run(root, out):
    out.mkdir(parents=True, exist_ok=True)
    history = root/'assets/real_evaluation/assets/original_assets'
    manifest = json.loads((root/'assets/compact_real/MANIFEST.json').read_text())['records']
    rows = []
    cells = sorted(p for p in (root/'real_evaluation').glob('repaired__*.json'))
    for result in cells:
        cell = result.stem
        evaluation = json.loads(result.read_text())
        for r in evaluation['records']:
            key = r['key']
            original = history/'official'/(key+'.npz')
            prediction = root/'real_predictions'/cell/(key+'.npz')
            with np.load(original) as a, np.load(prediction) as b, np.load(root/'assets/compact_real'/(key+'.npz')) as source:
                t0 = a['pred_cam_t'].reshape(3).astype('float64')
                t1 = b['pred_cam_t'].reshape(3).astype('float64')
                unchanged = all(np.array_equal(source['official_'+k], b[k]) for k in BODY_FIELDS)
                assert unchanged, (cell, key)
                delta = t1-t0
                actual = b['vertices_camera_A'].astype('float64')-a['vertices_camera_A']
                max_error = float(np.max(np.abs(actual-delta)))
                assert max_error < 2e-6, (cell, key, max_error)
            with np.load(root/'real_corrected/official'/(key+'.npz')) as a:
                official_applied = a['applied_translation_m'].reshape(3)
            with np.load(history/'inputs'/(key+'.npz')) as a:
                index_sha = hashlib.sha256(a['source_indices'].tobytes()).hexdigest()
                assert index_sha == r['A_sample_indices_sha256']
            applied = np.asarray(r['applied_translation_m'])
            rows.append(dict(cell=cell, key=key, identity=r['identity'], role=r['role'],
                             official_camera_xyz_m=t0.tolist(), new_camera_xyz_m=t1.tolist(),
                             model_delta_xyz_mm=(delta*1000).tolist(),
                             model_delta_norm_mm=float(np.linalg.norm(delta)*1000),
                             diagnostic_A_txyz_xyz_mm=(applied*1000).tolist(),
                             diagnostic_A_txyz_norm_mm=float(np.linalg.norm(applied)*1000),
                             diagnostic_endpoint_difference_xyz_mm=((delta+applied-official_applied)*1000).tolist(),
                             diagnostic_endpoint_difference_norm_mm=float(np.linalg.norm(delta+applied-official_applied)*1000),
                             all_12_Body_fields_exact_equal=unchanged,
                             vertex_delta_camera_delta_max_error_m=max_error,
                             fixed_A_indices_match=True,
                             prediction_sha256=hashlib.sha256(prediction.read_bytes()).hexdigest()))
        print('CAMERA_AUDITED', cell, len(evaluation['records']), flush=True)
    assert len(rows) == 3480
    feature_tables = {}
    for name in ['native', 'scan', 'real']:
        directory = root/f'assets/compact_{name}'
        source = json.loads((directory/'MANIFEST.json').read_text())['records']
        if name != 'real':
            source = [r for r in source if r['role'] == 'TRAIN']
        values = []
        for r in source:
            with np.load(directory/r['compact_file']) as z:
                values.append(z['metric'])
        feature_tables[name] = np.asarray(values, dtype='float64')
        print('FEATURES_READ', name, len(values), flush=True)
    feature_rows = []
    for i, name in enumerate(FEATURES):
        x = feature_tables['native'][:, i]
        active = bool(x.min() != x.max())
        data = dict(index=i, feature=name, native_train_constant=not active)
        for dataset, values in feature_tables.items():
            y = values[:, i]
            data[dataset] = statistics(y)
            data[dataset]['outside_native_train_range_fraction'] = float(np.mean((y < x.min()) | (y > x.max())))
        if active:
            zz = (feature_tables['real'][:, i]-x.mean())/max(x.std(), 1e-4)
            data['real_absolute_zscore_gt3_fraction'] = float(np.mean(np.abs(zz)>3))
        feature_rows.append(data)
    real_features = [dict(key=Path(r['compact_file']).stem, identity=r['identity'], role=r['role'],
                          features=dict(zip(FEATURES, map(float, x))))
                     for r, x in zip(manifest, feature_tables['real'])]
    report = dict(status='PASS', caches_checked=len(rows),
                  body_unchanged_records=sum(r['all_12_Body_fields_exact_equal'] for r in rows),
                  max_vertex_translation_consistency_error_m=max(r['vertex_delta_camera_delta_max_error_m'] for r in rows),
                  records=rows, feature_distributions=feature_rows, real_frame_features=real_features,
                  TEST_read=False, fitting_performed=False, new_inference=False,
                  interpretation='Camera changes and A-fit suggestions are not ground-truth translation errors')
    (out/'CACHE_CAMERA_AND_FEATURE_AUDIT.json').write_text(json.dumps(report, indent=2))
    print('AUDIT_COMPLETE', len(rows), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    run(args.root, args.out)
