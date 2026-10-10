"""Small positive-path Camera-only QA plus exact bounded-head capacity audit."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from camera_head import CameraHead, apply_camera
from train_camera import load_table, forward


def run(data, out, device):
    rows, table, target = load_table(data)
    train = np.asarray([i for i, r in enumerate(rows) if r['role']=='TRAIN'])
    val = np.asarray([i for i, r in enumerate(rows) if r['role']=='VAL'])
    assert (len(train), len(val)) == (3200, 400)
    mean = table['metric'][train].mean(0)
    std = table['metric'][train].std(0, unbiased=False)
    results = {}
    for mode in ['raw_bounded', 'metric_xyz', 'rgb_only_xyz']:
        torch.manual_seed(11)
        model = CameraHead(mean, std, mode).to(device)
        initial = forward(model, table, train[:16], device)
        err = float((initial-table['original_camera'][train[:16]].to(device)).abs().max())
        assert err < 2e-6
        loss = F.smooth_l1_loss(initial, target[train[:16]].to(device), beta=.05)
        loss.backward()
        grad = float(model.output[-1].weight.grad.norm())
        assert grad > 0 and np.isfinite(grad)
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)
        optimizer.step()
        after = forward(model, table, train[:16], device)
        absent = dict(table, available=torch.zeros_like(table['available']))
        missing = forward(model, absent, train[:16], device)
        assert torch.equal(missing, table['original_camera'][train[:16]].to(device))
        with np.load(data/rows[train[0]]['compact_file']) as z:
            body = {k.removeprefix('official_'): torch.as_tensor(z[k]).to(device)
                    for k in z.files if k.startswith('official_')}
            changed = apply_camera(body, after[:1])
            invariant = {k: torch.equal(changed[k], body[k]) for k in
                         ['pred_vertices', 'global_rot', 'body_pose', 'shape', 'scale', 'hand']}
        assert all(invariant.values())
        results[mode] = dict(zero_initialization_error_m=err, nonzero_target_gradient=grad,
                             camera_changed_after_step_m=float((after-initial).norm(dim=1).mean()),
                             body_exact_equal=invariant, missing_depth_exact_Official=True)
    c = table['original_camera'].numpy()
    t = target.numpy()
    K, center = table['K'].numpy(), table['bbox_center'].numpy()
    offset0 = (center-K[:, :2, 2])*c[:, 2:]/K[:, 0, 0, None]
    offsetgt = (center-K[:, :2, 2])*t[:, 2:]/K[:, 0, 0, None]
    raw0 = np.column_stack((c[:, 0]-offset0[:, 0], -c[:, 1]+offset0[:, 1]))
    rawgt = np.column_stack((t[:, 0]-offsetgt[:, 0], -t[:, 1]+offsetgt[:, 1]))
    need = np.column_stack((-2*np.log(t[:, 2]/c[:, 2]), (rawgt-raw0)/.15))
    assert np.isfinite(need).all()
    capacity = {role: dict(samples=len(indices), outside_bound=int((np.abs(need[indices])>1).any(1).sum()),
                           per_axis_outside_bound=(np.abs(need[indices])>1).sum(0).tolist(),
                           gt_Z_range_m=[float(t[indices, 2].min()), float(t[indices, 2].max())])
                for role, indices in [('TRAIN', train), ('VAL', val)]}
    report = dict(status='PASS', camera_only_QA=results, raw_bounded_capacity=capacity,
                  train_identities=len({rows[i]['identity'] for i in train}),
                  val_identities=len({rows[i]['identity'] for i in val}),
                  device=device, test_read=False, camera_B_read=False,
                  raw_capacity_note='A capacity diagnosis, not checkpoint selection or evidence of training superiority')
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--device', default='cuda')
    a = p.parse_args()
    run(a.data, a.out, a.device)
