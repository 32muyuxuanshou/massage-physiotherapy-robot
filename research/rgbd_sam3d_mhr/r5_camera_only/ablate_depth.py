"""Fixed RGB/Body/rays/validity Depth value interventions, synthetic VAL only."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from camera_head import CameraHead
from train_camera import forward, sha


def statistics(z, rays, valid_fraction):
    xyz = np.column_stack((rays*z[:, None], z))
    q = np.quantile(z, [.1, .25, .5, .75, .9])
    return np.r_[q, xyz.mean(0), xyz.std(0), q[-1]-q[0], valid_fraction].astype('float32')


def run(a):
    torch.set_num_threads(2)
    rows = [r for r in json.loads((a.data/'MANIFEST.json').read_text())['records'] if r['role'] == 'VAL']
    loaded = []
    keys = ['rgb', 'metric', 'original_camera', 'K', 'bbox_center', 'bbox_scale', 'available']
    table = {k: [] for k in keys}
    for r in rows:
        with np.load(a.data/r['compact_file']) as z:
            values = {k:z[k] for k in z.files}
        loaded.append(values)
        for k in keys:
            table[k].append(values[k])
    original = {k:torch.as_tensor(np.stack(v)) for k,v in table.items()}
    gt = np.stack([v['truth_pred_cam_t'].reshape(3) for v in loaded])
    state = torch.load(a.checkpoint, map_location='cpu', weights_only=False)
    mode = state['execution_identity'].get('mode')
    mode = 'metric_xyz' if mode in ['mixed', 'native_only'] else mode
    model = CameraHead(state['head']['metric_mean'], state['head']['metric_std'], mode)
    model.load_state_dict(state['head']); model.eval()
    conditions = ['original_all_valid', 'sampled_control', 'absolute_flat', 'relative_fixed_reference',
                  'mask_rays_only', 'offset_-0.10', 'offset_0.10', 'local_shuffle',
                  'cross_identity', 'same_identity_other_pose', 'missing_depth']
    # Fixed reference is fitted on TRAIN only through the saved mean (Z median feature).
    reference_z = float(model.metric_mean[2])
    results = {}
    rng = np.random.default_rng(20261011)
    for condition in conditions:
        data = {k:v.clone() for k,v in original.items()}
        if condition == 'missing_depth':
            data['available'].zero_()
        elif condition != 'original_all_valid':
            for i, v in enumerate(loaded):
                z = v['measured_z'].copy(); rays = v['measured_rays']
                if condition == 'absolute_flat': z[:] = np.median(z)
                elif condition == 'relative_fixed_reference': z += reference_z-np.median(z)
                elif condition == 'mask_rays_only': z[:] = reference_z
                elif condition.startswith('offset_'): z += float(condition[7:])
                elif condition == 'local_shuffle':
                    # Consecutive groups in the preserved raster-order sample; not a 16px image patch.
                    for b in range(0,len(z),64): rng.shuffle(z[b:b+64])
                elif condition in ['cross_identity', 'same_identity_other_pose']:
                    donor = next(j for j,r in enumerate(rows) if
                                 (r['identity'] != rows[i]['identity'] if condition == 'cross_identity'
                                  else r['identity'] == rows[i]['identity'] and r['pose_id'] != rows[i]['pose_id']))
                    dz = loaded[donor]['measured_z']
                    z = np.interp(np.linspace(0,1,len(z)), np.linspace(0,1,len(dz)), dz).astype('float32')
                data['metric'][i,:13] = torch.from_numpy(statistics(z, rays, v['depth_valid_fraction']))
        with torch.no_grad():
            prediction = torch.cat([forward(model,data,np.arange(b,min(b+16,len(rows))),'cpu')
                                    for b in range(0,len(rows),16)]).numpy()
        if condition == 'original_all_valid': original_camera = prediction
        if condition == 'sampled_control': control = prediction
        if condition == 'missing_depth': assert np.array_equal(prediction,original['original_camera'].numpy())
        baseline = original_camera if condition in ['original_all_valid','sampled_control','missing_depth'] else control
        error = np.linalg.norm(prediction-gt,axis=1)*1000
        shift = (prediction-baseline)*1000
        results[condition] = dict(camera_mean_mm=float(error.mean()), camera_p95_mm=float(np.quantile(error,.95)),
                                  mean_response_xyz_mm=shift.mean(0).tolist(),
                                  mean_response_norm_mm=float(np.linalg.norm(shift,axis=1).mean()),
                                  records=[dict(file=r['compact_file'],identity=r['identity'],camera_xyz_m=c.tolist(),
                                                camera_error_mm=float(e),response_xyz_mm=s.tolist())
                                           for r,c,e,s in zip(rows,prediction,error,shift)],
                                  Body_change=0, Pose_change=0, Shape_change=0, Scale_change=0)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(dict(checkpoint_sha256=sha(a.checkpoint),conditions=results,
        TEST_read=False,camera_B_read=False,reference_Z_TRAIN_m=reference_z,
        contract='All valid input statistics compared separately to <=5000-pixel control; perturbations compared within identical sampled control',
        limitation='relative condition replaces absolute Z by a fixed TRAIN reference; XYZ remains ray-derived, so this is an intervention, not orthogonal factor separation'),indent=2))
    print('ABLATIONS_COMPLETE',a.checkpoint,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['data','checkpoint','out']:p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
