"""Repeat cached Official + frozen Txyz under R4's three random seeds.

This checks numerical repeatability, not three trained Official checkpoints or
fresh GPU model inference. Anchors and Camera A/B point indices remain fixed.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import time

from run_r41_txyz import dependencies, np, sha, summary

SEEDS = [11, 23, 37]


def array_sha(a):
    return hashlib.sha256(a.tobytes()).hexdigest()


def repeat(task):
    work, seed, ref = task
    random.seed(seed)
    np.random.seed(seed)
    work = Path(work)
    assets = work / 'assets'
    f = dependencies(work / 'code')
    key = ref['key']
    native_path = assets / 'original_assets/official' / (key + '.npz')
    assert sha(native_path) == ref['input_sha256']
    with np.load(native_path) as z, np.load(assets / 'original_assets/inputs' / (key + '.npz')) as data:
        vertices = z['vertices_camera_A']
        faces = np.load(assets / 'original_assets/official/faces.npy')
        with np.load(assets / 'runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz') as anchor:
            surface = (vertices[faces[anchor['face_index']]] * anchor['barycentric'][:, :, None]).sum(1)
        assert array_sha(data['source_indices']) == ref['source_indices_sha256']
        raw, applied, trace, fallback = f['fit_txyz'](data['points_camera_A'], surface)
        moved = vertices + applied
        camera = z['pred_cam_t'] + applied
        vb = f['transform_camera'](moved, {k: data['A_' + k] for k in ['R', 'T']},
                                   {k: data['B_' + k] for k in ['R', 'T']})
    # Only now is the independent Camera B evidence loaded; no B fitting.
    with np.load(assets / 'datasets/heldout/humman_r3_k1_v1' / (key + '.npz')) as points:
        distances = f['distance'](points['points_camera_B'], vb, faces) * 1000
    with np.load(work / 'corrected/official' / (key + '.npz')) as old:
        mesh_error = max(float(np.max(np.abs(a - old[k]))) for k, a in
                         [('vertices_camera_A', moved), ('vertices_camera_B', vb), ('pred_cam_t', camera)])
    with np.load(work / 'distances/official' / (key + '.npz')) as old:
        distance_error = float(np.max(np.abs(distances - old['after_mm'])))
    checks = dict(raw_translation_max_error_m=float(np.max(np.abs(raw - ref['raw_translation_m']))),
                  applied_translation_max_error_m=float(np.max(np.abs(applied - ref['applied_translation_m']))),
                  mesh_max_error_m=mesh_error, distance_max_error_mm=distance_error,
                  trace_equal=trace == ref['trace'], fallback_equal=fallback == ref['fallback'])
    assert all(checks[k] == 0 for k in checks if k.endswith(('_m', '_mm')))
    assert checks['trace_equal'] and checks['fallback_equal']
    return dict(seed=seed, **{k: ref[k] for k in ['key', 'identity', 'sequence', 'role', 'frame']},
                triangle=summary(distances), raw_translation_m=raw.tolist(), applied_translation_m=applied.tolist(),
                trace=trace, fallback=fallback, checks=checks,
                corrected_vertices_A_array_sha256=array_sha(moved),
                corrected_vertices_B_array_sha256=array_sha(vb),
                distances_mm_array_sha256=array_sha(distances))


def main(args):
    start = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=False)
    work = args.work
    paired = json.loads((work / 'PAIRED_RESULTS.json').read_text())
    refs = [r for r in paired['records'] if r['cell'] == 'official']
    assert len(refs) == 232 and {r['role'] for r in refs} == {'TRAIN', 'VAL'}
    config = json.loads((work / 'EXECUTION_CONFIG.json').read_text())
    for name, expected in config['source_sha256'].items():
        assert sha(work / 'code' / name) == expected
    anchor = work / 'assets/runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz'
    assert sha(anchor) == 'e227a6a1d20a4fd285b08f1dfdec06deae9d542f251c7a8ce6138aa34ee406da'
    tasks = [(str(work), seed, ref) for seed in SEEDS for ref in refs]
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(repeat, tasks):
            rows.append(row)
            if len(rows) % 116 == 0:
                print('OFFICIAL_SEED_CHECK', len(rows), '/', len(tasks), flush=True)
    f = dependencies(work / 'code')
    aggregates = {str(seed): {role: f['aggregate_real']([r for r in rows if r['seed'] == seed and r['role'] == role])
                              for role in ['TRAIN', 'VAL']} for seed in SEEDS}
    metrics = ['median_mm', 'p95_mm', 'coverage_50mm']
    assert all(aggregates[str(s)][role]['identity_equal_mean'] == paired['results']['official']['after'][role]['identity_equal_mean']
               for s in SEEDS for role in ['TRAIN', 'VAL'])
    variation = {role: {metric: dict(mean=float(np.mean([aggregates[str(s)][role]['identity_equal_mean'][metric] for s in SEEDS])),
                                   sample_sd=float(np.std([aggregates[str(s)][role]['identity_equal_mean'][metric] - aggregates['11'][role]['identity_equal_mean'][metric] for s in SEEDS], ddof=1)),
                                   max_minus_min=float(np.ptp([aggregates[str(s)][role]['identity_equal_mean'][metric] for s in SEEDS])))
                        for metric in metrics} for role in ['TRAIN', 'VAL']}
    report = dict(status='PASS', seeds=SEEDS, frames_per_seed=232, completed_evaluations=len(rows),
                  timestamp_utc=datetime.now(timezone.utc).isoformat(), seconds=time.monotonic() - start,
                  scope='Cached Official initial mesh -> frozen Txyz -> exact fixed Camera B evaluation.',
                  fresh_GPU_inference=False, independent_training_seeds=False, resampled_points=False,
                  test_read=False, camera_B_fitting=False, aggregation=config['aggregation'],
                  source_report_sha256=sha(work / 'PAIRED_RESULTS.json'), anchor_sha256=sha(anchor),
                  checker_sha256=sha(Path(__file__)), source_sha256=config['source_sha256'],
                  results=aggregates, variation=variation,
                  max_distance_difference_mm=max(r['checks']['distance_max_error_mm'] for r in rows),
                  max_mesh_difference_m=max(r['checks']['mesh_max_error_m'] for r in rows),
                  fallback_counts={str(s): {role: sum(r['fallback'] for r in rows if r['seed'] == s and r['role'] == role)
                                           for role in ['TRAIN', 'VAL']} for s in SEEDS})
    (args.out / 'SEED_REPEAT_RESULTS.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (args.out / 'PER_FRAME_SEED_CHECK.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    with (args.out / 'COMPARISON_BY_SEED.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['role', 'seed', 'method', 'seed_type', *metrics])
        writer.writeheader()
        for seed in SEEDS:
            for role in ['TRAIN', 'VAL']:
                writer.writerow(dict(role=role, seed=seed, method='official+txyz', seed_type='cached_algorithm_repeat',
                                     **aggregates[str(seed)][role]['identity_equal_mean']))
                for method in ['g0', 'g1']:
                    writer.writerow(dict(role=role, seed=seed, method=method+'+txyz', seed_type='trained_checkpoint',
                                         **paired['results'][f'{method}_seed{seed}']['after'][role]['identity_equal_mean']))
    print(json.dumps(dict(status=report['status'], seconds=report['seconds'], variation=variation)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=6)
    main(parser.parse_args())
