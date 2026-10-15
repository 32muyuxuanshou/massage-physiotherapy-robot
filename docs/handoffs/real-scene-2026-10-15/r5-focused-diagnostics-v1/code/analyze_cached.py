"""Same-Full Coarse/Fine diagnosis with frozen historical CPU evaluation.

No training, no new sampling, no fitting to held-out cameras. Each output is a
counterfactual translation of the existing Full Last body, never another model.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = None
FUNCTIONS = None
FACES = None
MAP_FACES = None
MAP_WEIGHTS = None
REGIONS = ['shoulder_upper_torso_proxy', 'middle_torso_proxy',
           'waist_lower_torso_proxy', 'arms', 'legs', 'head', 'hands_feet']


def initialize(root):
    global ROOT, FUNCTIONS, FACES, MAP_FACES, MAP_WEIGHTS
    ROOT = Path(root)
    code = ROOT / 'historical_code'
    sys.path.insert(0, str(code))
    from run_r41_txyz import dependencies
    FUNCTIONS = dependencies(code)
    FACES = np.load(ROOT / 'assets/faces.npy')
    with np.load(ROOT / 'assets/mhr2smpl_mapping.npz') as z:
        MAP_FACES = FACES[z['triangle_ids']]
        MAP_WEIGHTS = z['baryc_coords']


def load(name):
    with np.load(ROOT / name) as z:
        return {k: z[k] for k in z.files}


def summary(d):
    return dict(median_mm=float(np.median(d)), p95_mm=float(np.quantile(d, .95)),
                coverage_50mm=float(np.mean(d <= 50)))


def vertex_error(p, q):
    return float(np.linalg.norm(p - q, axis=-1).mean() * 1000)


def rigid_align(p, q):
    """Fixed-scale proper Kabsch: minimizes squared corresponding distances."""
    a, b = p - p.mean(0), q - q.mean(0)
    u, _, vt = np.linalg.svd(a.T @ b)
    signs = np.ones(3)
    signs[-1] = np.linalg.det(u @ vt)
    rotation = (u * signs) @ vt
    return a @ rotation + q.mean(0), rotation


def paired_reference(p, q):
    centered = p - p.mean(0) + q.mean(0)
    aligned, rotation = rigid_align(p, q)
    return dict(pve_mm=vertex_error(p, q), centered_pve_mm=vertex_error(centered, q),
                rigid_reference_pve_mm=vertex_error(aligned, q),
                rigid_reference_rotation_deg=float(np.rad2deg(np.arccos(np.clip((np.trace(rotation)-1)/2, -1, 1)))))


def evaluate_one(task):
    start = time.monotonic()
    z = load(task['prediction'])
    t = z['camera_m'].reshape(3).astype(np.float64)
    coarse = z['coarse_camera'].reshape(3).astype(np.float64)
    delta = z['fine_delta'].reshape(3).astype(np.float64)
    vf = z['vertices_camera_A'].reshape(-1, 3).astype(np.float64)
    vc = vf + (coarse - t)
    result = {k: task[k] for k in ['dataset', 'seed', 'key', 'identity', 'role']}
    result.update(coarse_camera_m=coarse.tolist(), final_camera_m=t.tolist(),
        fine_delta_mm=(delta*1000).tolist(), fine_norm_mm=float(np.linalg.norm(delta)*1000),
        fine_raw_delta_mm=(z['fine_raw_delta'].reshape(3)*1000).tolist(),
        eigenvalues=z['eigenvalues'].reshape(3).tolist(),
        visible_queries=int(z['visible_queries'].reshape(-1)[0]),
        camera_sum_max_abs_m=float(np.max(np.abs(t-coarse-delta))))
    assert result['camera_sum_max_abs_m'] < 1e-6
    same_body = (vf-vf.mean(0)) - (vc-vc.mean(0))
    assert np.max(np.abs(same_body)) < 1e-12
    old_errors = {}
    if task['dataset'] == 'native':
        gt = load(task['truth'])
        gtv = gt['pred_vertices'].reshape(-1, 3).astype(np.float64)
        gtt = gt['pred_cam_t'].reshape(3).astype(np.float64)
        target = gtv + gtt
        stages = {}
        for name, vertices, cam in [('coarse', vc, coarse), ('final', vf, t)]:
            stages[name] = dict(camera_mm=float(np.linalg.norm(cam-gtt)*1000),
                vertex_camera_mm=vertex_error(vertices, target),
                vertex_translation_removed_mm=vertex_error(vertices-vertices.mean(0), target-target.mean(0)))
        old = task['original_record']['metrics']
        old_errors = {k:abs(stages['final'][k]-old[k]) for k in stages['final']}
        # Native stored metrics used float32 GPU arithmetic; this is float64 CPU.
        assert max(old_errors.values()) < .002, old_errors
        need = gtt-coarse
        norm = np.linalg.norm(need)
        cosine = float(np.dot(delta, need)/(np.linalg.norm(delta)*norm)) if norm > 1e-9 and np.linalg.norm(delta)>1e-9 else None
        parallel = float(np.dot(delta, need)/norm) if norm > 1e-9 else None
        result['native_direction'] = dict(target_camera_m=gtt.tolist(),
            needed_delta_mm=(need*1000).tolist(), cosine_to_true_camera=cosine,
            parallel_mm=parallel*1000 if parallel is not None else None,
            parallel_fraction=parallel/norm if parallel is not None else None,
            orthogonal_mm=float(np.sqrt(max(0, np.dot(delta, delta)-parallel**2))*1000) if parallel is not None else None)
        # This is an offline fitted alignment, NOT replacement of MHR root params.
        result['reference_alignment'] = paired_reference(vf, target)
        official_t = z['original_camera'].reshape(3).astype(np.float64)
        result['official'] = dict(camera_mm=float(np.linalg.norm(official_t-gtt)*1000),
                                 vertex_camera_mm=vertex_error(vf+(official_t-t), target))
    else:
        result.update(sequence=task['sequence'], frame=task['frame'])
        source = load(task['input'])
        held = load(task['heldout'])
        stages = {}
        if task['dataset'] == 'real':
            ca = {k: source['A_'+k] for k in ['R','T']}
            cb = {k: source['B_'+k] for k in ['R','T']}
            vb = FUNCTIONS['transform_camera'](vc, ca, cb)
            points = held['points_camera_B']
            dc = FUNCTIONS['distance'](points, vb, FACES)*1000
            stages['coarse'] = summary(dc)
            old = task['original_final_evaluation']['triangle']
            stages['final'] = {k:old[k] for k in stages['coarse']}
            labels = load(task['regions'])['labels']
            result['coarse_regions'] = {name:summary(dc[labels==i]) for i,name in enumerate(REGIONS) if np.any(labels==i)}
            result['final_regions'] = task['original_final_evaluation']['regions']
            baseline = task['baseline']
            result['official'] = {k:baseline['triangle'][k] for k in stages['coarse']}
            result['official_txyz'] = {k:baseline['triangle_txyz'][k] for k in stages['coarse']}
            baseline_camera = z['original_camera'].reshape(3)+np.array(baseline['applied_translation_m'])
            result['txyz_fallback'] = baseline['fallback']
            if task.get('recheck_final'):
                df = FUNCTIONS['distance'](points, FUNCTIONS['transform_camera'](vf, ca, cb), FACES)*1000
                old_errors = {k:abs(summary(df)[k]-stages['final'][k]) for k in stages['final']}
                assert max(old_errors.values()) < 1e-6, old_errors
                result['recheck_final_distance_mm'] = df.tolist()
            result['coarse_distance_mm'] = dc.tolist()
        else:
            ref = load(task['reference'])['vertices_camera_m'].astype(np.float64)
            stages['coarse'] = paired_reference(np.einsum('nj,njk->nk', MAP_WEIGHTS, vc[MAP_FACES]), ref)
            stages['final'] = paired_reference(np.einsum('nj,njk->nk', MAP_WEIGHTS, vf[MAP_FACES]), ref)
            original = task['original_final_evaluation']
            old_errors['pve_mm'] = abs(stages['final']['pve_mm']-original['pve']['pve_absolute_mm'])
            assert old_errors['pve_mm'] < 1e-6
            per = {}
            for kid in [1,2,3]:
                target = (vc@source['K0_R'].T+source['K0_t']-held[f'K{kid}_t'])@held[f'K{kid}_R']
                dc = FUNCTIONS['distance'](held[f'K{kid}_points_m'], target, FACES)*1000
                per[f'K{kid}'] = summary(dc)
                if task.get('recheck_final'):
                    target = (vf@source['K0_R'].T+source['K0_t']-held[f'K{kid}_t'])@held[f'K{kid}_R']
                    df = FUNCTIONS['distance'](held[f'K{kid}_points_m'], target, FACES)*1000
                    old_errors.update({f'K{kid}_'+k:abs(summary(df)[k]-original['heldout_surface'][f'K{kid}'][k]) for k in summary(df)})
                    assert max(old_errors.values()) < 1e-6, old_errors
            for k in ['median_mm','p95_mm','coverage_50mm']:
                stages['coarse']['surface_'+k] = float(np.mean([v[k] for v in per.values()]))
                stages['final']['surface_'+k] = original['frame_surface_camera_equal_mean'][k]
            result['coarse_per_camera'] = per
            baseline = task['baseline']
            result['official_txyz'] = dict(pve_mm=baseline['pve']['pve_absolute_mm'],
                **{'surface_'+k:v for k,v in baseline['frame_surface_camera_equal_mean'].items()})
            baseline_camera = np.array(task['original_camera'])+np.array(baseline['txyz']['applied_m'])
            result['txyz_fallback'] = baseline['txyz']['fallback']
        result['final_minus_txyz_xyz_mm'] = ((t-baseline_camera)*1000).tolist()
        result['coarse_minus_txyz_xyz_mm'] = ((coarse-baseline_camera)*1000).tolist()
    result.update(stages=stages, final_reproduction_error=old_errors,
                  elapsed_seconds=time.monotonic()-start)
    return result


def save_result(out, task, result):
    result = dict(result)
    arrays = {k:result.pop(k) for k in ['coarse_distance_mm','recheck_final_distance_mm'] if k in result}
    if arrays:
        path = out / 'distances' / f"{task['dataset']}_s{task['seed']}" / (task['key']+'.npz')
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **arrays)
    path = out / 'records' / f"{task['dataset']}_s{task['seed']}" / (task['key']+'.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))


def main(a):
    manifest_path = a.geometry/'MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    tasks = manifest['tasks']
    # Fixed first frame in every dataset/seed plus named known failures. No metric selection.
    pilot = []
    for d in ['native','real','behave']:
        for seed in [11,23,37]:
            task = next(t for t in tasks if t['dataset']==d and t['seed']==seed)
            pilot.append(task)
    for identity in ['p001195','p001196']:
        pilot.append(next(t for t in tasks if t['dataset']=='real' and t['seed']==11 and t['identity']==identity))
    pilot_keys = {(t['dataset'],t['seed'],t['key']) for t in pilot}
    for task in tasks:
        task['recheck_final'] = (task['dataset'],task['seed'],task['key']) in pilot_keys
    selected = pilot if a.pilot else tasks
    a.out.mkdir(parents=True,exist_ok=True)
    contract = dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        existing_final_metrics='Retained after fixed pilot exact CPU reproduction; native float32/64 tolerance .002 mm',
        same_model=True, same_body=True, training=False, new_model_Txyz=False,
        gpu_timing='DEFERRED_BY_USER', sealed_native_humman_TEST_read=False)
    (a.out/'CONTRACT.json').write_text(json.dumps(contract,indent=2))
    todo = [t for t in selected if not (a.out/'records'/f"{t['dataset']}_s{t['seed']}"/(t['key']+'.json')).exists()]
    started=time.monotonic()
    with ProcessPoolExecutor(max_workers=a.workers, initializer=initialize, initargs=(str(a.geometry),)) as pool:
        for i,(task,result) in enumerate(zip(todo,pool.map(evaluate_one,todo)),1):
            save_result(a.out,task,result)
            if i%10==0 or i==len(todo):
                print('COMPLETE',i,len(todo),task['dataset'],task['seed'],round(time.monotonic()-started,1),flush=True)
    print('PILOT_COMPLETE' if a.pilot else 'Q1_COMPLETE',len(selected),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--geometry',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=6)
    p.add_argument('--pilot',action='store_true')
    main(p.parse_args())
