"""Cache-only engineering point diagnosis; no SAM inference or geometry fitting."""
import argparse, csv, datetime, hashlib, json, platform, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
CONTROL = REPO / 'docs/handoffs/real-scene-2026-10-04/controlled-back-reference-v1'
ATLAS_ROOT = REPO / 'docs/handoffs/real-scene-2026-10-03/back-geometry-correspondence-v2'
BODY = REPO / 'docs/handoffs/real-scene-2026-10-05/prone-body-query-workbench-v1'
REAL = REPO / 'docs/handoffs/real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2-execution/results'
PRE = REPO / 'docs/handoffs/real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2'
SITE = REPO / 'docs/handoffs/real-scene-2026-10-05/prone-reference-rule-workbench-v1'
METHODS = ['Official', 'Rigid', 'RigidD']


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save_csv(name, rows):
    with (ROOT / name).open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def summary(a):
    a = np.asarray(a)
    return dict(n=a.size, median=float(np.median(a)), p95=float(np.percentile(a, 95)), maximum=float(np.max(a)))


class Sources:
    """Record only files actually opened; compare existing reviewed hashes where available."""
    def __init__(self):
        self.rows = {}; self.expected = {}
        for root in [CONTROL, ATLAS_ROOT, BODY, PRE, SITE]:
            manifest = root / 'FILES_MANIFEST.json'
            if manifest.exists():
                x = read(manifest)
                for r in x.get('rows', x.get('files', [])):
                    self.expected[(root / r['path']).resolve()] = r['sha256']

    def add(self, p, expected=None):
        p = p.resolve()
        if p not in self.rows:
            digest = sha(p); frozen = expected or self.expected.get(p)
            if frozen is not None:
                assert digest == frozen, f'SOURCE_HASH_MISMATCH: {p}'
            self.rows[p] = dict(path=p.relative_to(REPO).as_posix(), bytes=p.stat().st_size,
                                sha256=digest, historical_hash_checked=frozen is not None)
        return p

    def load(self, p, expected=None):
        return dict(np.load(self.add(p, expected), allow_pickle=False))

    def json(self, p):
        return read(self.add(p))


def controlled(src, cfg, records):
    rows = []; per = []; points = []; refs = []; normals = []; refnormals = []
    max_old_difference = 0.
    for subject in cfg['subjects']:
        for case in cfg['cases']:
            folder = CONTROL / 'results' / subject / case
            old = {r['method']: r for r in src.json(folder / 'results.json')}
            fixed_reference = None
            for method in cfg['methods']:
                z = src.load(folder / (method + '_probes.npz'))
                p, ref, n, rn = [z[k] for k in ['xyz_m', 'reference_xyz_m', 'normals', 'reference_normals']]
                if fixed_reference is None: fixed_reference = ref
                np.testing.assert_array_equal(ref, fixed_reference)
                delta = (p - ref) * 1000; err = np.linalg.norm(delta, axis=1)
                signed = np.einsum('ij,ij->i', delta, rn)
                tangent = np.linalg.norm(delta - signed[:, None] * rn, axis=1)
                angle = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', n, rn), -1, 1)))
                max_old_difference = max(max_old_difference, float(np.max(np.abs(err - old[method]['probe_errors_mm']))))
                camera_medians = []; camera_p95 = []
                for k in [1, 2]:
                    a = src.load(folder / f'{method}_K{k}_metrics.npz')
                    idx = src.load(CONTROL / 'observation_indices' / subject / f'K{k}.npz')
                    np.testing.assert_array_equal(a['evaluation_point_idx'], idx['posterior_eval_idx'])
                    assert idx['optimization_idx'].size == 0
                    camera_medians.append(float(np.median(a['point_to_surface_m']) * 1000))
                    camera_p95.append(float(np.percentile(a['point_to_surface_m'], 95) * 1000))
                for j, r in enumerate(records):
                    rows.append(dict(subject=subject, role='dev' if subject in cfg['dev'] else 'consumed_test',
                        case=case, method=method, point_id=r['id'], face_id=r['face_id'],
                        error_mm=float(err[j]), signed_normal_error_mm=float(signed[j]),
                        tangent_error_mm=float(tangent[j]), normal_angle_deg=float(angle[j])))
                per.append(dict(subject=subject, role=rows[-1]['role'], case=case, method=method,
                    point_median_mm=float(np.median(err)), point_p95_mm=float(np.percentile(err, 95)),
                    point_max_mm=float(err.max()), normal_median_mm=float(np.median(np.abs(signed))),
                    tangent_median_mm=float(np.median(tangent)), surface_median_mm=float(np.median(camera_medians)),
                    surface_p95_mm=float(np.median(camera_p95))))
                points.append(p); refs.append(ref); normals.append(n); refnormals.append(rn)
    assert len(rows) == 1920 and len(per) == 240 and max_old_difference < 1e-9
    np.savez_compressed(ROOT / 'controlled_cache.npz', xyz_m=points, reference_xyz_m=refs,
                        normals=normals, reference_normals=refnormals)
    aggregates = []
    for role in ['dev', 'consumed_test']:
        for case in cfg['cases']:
            for method in cfg['methods']:
                p = [r for r in per if (r['role'], r['case'], r['method']) == (role, case, method)]
                e = [r['error_mm'] for r in rows if (r['role'], r['case'], r['method']) == (role, case, method)]
                aggregates.append(dict(role=role, case=case, method=method, subjects=len(p),
                    subject_equal_point_median_mm=float(np.median([r['point_median_mm'] for r in p])),
                    subject_median_p95_mm=float(np.percentile([r['point_median_mm'] for r in p], 95)),
                    pooled_point_p95_mm=float(np.percentile(e, 95)), pooled_point_max_mm=float(np.max(e)),
                    within_5mm_fraction=float(np.mean(np.asarray(e) <= 5)),
                    within_10mm_fraction=float(np.mean(np.asarray(e) <= 10)),
                    within_20mm_fraction=float(np.mean(np.asarray(e) <= 20)),
                    subject_equal_surface_median_mm=float(np.median([r['surface_median_mm'] for r in p]))))
    save_csv('CONTROLLED_POINTS.csv', rows); save_csv('CONTROLLED_PER_SUBJECT.csv', per)
    write('CONTROLLED_AGGREGATED.json', aggregates)
    return dict(point_records=len(rows), cache_groups=len(per), old_numeric_max_difference_mm=max_old_difference,
                error_recomputed_from_point_coordinates=True, error_recomputed_from_full_mesh=False), per


def real(src, cfg, records):
    subjects = cfg['subjects']; point_ids = [r['id'] for r in records]
    old = src.json(ATLAS_ROOT / 'results/a_atlas/PROPAGATED_2400_POINTS.json')
    lookup = {(r['subject'], r['seed'], r['method'], r['id']): r for r in old}
    targets = {(r['subject'], r['split_seed'], r['mesh_method']): r for r in src.json(BODY / 'TARGET_MANIFEST.json') if r['method'] == 'TOPOLOGY'}
    reviews = {(r['subject'], r['split_seed'], r['mesh_method']): r for r in src.json(BODY / 'MESH_REVIEW_MANIFEST.json')}
    move = {(r['subject'], r['seed'], r['id']): r for r in src.json(ATLAS_ROOT / 'results/c_pressure_normal/ENG_MOVEMENT_960.json') if r['method'] == 'Official+Rigid+D'}
    roi = {r['subject']: r for r in src.json(PRE / 'POSTERIOR_RGB_ROI.json')['entries']}
    points = np.zeros((20, 3, 3, 8, 3)); normals = points.copy(); triangles = np.zeros((20, 3, 2, 8, 3, 3))
    Ks = []; positions = []; changes = []; stability = []; per = []; binding_max = 0.; old_max = 0.
    faces = np.asarray([r['face_id'] for r in records]); bary = np.asarray([r['barycentric'] for r in records])
    for i, subject in enumerate(subjects):
        view = src.json(SITE / 'site/cases' / (subject + '.json')); K = np.asarray(view['K']); Ks.append(K)
        assert view['mesh_sha256'] == reviews[subject, 0, 'RigidD']['full_mesh_sha256']
        mask = Image.new('1', (view['image_width'], view['image_height']))
        ImageDraw.Draw(mask).polygon([tuple(p) for p in roi[subject]['polygon_xy_px']], fill=1)
        roi_mask = np.asarray(mask)
        for seed in cfg['seeds']:
            for k, method in enumerate(METHODS):
                historical = {'Official': 'Official', 'Rigid': 'Official+Rigid', 'RigidD': 'Official+Rigid+D'}[method]
                before = [lookup[subject, seed, historical, pid] for pid in point_ids]
                p = np.asarray([r['xyz_m'] for r in before]); n = np.asarray([r['normal'] for r in before])
                if method != 'Official':
                    tr = targets[subject, seed, method]; mr = reviews[subject, seed, method]
                    z = src.load(BODY / 'targets' / Path(tr['path']).name, tr['sha256'])
                    mesh = src.load(BODY / 'mesh_reviews' / Path(mr['path']).name, mr['sha256'])
                    np.testing.assert_array_equal(z['face_id'], faces); np.testing.assert_array_equal(z['barycentric'], bary)
                    local = np.searchsorted(mesh['global_face_id'], faces)
                    np.testing.assert_array_equal(mesh['global_face_id'][local], faces)
                    tri = mesh['triangles_m'][local]; p = np.sum(tri * bary[:, :, None], axis=1)
                    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None]
                    binding_max = max(binding_max, float(np.max(np.linalg.norm(p - z['xyz_m'], axis=1))) * 1000)
                    old_max = max(old_max, float(np.max(np.linalg.norm(p - np.asarray([r['xyz_m'] for r in before]), axis=1))) * 1000)
                    triangles[i, seed, k - 1] = tri
                points[i, seed, k] = p; normals[i, seed, k] = n
                uvh = p @ K.T; uv = uvh[:, :2] / uvh[:, 2:]
                for j, r in enumerate(records):
                    x, y = np.rint(uv[j]).astype(int); inside = p[j, 2] > 0 and 0 <= x < mask.width and 0 <= y < mask.height
                    nearest = move[subject, seed, r['id']] if method == 'RigidD' else None
                    positions.append(dict(subject=subject, role='dev' if subject in cfg['dev'] else 'consumed_test',
                        seed=seed, method=method, point_id=r['id'], face_id=r['face_id'],
                        x_m=float(p[j, 0]), y_m=float(p[j, 1]), z_m=float(p[j, 2]),
                        u_px=float(uv[j, 0]), v_px=float(uv[j, 1]), inside_rgb=bool(inside),
                        inside_back_roi=bool(inside and roi_mask[y, x]), visibility='NOT_VERIFIED',
                        nearest_train_mm=nearest['nearest_train_point_mm'] if nearest else None,
                        nearest_heldout_mm=nearest['nearest_posterior_heldout_point_mm'] if nearest else None,
                        binding_recomputed_from_triangles=method != 'Official', real_point_accuracy=False))
            delta = (points[i, seed, 2] - points[i, seed, 1]) * 1000
            rn = normals[i, seed, 1]; signed = np.sum(delta * rn, axis=1)
            uv = [(points[i, seed, k] @ K.T) for k in [1, 2]]
            uv = [x[:, :2] / x[:, 2:] for x in uv]
            for j, r in enumerate(records):
                changes.append(dict(subject=subject, role=positions[-1]['role'], seed=seed, point_id=r['id'],
                    total_movement_mm=float(np.linalg.norm(delta[j])), signed_normal_movement_mm=float(signed[j]),
                    tangent_movement_mm=float(np.linalg.norm(delta[j] - signed[j] * rn[j])),
                    image_movement_px=float(np.linalg.norm(uv[1][j] - uv[0][j]))))
        np.testing.assert_array_equal(points[i, 0, 0], points[i, 1, 0]); np.testing.assert_array_equal(points[i, 0, 0], points[i, 2, 0])
        for k, method in enumerate(METHODS):
            spans = np.max([np.linalg.norm(points[i, a, k] - points[i, b, k], axis=1) * 1000 for a, b in [(0, 1), (0, 2), (1, 2)]], axis=0)
            for j, pid in enumerate(point_ids):
                stability.append(dict(subject=subject, role=positions[-1]['role'], method=method, point_id=pid, max_pairwise_span_mm=float(spans[j])))
            per.append(dict(subject=subject, role=positions[-1]['role'], method=method,
                point_median_span_mm=float(np.median(spans)), point_max_span_mm=float(spans.max())))
    assert len(positions) == 1440 and len(changes) == 480 and len(stability) == 480
    assert binding_max < 1e-7 and old_max < 1e-7
    np.savez_compressed(ROOT / 'real_cache.npz', xyz_m=points, normals=normals, triangles_m=triangles, K=Ks, face_id=faces, barycentric=bary)
    save_csv('REAL_POSITIONS.csv', positions); save_csv('REAL_MOVEMENT.csv', changes)
    save_csv('REAL_STABILITY_POINTS.csv', stability); save_csv('REAL_STABILITY_PER_SUBJECT.csv', per)
    aggregates = []
    for role in ['dev', 'consumed_test']:
        for method in METHODS:
            q = [r for r in per if (r['role'], r['method']) == (role, method)]
            pp = [r for r in positions if (r['role'], r['method']) == (role, method)]
            aggregates.append(dict(role=role, method=method, subjects=len(q),
                subject_equal_span_median_mm=float(np.median([r['point_median_span_mm'] for r in q])),
                subject_span_p95_mm=float(np.percentile([r['point_median_span_mm'] for r in q], 95)),
                point_span_max_mm=float(np.max([r['point_max_span_mm'] for r in q])),
                inside_roi_fraction=float(np.mean([r['inside_back_roi'] for r in pp])), point_accuracy='NOT_MEASURED'))
    write('REAL_AGGREGATED.json', aggregates)
    return dict(position_records=len(positions), movement_records=len(changes), stability_records=len(stability),
                triangle_bindings_recomputed=960, official_positions_from_historical_cache=480,
                binding_max_difference_mm=binding_max, old_position_max_difference_mm=old_max,
                official_shared_initial_identical=True, visibility='NOT_VERIFIED', real_accuracy=False), per


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--cohort', choices=['dev', 'all'], default='all'); a = parser.parse_args()
    # Both stages retain the full fixed order; --cohort dev checks import/data paths before the full write.
    start = time.monotonic(); src = Sources(); cfg = src.json(CONTROL / 'CONTRACT.json')
    atlas = src.json(ATLAS_ROOT / 'results/a_atlas/ENGINEERING_BACK_ATLAS_V2.json'); records = atlas['records']
    native = REPO / 'output/prone_back_point_validation_v1/assets'
    V = np.load(src.add(native / 'mhr_rest_vertices.npy', atlas['source'][0]['sha256'])).astype(float) * .01
    F = np.load(src.add(native / 'mhr_faces.npy', atlas['source'][1]['sha256']))
    bary = np.asarray([r['barycentric'] for r in records]); ids = np.asarray([r['face_id'] for r in records]); tri = V[F[ids]]
    points = np.sum(tri * bary[:, :, None], axis=1)
    np.testing.assert_array_equal(F[ids], [r['vertex_ids'] for r in records])
    canonical_max = float(np.max(np.linalg.norm(points * 1000 - [r['canonical_xyz_mm'] for r in records], axis=1)))
    assert canonical_max < 1e-4
    np.savez_compressed(ROOT / 'canonical_cache.npz', triangles_m=tri, xyz_m=points, normals=np.asarray([r['canonical_normal'] for r in records]))
    write('FROZEN_POINTS.json', atlas)
    write('EXECUTION_CONFIG.json', dict(subjects=cfg['subjects'], dev=cfg['dev'], seeds=[0, 1, 2], controlled_cases=cfg['cases'],
        controlled_methods=cfg['methods'], real_methods=METHODS, point_ids=[r['id'] for r in records],
        aggregation='8-point median per subject -> role subject median; real span = max pairwise distance over 3 split seeds',
        historical_subjects_consumed=True, new_inferences=0, new_fits=0, new_training=0))
    if a.cohort == 'dev':
        # Targeted main-path check: known development S107 point cache and real face binding.
        z = src.load(CONTROL / 'results/S107/TANGENTIAL_SHIFT/D_VECTOR_probes.npz')
        r = next(r for r in src.json(BODY / 'MESH_REVIEW_MANIFEST.json') if (r['subject'], r['split_seed'], r['mesh_method']) == ('S107', 0, 'RigidD'))
        m = src.load(BODY / 'mesh_reviews' / Path(r['path']).name, r['sha256'])
        local = np.searchsorted(m['global_face_id'], ids); assert np.array_equal(m['global_face_id'][local], ids)
        print(json.dumps(dict(status='DEV_MAIN_PATH_PASS',canonical_max_difference_mm=canonical_max,controlled_points=len(z['xyz_m']),real_faces=len(local))))
        return
    controlled_check, _ = controlled(src, cfg, records); print('CONTROLLED_COMPLETE', controlled_check, flush=True)
    real_cfg = src.json(ATLAS_ROOT / 'results/c_pressure_normal/EXECUTION_CONTRACT.json')
    assert real_cfg['subjects'] == cfg['subjects'] and real_cfg['dev'] == cfg['dev']
    assert real_cfg['seeds'] == [0, 1, 2]
    real_check, _ = real(src, real_cfg, records); print('REAL_COMPLETE', real_check, flush=True)
    write('SOURCE_MANIFEST.json', dict(rows=list(src.rows.values()), historical_hash_checks=sum(r['historical_hash_checked'] for r in src.rows.values())))
    write('EXECUTION_LEDGER.json', dict(status='LOCAL_CACHE_DIAGNOSIS_COMPLETE_FULL_MESH_REPLAY_NOT_AVAILABLE',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), seconds=time.monotonic() - start,
        python=platform.python_version(), numpy=np.__version__, host=platform.node(), server_used=False,
        controlled=controlled_check, real=real_check, canonical_max_difference_mm=canonical_max,
        sources_opened=len(src.rows), new_inferences=0, new_fits=0, new_training=0,
        full_mesh_geometry_metrics_recomputed=False, medical_accuracy=False, robot_release=False))


if __name__ == '__main__':
    main()
