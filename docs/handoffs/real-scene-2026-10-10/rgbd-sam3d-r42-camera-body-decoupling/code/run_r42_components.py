"""R4.2 full-development mechanical Camera/Body exchanges; Camera A fit only."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time
from run_r41_txyz import dependencies, np, sha, summary, regional, summarize

SEEDS = [11, 23, 37]
PARAMS = ['global_rot', 'body_pose', 'shape', 'scale']


def one(task):
    source, out, seed, kind, ref, gref = task
    source, out = Path(source), Path(out)
    assets = source / 'assets'
    f = dependencies(source / 'code')
    key = ref['key']
    op = assets / 'original_assets/official' / (key + '.npz')
    gp = assets / f'r4/formal/g1_seed{seed}/real' / (key + '.npz')
    assert sha(op) == ref['input_sha256'] and sha(gp) == gref['input_sha256']
    o, g = np.load(op), np.load(gp)
    body, camera = (o, g) if kind == 'official_body_g1_camera' else (g, o)
    cell = f'{kind}_seed{seed}'
    vertices = body['vertices_camera_A'] + (camera['pred_cam_t'] - body['pred_cam_t']).reshape(3)
    params = {k: body[k] for k in PARAMS}
    body_error = float(np.max(np.abs((vertices.astype(np.float64) - camera['pred_cam_t'].reshape(3)) -
                                     (body['vertices_camera_A'].astype(np.float64) - body['pred_cam_t'].reshape(3)))))
    assert body_error < 1e-6  # float32 translated-vertex rounding, no body deformation
    with np.load(assets / 'original_assets/inputs' / (key + '.npz')) as a:
        faces = np.load(assets / 'original_assets/official/faces.npy')
        anchor = np.load(assets / 'runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz')
        surface = (vertices[faces[anchor['face_index']]] * anchor['barycentric'][:, :, None]).sum(1)
        raw, applied, trace, fallback = f['fit_txyz'](a['points_camera_A'], surface)
        ca, cb = ({k: a['A_' + k] for k in ['R', 'T']}, {k: a['B_' + k] for k in ['R', 'T']})
        before_b = f['transform_camera'](vertices, ca, cb)
        moved = vertices + applied
        after_b = f['transform_camera'](moved, ca, cb)
    for stage, va, vb, cam in [('raw', vertices, before_b, camera['pred_cam_t']),
                               ('corrected', moved, after_b, camera['pred_cam_t'] + applied)]:
        p = out / stage / cell / (key + '.npz')
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(p, vertices_camera_A=va, vertices_camera_B=vb, pred_cam_t=cam,
                            raw_translation_m=raw, applied_translation_m=applied, **params)
        with np.load(p) as saved:
            assert all(np.array_equal(saved[k], body[k]) for k in PARAMS)
    # Camera B observations enter only after both outputs are fully determined.
    with np.load(assets / 'datasets/heldout/humman_r3_k1_v1' / (key + '.npz')) as b:
        before = f['distance'](b['points_camera_B'], before_b, faces) * 1000
        after = f['distance'](b['points_camera_B'], after_b, faces) * 1000
    with np.load(source / 'regions' / (key + '.npz')) as r:
        labels = r['labels']
    p = out / 'distances' / cell / (key + '.npz')
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, before_mm=before, after_mm=after)
    return dict(**{k: ref[k] for k in ['key', 'identity', 'sequence', 'frame', 'role']}, cell=cell, seed=seed,
                body_source='official' if kind.startswith('official') else f'g1_seed{seed}',
                camera_source=f'g1_seed{seed}' if kind.startswith('official') else 'official',
                body_parameter_arrays_exact=True, body_relative_vertex_roundoff_max_m=body_error,
                triangle_before=summary(before), triangle_after=summary(after),
                regions_before=regional(before, labels), regions_after=regional(after, labels),
                raw_translation_m=raw.tolist(), applied_translation_m=applied.tolist(), trace=trace, fallback=fallback,
                raw_norm_mm=float(np.linalg.norm(raw)*1000), applied_norm_mm=float(np.linalg.norm(applied)*1000),
                original_official_fallback=ref['fallback'], camera_delta_from_official_mm=((camera['pred_cam_t']-o['pred_cam_t'])*1000).reshape(3).tolist())


def controls(source):
    assets = source / 'assets'
    f = dependencies(source / 'code')
    faces = np.load(assets / 'original_assets/official/faces.npy')
    anchor = np.load(assets / 'runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz')
    refs = [r for r in json.loads((source / 'PAIRED_RESULTS.json').read_text())['records'] if r['cell']=='official']
    selected = [refs[0], next(r for r in refs if r['fallback']), next(r for r in refs if r['identity']=='p001196'), refs[-1]]
    checks = []
    for ref in selected:
        key = ref['key']
        z = np.load(assets / 'original_assets/official' / (key+'.npz'))
        identity = z['vertices_camera_A'] + (z['pred_cam_t']-z['pred_cam_t']).reshape(3)
        assert np.array_equal(identity, z['vertices_camera_A'])
        a = np.load(assets / 'original_assets/inputs' / (key+'.npz'))
        anchors = (identity[faces[anchor['face_index']]]*anchor['barycentric'][:,:,None]).sum(1)
        raw, applied, trace, fallback = f['fit_txyz'](a['points_camera_A'], anchors)
        assert np.array_equal(raw,ref['raw_translation_m']) and np.array_equal(applied,ref['applied_translation_m'])
        assert trace==ref['trace'] and fallback==ref['fallback']
        checks.append(dict(key=key,status='PASS',identity_exchange_exact=True,historical_txyz_trace_exact=True))
    return checks


def main(a):
    start = time.monotonic()
    a.out.mkdir(parents=True, exist_ok=False)
    old = json.loads((a.source/'PAIRED_RESULTS.json').read_text())
    refs = [r for r in old['records'] if r['cell']=='official']
    assert len(refs)==232 and all(r['role'] in ['TRAIN','VAL'] for r in refs)
    lookup = {(r['cell'],r['key']):r for r in old['records']}
    freeze = dict(stage='R4.2_COMPONENT_DIAGNOSTIC',source_commit='852a9bcf',frames=232,seeds=SEEDS,
        source_paired_sha256=sha(a.source/'PAIRED_RESULTS.json'),
        frame_contract_sha256=sha(a.source/'FRAME_CONTRACT.json'),
        anchor_sha256=sha(a.source/'assets/runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz'),
        checker_sha256=sha(Path(__file__)),test_read=False,camera_B_fitting=False,
        numerical_source_sha256=json.loads((a.source/'EXECUTION_CONFIG.json').read_text())['source_sha256'],
        body_invariant='native global_rot/body_pose/shape/scale exact; relative vertices within float32 rounding',
        methods=['official','g1']+['official_body_g1_camera','g1_body_official_camera'],
        stages=['before','after'],txyz='unchanged frozen R3.1/R4.1',
        interpretation='Full cached mechanical decomposition, not a final trainable model or causal training attribution.')
    for name,expected in freeze['numerical_source_sha256'].items():
        assert sha(a.source/'code'/name)==expected
    (a.out/'EXECUTION_CONFIG.json').write_text(json.dumps(freeze,indent=2))
    (a.out/'SMALL_CONTROLS.json').write_text(json.dumps(controls(a.source),indent=2))
    tasks = [(str(a.source),str(a.out),s,kind,ref,lookup[f'g1_seed{s}',ref['key']])
             for s in SEEDS for kind in ['official_body_g1_camera','g1_body_official_camera'] for ref in refs]
    rows = []
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for row in pool.map(one,tasks):
            rows.append(row)
            if len(rows)%116==0:print('COMPONENTS',len(rows),'/',len(tasks),flush=True)
    (a.out/'COMPONENT_RECORDS.json').write_text(json.dumps(rows,indent=2))
    baseline = [r for r in old['records'] if r['cell'] in ['official',*[f'g1_seed{s}' for s in SEEDS]]]
    report = summarize(baseline+rows,dependencies(a.source/'code'))
    report.update(stage='R4.2',cached_mechanical_exchange=True,new_gpu_inference=False,seconds=time.monotonic()-start,
                  new_exchange_evaluations=len(rows)*2,baseline_evaluations_reused=len(baseline)*2)
    (a.out/'PAIRED_RESULTS.json').write_text(json.dumps(report,indent=2))
    print('R42_COMPONENTS_COMPLETE',report['seconds'],flush=True)
    for cell in ['official',*[f'official_body_g1_camera_seed{s}' for s in SEEDS],*[f'g1_body_official_camera_seed{s}' for s in SEEDS]]:
        print(cell,{role:report['results'][cell]['after'][role]['identity_equal_mean'] for role in ['TRAIN','VAL']},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=6)
    main(p.parse_args())
