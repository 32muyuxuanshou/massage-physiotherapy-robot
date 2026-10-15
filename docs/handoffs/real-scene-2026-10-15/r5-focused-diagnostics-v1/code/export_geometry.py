"""Read existing Last outputs; export CPU geometry, never run a model or fit."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import time

import numpy as np

BASE = Path('/root/autodl-tmp/rgbd_sam3d')
R5 = BASE / 'runs/r5_complete_comparison_v1'
BEHAVE = BASE / 'evaluations/behave_model_comparison_v1'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(out):
    data = out / 'geometry'
    data.mkdir(parents=True, exist_ok=True)
    sources = {}

    def remember(path, expected=None):
        path = Path(path)
        key = str(path)
        if key not in sources:
            sources[key] = sha(path)
        if expected is not None:
            assert sources[key] == expected, ('SOURCE_HASH_MISMATCH', key)
        return sources[key]

    def read_json(path):
        remember(path)
        return json.loads(Path(path).read_text())

    def copy(path, name, expected=None):
        remember(path, expected)
        target = data / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(path, target)
        assert sha(target) == sources[str(Path(path))]
        return name

    def save(name, **arrays):
        target = data / name
        target.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(target, **arrays)
        return name

    def compact_prediction(path, expected, name, prefix=''):
        remember(path, expected)
        with np.load(path) as z:
            values = dict(body_m=z['pred_vertices'].reshape(-1, 3),
                          vertices_camera_A=z['vertices_camera_A'],
                          camera_m=z['pred_cam_t'].reshape(3),
                          global_rot=z['global_rot'].reshape(3))
            for key in ['coarse_camera', 'fine_delta', 'fine_raw_delta', 'eigenvalues', 'visible_queries']:
                values[key] = z[prefix + key]
            if 'original_camera' in z:
                values['original_camera'] = z['original_camera'].reshape(3)
        assert np.max(np.abs(values['camera_m'] - values['coarse_camera'].reshape(3)
                             - values['fine_delta'].reshape(3))) < 1e-6
        return save(name, **values)

    paths = read_json(R5 / 'PATHS.json')
    remember(__file__)
    history = R5 / 'assets/real_evaluation'
    faces = copy(paths['faces'], 'assets/faces.npy')
    copy(paths['anchors'], 'assets/anchors.npz')
    for name in ['surface_metrics.py', 'humman_geometry.py', 'diagnose_r31.py',
                 'evaluate_r3_humman.py', 'run_r41_txyz.py']:
        copy(history / 'code' / name, 'historical_code/' + name)
    copy(BASE / 'evaluations/behave_metric_alignment_v1/assets/mhr2smpl_mapping.npz',
         'assets/mhr2smpl_mapping.npz')

    native_manifest = read_json(Path(paths['native_cache']) / 'CACHE_MANIFEST.json')
    native_rows = {Path(r['cache_file']).stem: r for r in native_manifest['records'] if r['role'] == 'VAL'}
    assert len(native_rows) == 400
    truth = {}
    for i, (sample, row) in enumerate(native_rows.items()):
        source = BASE / 'datasets/synthetic/native_scale_v2' / row['file']
        remember(source, row['sha256'])
        with np.load(source) as z:
            keys = ['pred_vertices', 'pred_cam_t', 'global_rot', 'body_pose', 'shape', 'scale',
                    'hand', 'pred_joint_coords', 'R_world_to_camera', 'T_world_to_camera', 'root_pivot_shift_m']
            truth[sample] = save('native/truth/' + sample + '.npz', **{k: z[k] for k in keys})
        if i % 100 == 0:
            print('NATIVE_TRUTH', i, 400, flush=True)

    official_real = read_json(R5 / 'evaluation/official/real_B/RESULTS.json')
    copy(R5 / 'evaluation/official/real_B/RESULTS.json', 'metadata/official_real.json')
    official_by_key = {r['key']: r for r in official_real['records']}
    tasks = []
    for seed in [11, 23, 37]:
        for dataset in ['native', 'real']:
            report_path = R5 / f'evaluation/full_s{seed}_last' / dataset / 'RESULTS.json'
            report = read_json(report_path)
            assert len(report['records']) == (400 if dataset == 'native' else 232)
            for i, row in enumerate(report['records']):
                sample = row['sample_id']
                prediction = compact_prediction(row['prediction_file'], row['prediction_sha256'],
                    f'{dataset}/s{seed}/' + sample + '.npz')
                task = dict(dataset=dataset, seed=seed, key=sample, identity=row['identity'], role=row['role'],
                            prediction=prediction, original_record=row)
                if dataset == 'native':
                    assert row['role'] == 'VAL'
                    task['truth'] = truth[sample]
                else:
                    assert row['role'] in ['TRAIN', 'VAL']
                    task.update(sequence=row['sequence'], frame=row['frame'], baseline=official_by_key[sample])
                    task['input'] = copy(history / 'assets/original_assets/inputs' / (sample + '.npz'),
                                         'real/inputs/' + sample + '.npz')
                    task['heldout'] = copy(history / 'assets/datasets/heldout/humman_r3_k1_v1' / (sample + '.npz'),
                                           'real/heldout/' + sample + '.npz')
                    with np.load(data / task['heldout']) as z:
                        assert hashlib.sha256(z['points_camera_B'].tobytes()).hexdigest() == task['baseline']['B_points_sha256']
                    with np.load(data / task['input']) as z:
                        assert hashlib.sha256(z['source_indices'].tobytes()).hexdigest() == task['baseline']['A_indices_sha256']
                    task['regions'] = copy(history / 'regions' / (sample + '.npz'), 'real/regions/' + sample + '.npz')
                tasks.append(task)
                if i % 100 == 0:
                    print('PREDICTIONS', dataset, seed, i, len(report['records']), flush=True)
            if dataset == 'real':
                original = read_json(R5 / f'evaluation/full_s{seed}_last/real_B/RESULTS.json')
                by_key = {r['key']: r for r in original['records']}
                for task in tasks:
                    if task['dataset'] == 'real' and task['seed'] == seed:
                        task['original_final_evaluation'] = by_key[task['key']]

        prediction_manifest = read_json(BEHAVE / f'predictions/full_s{seed}_last/PREDICTION_MANIFEST.json')
        original = read_json(BEHAVE / f'evaluation/full_s{seed}_last/RESULTS.json')
        final_by_key = {(r['sequence'], r['frame']): r for r in original['records']}
        official_manifest = read_json(BEHAVE / f'cache/s{seed}/CACHE_MANIFEST.json')
        official_by_frame = {(r['sequence'], r['frame']): r for r in official_manifest['records']}
        baseline = read_json(BEHAVE / f'evaluation/official_s{seed}/RESULTS.json')
        txyz_by_key = {(r['sequence'], r['frame']): r for r in baseline['records'] if r['cell'].endswith('_txyz')}
        for i, row in enumerate(prediction_manifest['records']):
            key = row['sequence'] + '_' + row['frame']
            prediction = compact_prediction(row['prediction_file'], row['prediction_sha256'],
                                             f'behave/s{seed}/' + key + '.npz', prefix='trace_')
            remember(row['input_file'], row['input_sha256'])
            with np.load(row['input_file']) as z:
                compact_input = save('behave/inputs/' + key + '.npz',
                    **{k: z[k] for k in ['K0_points_m', 'K0_R', 'K0_t']})
            ref = copy(row['reference_file'], 'behave/references/' + key + '.npz', row['reference_sha256'])
            held = copy(row['heldout_file'], 'behave/heldout/' + key + '.npz', row['heldout_sha256'])
            off = official_by_frame[row['sequence'], row['frame']]
            remember(off['prediction_file'], off['prediction_sha256'])
            with np.load(off['prediction_file']) as z:
                official_camera = z['pred_cam_t'].reshape(3).tolist()
            tasks.append(dict(dataset='behave', seed=seed, key=key, identity=row['subject'], role=row['role'],
                sequence=row['sequence'], frame=row['frame'], prediction=prediction, input=compact_input,
                reference=ref, heldout=held, original_camera=official_camera,
                original_final_evaluation=final_by_key[row['sequence'], row['frame']],
                baseline=txyz_by_key[row['sequence'], row['frame']]))
            if i % 100 == 0:
                print('PREDICTIONS', 'behave', seed, i, 270, flush=True)

    assert len(tasks) == 2706
    manifest = dict(status='GEOMETRY_EXPORT_COMPLETE', tasks=tasks, source_sha256=sources, faces=faces,
                    training=False, sealed_native_or_humman_TEST_read=False,
                    behave_scope='Previously consumed fixed 270-frame official TEST subset',
                    array_policy='Existing meter coordinates/dtypes preserved; no new resampling or alignment',
                    files=[dict(path=p.relative_to(data).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
                           for p in sorted(data.rglob('*')) if p.is_file() and p.name != 'MANIFEST.json'])
    (data / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2))
    archive = out / 'R5_FOCUSED_GEOMETRY.tar'
    with tarfile.open(archive, 'w') as tar:
        tar.add(data, arcname='geometry')
    receipt = dict(status='PASS', path=str(archive), bytes=archive.stat().st_size, sha256=sha(archive),
                   tasks=len(tasks), created_unix=time.time())
    (out / 'EXPORT_RECEIPT.json').write_text(json.dumps(receipt, indent=2))
    print('EXPORT_COMPLETE', json.dumps(receipt), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
