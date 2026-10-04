"""Post-only independent numeric verification of the public point caches."""
import ast
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    cfg = read(ROOT / 'CONTRACT.json')
    given = cfg['input_indices']
    query = cfg['query_indices']
    assert not set(given) & set(query)
    ids = read(ROOT / 'POSTERIOR_FACE_IDS.json')['face_ids']
    checked = []
    noise_by_subject = {}
    cache_manifest = read(ROOT / 'FINAL_POINT_CACHE_MANIFEST.json')
    cache_hash = {(r['subject'], r['case'], r['method']): r['sha256'] for r in cache_manifest}
    for subject in cfg['subjects']:
        for case in cfg['cases']:
            inp = np.load(ROOT / 'inputs' / subject / (case + '.npz'))
            truth = np.load(ROOT / 'evaluation_truth' / subject / (case + '.npz'))
            np.testing.assert_array_equal(inp['input_indices'], given)
            np.testing.assert_array_equal(truth['query_indices'], query)
            np.testing.assert_array_equal(inp['exact_xyz_m'], truth['reference_xyz_m'][given])
            np.testing.assert_allclose(np.linalg.norm(inp['noise_m'], axis=1), .005, rtol=0, atol=1e-15)
            np.testing.assert_allclose(inp['noisy_xyz_m'], inp['exact_xyz_m'] + inp['noise_m'], rtol=0, atol=1e-15)
            if subject in noise_by_subject:
                np.testing.assert_array_equal(inp['noise_m'], noise_by_subject[subject])
            else:
                noise_by_subject[subject] = inp['noise_m'].copy()
            rows = read(ROOT / 'runs' / subject / case / 'results.json')
            assert [r['method'] for r in rows] == cfg['methods']
            for row in rows:
                method = row['method']
                path = ROOT / 'runs' / subject / case / (method + '.npz')
                assert sha(path) == cache_hash[subject, case, method]
                z = np.load(path)
                np.testing.assert_array_equal(z['input_indices'], given)
                np.testing.assert_array_equal(z['query_indices'], query)
                assert np.isfinite(z['xyz_m']).all()
                assert np.isin(z['face_id'], ids).all()
                assert z['barycentric'].min() >= -1e-10
                np.testing.assert_allclose(z['barycentric'].sum(axis=1), 1, rtol=0, atol=1e-10)
                delta = z['xyz_m'] - truth['reference_xyz_m']
                normal = truth['reference_normals']
                signed = np.einsum('ij,ij->i', delta, normal)
                dist = np.linalg.norm(delta, axis=1) * 1000
                tangent = np.linalg.norm(delta - signed[:, None] * normal, axis=1) * 1000
                normal_abs = np.abs(signed) * 1000
                angles = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', z['normals'], normal), -1, 1)))
                supplied = inp['noisy_xyz_m' if method == 'REF4_NOISY5' else 'exact_xyz_m']
                expected = {
                    'per_probe_error_mm': dist,
                    'per_probe_tangent_mm': tangent,
                    'per_probe_normal_abs_mm': normal_abs,
                    'per_probe_normal_angle_deg': angles,
                    'query_median_mm': np.median(dist[query]),
                    'query_p95_mm': np.percentile(dist[query], 95),
                    'query_tangent_median_mm': np.median(tangent[query]),
                    'query_normal_median_mm': np.median(normal_abs[query]),
                    'query_normal_angle_median_deg': np.median(angles[query]),
                    'provided_reference_true_median_mm': np.median(dist[given]),
                    'provided_input_fit_median_mm': np.median(np.linalg.norm(z['xyz_m'][given] - supplied, axis=1) * 1000),
                    'projection_distance_median_mm': np.median(z['projection_distance_m']) * 1000,
                }
                for key, value in expected.items():
                    np.testing.assert_allclose(value, row[key], rtol=0, atol=1e-9)
                checked.append(row)
    assert len(checked) == len(cache_manifest) == 180
    assert read(ROOT / 'ALL_RESULTS.json') == checked
    with (ROOT / 'PER_PROBE_RESULTS.csv').open(encoding='utf-8-sig', newline='') as f:
        point_rows = list(csv.DictReader(f))
    raw = {(r['subject'], r['case'], r['method']): r for r in checked}
    probe_index = {p['id']: i for i, p in enumerate(read(ROOT / 'ATLAS.json')['records'])}
    for row in point_rows:
        reference = raw[row['subject'], row['case'], row['method']]
        i = probe_index[row['probe_id']]
        assert (row['provided_reference'] == 'True') == (i in given)
        for column, key in [('error_mm', 'per_probe_error_mm'), ('tangent_mm', 'per_probe_tangent_mm'),
                            ('normal_abs_mm', 'per_probe_normal_abs_mm'), ('normal_angle_deg', 'per_probe_normal_angle_deg')]:
            np.testing.assert_allclose(float(row[column]), reference[key][i], rtol=0, atol=1e-10)
    assert len(point_rows) == 1440
    assert sum(r['provided_reference'] == 'False' for r in point_rows) == 720
    aggregate = read(ROOT / 'AGGREGATED_RESULTS.json')
    for summary in aggregate['summaries']:
        subset = [r for r in checked if r['case'] == summary['case'] and r['method'] == summary['method']
                  and ('dev' if r['subject'] in cfg['dev'] else 'validation_consumed') == summary['role']]
        assert len(subset) == summary['sources']
        for key in summary:
            if key not in ('role', 'case', 'method', 'sources'):
                np.testing.assert_allclose(np.median([r[key] for r in subset]), summary[key], rtol=0, atol=1e-10)
    for row in aggregate['paired_changes']:
        value = raw[row['subject'], row['case'], row['method']]['query_median_mm'] - raw[row['subject'], row['case'], 'FIXED']['query_median_mm']
        np.testing.assert_allclose(value, row['query_change_vs_fixed_mm'], rtol=0, atol=1e-10)
    assert len(aggregate['summaries']) == 18 and len(aggregate['paired_changes']) == 120
    visuals = read(ROOT / 'VISUALIZATION_MANIFEST.json')
    for row in visuals:
        assert sha(ROOT / 'figures' / Path(row['path']).name) == row['sha256']
        for cached in row['input_point_cache_hashes']:
            assert cached['sha256'] == cache_hash[row['subject'], row['case'], cached['method']]
    assert len(visuals) == 60
    source_root = '/raid5/xuhd/datasets/back_reference_assisted_v1_20261004/'
    frozen_local = 0
    for row in read(ROOT / 'SOURCE_FREEZE.json'):
        if row['path'].startswith(source_root):
            path = ROOT / row['path'][len(source_root):]
            assert sha(path) == row['sha256'], path
            frozen_local += 1
    scripts = list((ROOT / 'code').glob('*.py')) + list((ROOT / 'frozen_baseline_code').glob('*.py'))
    for path in scripts:
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    report = dict(status='PASS',post_execution_read_only_verification=True,point_caches=180,
                  scalar_and_per_probe_metrics_recomputed=180,point_csv_rows=1440,unprovided_csv_rows=720,
                  aggregate_groups=18,paired_comparisons=120,case_image_sha256=60,
                  exported_current_source_freeze_entries=frozen_local,python_ast_files=len(scripts),
                  input_query_intersection=[],noise_norm_mm=5,noise_shared_across_cases=True,
                  local_mesh_reconstruction=False,mesh_reconstruction_checked_in_server_runner=True,
                  new_estimates=0,new_mesh_fits=0,script_sha256=sha(Path(__file__)))
    (ROOT / 'DELIVERY_NUMERICAL_VERIFICATION.json').write_bytes((json.dumps(report,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
