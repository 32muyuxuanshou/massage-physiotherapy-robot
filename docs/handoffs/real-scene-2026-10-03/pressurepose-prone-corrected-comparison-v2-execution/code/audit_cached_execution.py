"""Read-only mesh audit and independent recomputation into a temporary directory.

Run AFTER run_comparison.py --stage full. This script does not fit/infer a model.
The reviewed experiment directory and all original caches remain unchanged.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--delivery', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--history', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.delivery / 'code'))
    from data_v2 import load_json, save_json, sha
    from evaluate_cache import evaluate_subject
    from audit_outputs import audit_outputs

    contract = load_json(a.delivery / 'EXPERIMENT_CONTRACT.json')
    assert load_json(a.out / 'AGGREGATED_RESULTS.json')['status'] == 'FORMAL_COMPLETE'
    meshes = sorted((a.out / 'meshes').rglob('*.npz'))
    before = {str(x.relative_to(a.out)): sha(x) for x in meshes}
    records = []
    history = []
    # New evaluation outputs go to a temporary root, never over existing results.
    with tempfile.TemporaryDirectory(prefix='cache_recompute_', dir=a.out) as tmp:
        target = Path(tmp)
        (target / 'inputs').symlink_to(a.out / 'inputs', target_is_directory=True)
        (target / 'meshes').symlink_to(a.out / 'meshes', target_is_directory=True)
        for subject in contract['subjects']:
            original = load_json(a.out / 'evaluation' / subject / 'results.json')
            repeated = evaluate_subject(subject, a.delivery, target)
            assert repeated == original, 'CACHE_RECOMPUTE_ROW_DIFFERENCE ' + subject
            arrays_checked = 0
            for path in (target / 'evaluation' / subject).rglob('*_metrics.npz'):
                old = np.load(a.out / path.relative_to(target), allow_pickle=False)
                new = np.load(path, allow_pickle=False)
                assert old.files == new.files
                for key in old.files:
                    assert np.array_equal(old[key], new[key], equal_nan=True), (subject, key)
                    arrays_checked += 1
            records.append(dict(subject=subject, rows=len(repeated),
                                row_exact_equality=True, metric_arrays_exact=arrays_checked))
            print(subject, 'cache-only recompute exact', flush=True)

            old_path = a.history / 'subjects' / subject / 'mesh_parameters.npz'
            old = np.load(old_path, allow_pickle=False)
            new = np.load(a.out / 'meshes' / subject / 'seed_0' / 'Official.npz', allow_pickle=False)
            inp = np.load(a.out / 'inputs' / subject / 'input.npz', allow_pickle=False)
            diff = np.linalg.norm(new['vertices_m'] - old['Official_vertices'], axis=1) * 1000
            history.append(dict(subject=subject, historical_file=str(old_path),
                historical_sha256=sha(old_path), fresh_official_sha256=sha(a.out / 'initial' / subject / 'official_prediction.npz'),
                bbox_exact=np.array_equal(inp['bbox_xyxy'], old['bbox_xyxy']),
                K_exact=np.array_equal(inp['K'], old['K']),
                faces_exact=np.array_equal(new['faces'], old['faces']),
                official_vertex_difference_median_mm=float(np.median(diff)),
                official_vertex_difference_max_mm=float(diff.max()),
                official_cam_t_delta_mm=((new['mhr_pred_cam_t'] - old['Official_cam_t']) * 1000).tolist()))

    after = {str(x.relative_to(a.out)): sha(x) for x in meshes}
    assert before == after
    assert sum(r['rows'] for r in records) == 300
    result = dict(status='PASS', scope='all 300 cached evaluations; no inference/optimization',
        rows=300, cached_mesh_count=len(meshes), cached_meshes_unchanged=True,
        existing_evaluation_outputs_unchanged=True, records=records)
    save_json(a.out / 'CACHE_RECOMPUTE_AUDIT.json', result)
    save_json(a.out / 'OFFICIAL_HISTORY_IDENTITY_AUDIT.json', dict(
        scope='Only RGB Official baseline; old depth-fitted outputs never initialize branches',
        subjects=history))
    audit_outputs(a.out, contract, contract['subjects'])
    # Check the frozen delivery/assets again after this read-only audit too.
    from types import SimpleNamespace
    from run_comparison import delivery_identity, runtime_assets
    frozen = load_json(a.out / 'RUN_FREEZE.json')
    args = SimpleNamespace(**{k: Path(v) for k, v in frozen['arguments'].items()})
    assert delivery_identity() == frozen['delivery_manifest_sha256']
    assert runtime_assets(args, contract) == frozen['assets']
    save_json(a.out / 'POST_AUDIT_INTEGRITY.json', dict(status='PASS',
        delivery_manifest_sha256=frozen['delivery_manifest_sha256'],
        runtime_assets_unchanged=True, cached_meshes_unchanged=True,
        read_only_audit_script_sha256=sha(Path(__file__))))
    print(json.dumps(dict(status=result['status'], rows=result['rows'])), flush=True)


if __name__ == '__main__':
    main()
