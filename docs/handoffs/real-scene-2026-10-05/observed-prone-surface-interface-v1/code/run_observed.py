"""Actual author point cloud -> frozen V2 -> cached MHR surface/rules.

No new SAM inference, fitting, training, or clinical accuracy experiment.
Raw inputs stay in the private output directory; public caches contain predicted
mesh/fields and source indices, not the author's point cloud or RGB.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
FROZEN_DATA = REPO/'docs/handoffs/real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2'
PREVIOUS_EXECUTION = FROZEN_DATA.with_name(FROZEN_DATA.name+'-execution')
MODEL = ROOT.parent/'reference-anchored-surface-field-v2'
WORKBENCH = ROOT.parent/'prone-reference-rule-workbench-v1'
sys.path[:0] = [str(FROZEN_DATA/'code'), str(MODEL/'code'), str(WORKBENCH/'code')]
from data_v2 import prepare_subject, sha, array_sha, load_json, save_json
from anchored_field import AnchoredField
from patient_interface import infer_patient, frame_and_references
from reference_frame import to_local
from check_pipeline import fixture, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--subject', default='S107')
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--private-output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    args.raw = args.raw.resolve(); args.checkpoint = args.checkpoint.resolve()
    args.private_output = args.private_output.resolve()
    start = time.time(); torch.set_num_threads(4)
    contract = load_json(ROOT/'INTERFACE_CONTRACT.json')
    assert args.seed == 0, 'CURRENT_PUBLIC_MESH_IS_RIGIDD_SEED0'
    assert sha(args.checkpoint) == contract['checkpoint_sha256']
    mesh_path = WORKBENCH/'site/cases'/(args.subject+'.json')
    mesh = load_json(mesh_path)
    before = {str(p.relative_to(REPO)): sha(p) for p in [
        mesh_path, FROZEN_DATA/'CALIBRATION_INPUT.json',
        FROZEN_DATA/'POSTERIOR_RGB_ROI.json', MODEL/'code/patient_interface.py',
        MODEL/'code/anchored_field.py', MODEL/'code/frozen_point_field.py']}
    input_dir = args.private_output/'inputs'/args.subject
    qa = prepare_subject(args.raw, args.subject, FROZEN_DATA, input_dir)
    previous = load_json(PREVIOUS_EXECUTION/'results/inputs'/args.subject/'input_manifest.json')
    for key in ['source_sha256','rgb_array_sha256','depth_array_sha256','points_array_sha256']:
        assert qa[key] == previous[key], 'FROZEN_INPUT_ARRAY_CHANGED '+key
    with np.load(input_dir/'input.npz') as z:
        points = z['points_m']; back = z['posterior_point_mask']; K = z['K']
    with np.load(input_dir/'split_0.npz') as z:
        split = {k:z[k] for k in z.files}
    split_path = PREVIOUS_EXECUTION/'results/inputs'/args.subject/'split_0.npz'
    with np.load(split_path) as z:
        for key in z.files: assert np.array_equal(split[key], z[key]), 'FROZEN_SPLIT_CHANGED '+key
    assert np.array_equal(K, np.asarray(mesh['K'], np.float32)), 'MESH_POINT_CAMERA_MISMATCH'
    refs = {k:v for k,v in fixture(mesh).items() if k in ['T3','L2','LEFT_REF','RIGHT_REF']}
    vertices = np.asarray(mesh['vertices_m']); faces = np.asarray(mesh['faces'])
    frame, _ = frame_and_references(mesh, refs, [0.,0.,0.])
    local_points = to_local(points, frame)
    along = local_points[:,2]*500./frame['reference_length_mm']
    roi = back & (along >= -.4) & (along <= 1.4) & (abs(local_points[:,0]*500.) <= 150.)
    available = split['train_idx'][roi[split['train_idx']]]
    n = contract['observed_points']
    rng = np.random.default_rng(int(hashlib.sha256(args.subject.encode()).hexdigest()[:8],16))
    selected = rng.choice(available, n, replace=False)
    assert np.intersect1d(selected,split['heldout_idx']).size == 0
    # Same observed count/model/mesh/references for the input-origin comparison.
    # Sampling identities differ; this is not a clinical domain-shift experiment.
    mesh_indices = rng.choice(len(vertices), n, replace=False)
    model = AnchoredField()
    model.load_state_dict(torch.load(args.checkpoint, map_location='cpu', weights_only=True)); model.eval()
    records = []
    output = ROOT/'results'/args.subject; output.mkdir(parents=True,exist_ok=True)
    for name, observed in [('MESH_SAMPLED_FIXTURE',vertices[mesh_indices]),
                           ('AUTHOR_FILTERED_OBSERVED_PC',points[selected])]:
        result = infer_patient(mesh, observed, refs, [0.,0.,0.], model)
        binding_error = verify(mesh,result['rules'])
        cache = output/(name+'.npz')
        np.savez_compressed(cache,vertices_m=vertices,faces=faces,global_face_ids=mesh['global_face_ids'],
            local_query=to_local(vertices,frame),learned_field=result.pop('learned_field'),
            ray_delta_mm=result.pop('ray_delta_mm'),observed_indices=selected if name.startswith('AUTHOR') else mesh_indices)
        result.update(subject=args.subject,observation_origin=name,observed_n=n,
            checkpoint_sha256=sha(args.checkpoint),mesh_sha256=mesh['mesh_sha256'],
            public_mesh_payload_sha256=sha(mesh_path),cache_sha256=sha(cache),
            reference_origin='GEOMETRY_FIXTURES_NOT_INDEPENDENT_ANATOMICAL_REFERENCES',
            max_rule_binding_error_m=binding_error)
        save_json(output/(name+'.json'),result); records.append(result)
    actual, fixture_result = records[1], records[0]
    movement = {k:float(np.linalg.norm(np.asarray(v['xyz_m'])-
        fixture_result['suggestions'][k]['xyz_m'])*1000) for k,v in actual['suggestions'].items()}
    with np.load(output/'AUTHOR_FILTERED_OBSERVED_PC.npz') as z:
        raw_delta = z['ray_delta_mm']; actual_field = z['learned_field']
    with np.load(output/'MESH_SAMPLED_FIXTURE.npz') as z:
        field_difference = np.linalg.norm(actual_field-z['learned_field'],axis=1)
    after = {p:sha(REPO/p) for p in before}
    assert before == after, 'FROZEN_INPUT_OR_MODEL_CHANGED'
    assert sha(args.checkpoint) == contract['checkpoint_sha256'], 'CHECKPOINT_CHANGED_DURING_RUN'
    report = dict(status='ACTUAL_OBSERVED_POINT_INTERFACE_PASS_NOT_ACCURACY_VALIDATION',
        subject=args.subject,coordinate_frame='historical reconstructed camera_m',
        checkpoint_sha256=contract['checkpoint_sha256'],
        camera_status=qa['camera_status'],raw_input_sha256=qa['source_sha256'],
        raw_points_n=len(points),posterior_roi_points_n=int(roi.sum()),eligible_train_points_n=len(available),
        observed_points=n,observed_source_indices=selected.tolist(),train_heldout_intersection=0,
        historical_split_indices_identical=True,historical_input_arrays_identical=True,
        original_split_file_sha256=sha(split_path),reconstructed_input_manifest=qa,
        output_cache_files=[dict(path=p.name,sha256=sha(p)) for p in sorted(output.glob('*.npz'))],
        suggestion_input_change_mm=movement,field_change_norm_median=float(np.median(field_difference)),
        raw_ray_delta_median_mm=float(np.median(raw_delta)),raw_ray_delta_abs_p95_mm=float(np.percentile(abs(raw_delta),95)),
        suggestions=6,rules=16,reference_count=4,geometry_correction_applied=False,
        fresh_model_training=False,fresh_sam_inference=False,fresh_mesh_fit=False,
        clinical_accuracy_evaluated=False,robot_release=False,
        max_rule_binding_error_m=max(r['max_rule_binding_error_m'] for r in records),
        interpretation='One consumed subject; source-input/interface comparison, not efficacy. '
            'Filtered author cloud is real observation; camera remains approximate; references remain fixtures.',
        seconds=time.time()-start,environment=dict(python=sys.version,torch=torch.__version__,numpy=np.__version__,device='cpu'),
        dependencies_before=before,dependencies_after=after)
    save_json(output/'EXECUTION_RESULT.json',report)
    print(json.dumps({k:report[k] for k in ['status','observed_points','eligible_train_points_n',
        'suggestion_input_change_mm','raw_ray_delta_abs_p95_mm','seconds']}),flush=True)


if __name__ == '__main__': main()
