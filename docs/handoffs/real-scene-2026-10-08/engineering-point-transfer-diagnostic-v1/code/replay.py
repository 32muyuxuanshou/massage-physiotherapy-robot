"""Independent arithmetic replay using only this delivery's small caches."""
import csv, json, hashlib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    cfg = json.loads((ROOT / 'EXECUTION_CONFIG.json').read_text(encoding='utf-8'))
    with np.load(ROOT / 'canonical_cache.npz') as z:
        atlas = json.loads((ROOT / 'FROZEN_POINTS.json').read_text(encoding='utf-8'))
        b = np.asarray([r['barycentric'] for r in atlas['records']])
        np.testing.assert_allclose((z['triangles_m'] * b[:, :, None]).sum(1), z['xyz_m'], atol=1e-15, rtol=0)
    with np.load(ROOT / 'controlled_cache.npz') as z:
        d = (z['xyz_m'] - z['reference_xyz_m']) * 1000
        e = np.linalg.norm(d, axis=2).ravel()
        rows = list(csv.DictReader((ROOT / 'CONTROLLED_POINTS.csv').open(encoding='utf-8')))
        np.testing.assert_allclose(e, [float(r['error_mm']) for r in rows], atol=1e-10, rtol=0)
        normal = np.sum(d * z['reference_normals'], axis=2)
        tangent = np.linalg.norm(d - normal[:, :, None] * z['reference_normals'], axis=2).ravel()
        np.testing.assert_allclose(tangent, [float(r['tangent_error_mm']) for r in rows], atol=1e-10, rtol=0)
        aggregates = json.loads((ROOT / 'CONTROLLED_AGGREGATED.json').read_text(encoding='utf-8'))
        for aggregate in aggregates:
            q = [r for r in rows if (r['role'], r['case'], r['method']) == (aggregate['role'], aggregate['case'], aggregate['method'])]
            subjects = sorted({r['subject'] for r in q})
            values = [np.median([float(r['error_mm']) for r in q if r['subject'] == subject]) for subject in subjects]
            np.testing.assert_allclose(np.median(values), aggregate['subject_equal_point_median_mm'], atol=1e-10, rtol=0)
            np.testing.assert_allclose(np.percentile([float(r['error_mm']) for r in q], 95), aggregate['pooled_point_p95_mm'], atol=1e-10, rtol=0)
    with np.load(ROOT / 'real_cache.npz') as z:
        xyz = (z['triangles_m'] * z['barycentric'][None, None, None, :, :, None]).sum(-2)
        np.testing.assert_allclose(xyz, z['xyz_m'][:, :, 1:], atol=1e-14, rtol=0)
        rows = list(csv.DictReader((ROOT / 'REAL_POSITIONS.csv').open(encoding='utf-8')))
        np.testing.assert_allclose(z['xyz_m'].reshape(-1, 3), [[float(r[k]) for k in ['x_m', 'y_m', 'z_m']] for r in rows], atol=1e-14, rtol=0)
        spans = np.max([np.linalg.norm(z['xyz_m'][:, a] - z['xyz_m'][:, b], axis=-1) * 1000 for a, b in [(0, 1), (0, 2), (1, 2)]], axis=0)
        rows = list(csv.DictReader((ROOT / 'REAL_STABILITY_POINTS.csv').open(encoding='utf-8')))
        np.testing.assert_allclose(spans.ravel(), [float(r['max_pairwise_span_mm']) for r in rows], atol=1e-10, rtol=0)
        aggregates = json.loads((ROOT / 'REAL_AGGREGATED.json').read_text(encoding='utf-8'))
        for aggregate in aggregates:
            q = [r for r in rows if (r['role'], r['method']) == (aggregate['role'], aggregate['method'])]
            subjects = sorted({r['subject'] for r in q})
            values = [np.median([float(r['max_pairwise_span_mm']) for r in q if r['subject'] == subject]) for subject in subjects]
            np.testing.assert_allclose(np.median(values), aggregate['subject_equal_span_median_mm'], atol=1e-10, rtol=0)
    visuals = json.loads((ROOT / 'VISUALIZATION_MANIFEST.json').read_text(encoding='utf-8'))['new_pages']
    for r in visuals: assert hashlib.sha256((ROOT / r['path']).read_bytes()).hexdigest() == r['sha256']
    out = dict(status='PASS', canonical_points=8, controlled_point_errors=1920, real_positions=1440,
        real_face_bindings=960, real_stability_spans=480, visualizations_hashed=len(visuals),
        controlled_aggregation_groups=24, real_aggregation_groups=6,
        no_native_MHR_or_raw_patient_data_needed=True, full_mesh_replay=False, medical_accuracy=False, new_fits=0)
    (ROOT / 'CACHE_REPLAY.json').write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8'); print(json.dumps(out))


if __name__ == '__main__': main()
