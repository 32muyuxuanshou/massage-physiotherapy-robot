"""Exposure-matched native-only versus scan weak continuation, fixed Body."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np
import torch
from torch.nn import functional as F
from camera_head import CameraHead
from train_camera import load_table, forward, camera_summary, native_geometry, sha
from scan_render import ScanTable, output_gradient, renderer_qa


def restore(path, device):
    state = torch.load(path, map_location='cpu', weights_only=False)
    model = CameraHead(state['head']['metric_mean'], state['head']['metric_std'], 'metric_xyz').to(device)
    model.load_state_dict(state['head'])
    return model, state


def calibrate(a):
    torch.set_num_threads(2)
    rows, data, target = load_table(a.root/'assets/compact_native')
    train = np.asarray([i for i, r in enumerate(rows) if r['role'] == 'TRAIN'])
    rng = np.random.default_rng(20261011)
    index = rng.choice(train, 32, replace=False)
    scan = ScanTable(a.root/'assets/compact_scan', a.scan_source, a.anchors)
    si = scan.sample(rng, 32)
    model, _ = restore(a.root/'native/metric_xyz_s11/last.pt', 'cuda')
    model.eval()
    with torch.no_grad():
        camera = forward(model, data, index, 'cuda')
        scamera = forward(model, scan.data, si, 'cuda')
    qa = renderer_qa()
    leaf = camera.detach().clone().requires_grad_(True)
    native_loss = F.smooth_l1_loss(leaf, target[index].cuda(), beta=.05, reduction='none').mean(1)
    gn = np.linalg.norm(output_gradient(leaf, native_loss), axis=1)
    depth_grads, silhouette_grads, hits = [], [], []
    for b in range(0, len(si), 4):
        leaf = scamera[b:b+4].detach().clone().requires_grad_(True)
        lz, ls, hit = scan.components(leaf, si[b:b+4])
        depth_grads.extend(np.linalg.norm(output_gradient(leaf, lz),axis=1))
        silhouette_grads.extend(np.linalg.norm(output_gradient(leaf, ls),axis=1))
        hits.extend(hit.detach().cpu().tolist())
    weights = dict(depth=float(np.median(gn)/np.median(depth_grads)),
                   silhouette=float(np.median(gn)/np.median(silhouette_grads)))
    assert all(np.isfinite(v) and v>0 for v in weights.values())
    model.train()
    model.zero_grad(set_to_none=True)
    loss = scan.loss(forward(model, scan.data, si[:4], 'cuda'), si[:4], weights)
    loss.backward()
    gradient = float(model.output[-1].weight.grad.norm())
    assert np.isfinite(gradient) and gradient > 0
    config = dict(status='PASS', native_gradient_norms=gn.tolist(), render_depth_gradient_norms=list(map(float,depth_grads)),
                  silhouette_gradient_norms=list(map(float,silhouette_grads)),
                  weak_weights=weights, renderer_QA=qa, calibration_hit_rates=hits,
                  formula='median per-sample native Camera gradient / median per-sample geometric gradient, separately for Z and silhouette',
                  native_rows=[rows[i]['compact_file'] for i in index],
                  scan_rows=[scan.rows[i]['sample_id'] for i in si],
                  renderer_resolution=[480,640], weak_batch=4, per_image_reduction=True,
                  native_batch=16, native_beta_m=.05, weak_beta_m=.02, seed=20261011,
                  scan_parameter_gradient=gradient,
                  weak_loss='full clean person-mask axial Z SmoothL1 including missing hits + per-image antialiased silhouette IoU',
                  input_depth='registered noisy depth; target depth is clean synthetic scan render',
                  label_scope='clothed visible scan surface, not MHR root or anatomical correspondence',
                  sampler='identity -> source mesh -> camera factor group -> configuration, equal conditional draw',
                  native_manifest_sha256=sha(a.root/'assets/compact_native/MANIFEST.json'),
                  scan_manifest_sha256=sha(a.root/'assets/compact_scan/MANIFEST.json'),
                  renderer_sha256=sha(Path(__file__).parent/'render_losses.py'), teacher_checkpoint_sha256=sha(a.root/'native/metric_xyz_s11/last.pt'),
                  code_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},
                  TEST_read=False, VAL_calibration=False, camera_B_read=False)
    (a.root/'WEAK_SUPERVISION_FREEZE.json').write_text(json.dumps(config, indent=2))
    print('WEAK_QA_PASS', weights, gradient, flush=True)


def train(a):
    torch.set_num_threads(2)
    freeze = json.loads((a.root/'WEAK_SUPERVISION_FREEZE.json').read_text())
    assert freeze['status'] == 'PASS'
    native = a.root/'assets/compact_native'
    rows, data, target = load_table(native)
    ti = np.asarray([i for i, r in enumerate(rows) if r['role'] == 'TRAIN'])
    vi = np.asarray([i for i, r in enumerate(rows) if r['role'] == 'VAL'])
    scan = ScanTable(a.root/'assets/compact_scan', a.scan_source, a.anchors) if a.mode == 'mixed' else None
    parent = a.root/f'native/metric_xyz_s{a.seed}/last.pt'
    model, state = restore(parent, 'cuda')
    # Both arms restore identical optimizer/shuffle state and use the same new 20-epoch schedule.
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    optimizer.load_state_dict(state['optimizer'])
    for group in optimizer.param_groups:
        group['lr'] = 3e-4
        group['initial_lr'] = 3e-4
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda e: .1+.9*(1+math.cos(math.pi*e/20))/2)
    torch.set_rng_state(state['torch_rng'])
    if state['cuda_rng']:
        torch.cuda.set_rng_state(state['cuda_rng'][0], 0)
    native_rng = np.random.default_rng()
    native_rng.bit_generator.state = state['numpy_rng']
    scan_rng = np.random.default_rng(a.seed+20261011)
    out = a.root/f'continuation/{a.mode}_s{a.seed}'
    out.mkdir(parents=True, exist_ok=False)
    identity = dict(mode=a.mode, seed=a.seed, epochs=20, parent_sha256=sha(parent),
                    weak_freeze_sha256=sha(a.root/'WEAK_SUPERVISION_FREEZE.json'),
                    native_order_and_exposure='same parent RNG, 3200 native rows / epoch, batch16, 200 updates',
                    added_scan_cost='four scan rows / update only in mixed arm',
                    schedule='both arms reset to lr3e-4, cosine20 floor .1; optimizer moments preserved',
                    checkpoint_selection='native VAL identity-equal Camera L2 only',
                    TEST_read=False, camera_B_read=False)
    (out/'EXECUTION_IDENTITY.json').write_text(json.dumps(identity, indent=2))
    valrows = [rows[i] for i in vi]
    best, curves = float('inf'), []
    status = 'COMPLETE'
    scan_visits = np.zeros(len(scan.rows), np.int64) if scan else None
    for epoch in range(1, 21):
        if time.time() >= a.deadline:
            status = 'DEADLINE_SAVED_EPOCH'; break
        tick = time.monotonic()
        model.train()
        losses, weak_losses = [], []
        order = native_rng.permutation(ti)
        for b in range(0, len(order), 16):
            index = order[b:b+16]
            optimizer.zero_grad(set_to_none=True)
            native_loss = F.smooth_l1_loss(forward(model, data, index, 'cuda'), target[index].cuda(), beta=.05)
            loss = native_loss
            if scan:
                si = scan.sample(scan_rng)
                np.add.at(scan_visits, si, 1)
                weak = scan.loss(forward(model, scan.data, si, 'cuda'), si, freeze['weak_weights'])
                loss = loss+weak
                weak_losses.append(float(weak.detach()))
            assert torch.isfinite(loss)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            losses.append(float(native_loss.detach()))
        model.eval()
        with torch.no_grad():
            prediction = torch.cat([forward(model, data, vi[b:b+16], 'cuda').cpu() for b in range(0, len(vi), 16)]).numpy()
        report = camera_summary(prediction, target[vi].numpy(), valrows)
        score = report['camera_mean_mm']
        curves.append(dict(epoch=epoch, native_loss=float(np.mean(losses)),
                           native_order_sha256=hashlib.sha256(order.tobytes()).hexdigest(),
                           weak_loss=float(np.mean(weak_losses)) if scan else None,
                           val=report, seconds=time.monotonic()-tick, lr=optimizer.param_groups[0]['lr']))
        improved = score < best
        best = min(best, score)
        scheduler.step()
        saved = dict(head=model.state_dict(), optimizer=optimizer.state_dict(), scheduler=scheduler.state_dict(),
                     epoch=epoch, best_score=best, execution_identity=identity,
                     torch_rng=torch.get_rng_state(), numpy_rng=native_rng.bit_generator.state,
                     scan_rng=scan_rng.bit_generator.state, cuda_rng=torch.cuda.get_rng_state_all())
        torch.save(saved, out/'last.pt')
        if improved:
            torch.save(saved, out/'best.pt')
            np.savez_compressed(out/'BEST_CAMERAS.npz', cameras=prediction, row_indices=vi)
        (out/'CURVES.json').write_text(json.dumps(curves, indent=2))
        print('CONTINUATION', a.mode, a.seed, epoch, round(score, 3), round(curves[-1]['seconds'], 2), flush=True)
    if curves:
        geometry = native_geometry(native, valrows, np.load(out/'BEST_CAMERAS.npz')['cameras'])
        (out/'RESULTS.json').write_text(json.dumps(dict(status=status, best=geometry, epochs_completed=len(curves),
                                                       best_camera_score_mm=best, identity=identity), indent=2))
    if scan:
        (out/'SCAN_EXPOSURE.json').write_text(json.dumps([
            dict(sample_id=r['sample_id'], identity=r['identity'], count=int(n))
            for r, n in zip(scan.rows, scan_visits)], indent=2))
    print('CONTINUATION_END', a.mode, a.seed, status, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--scan-source', type=Path, required=True)
    p.add_argument('--anchors', type=Path, required=True)
    p.add_argument('--calibrate', action='store_true')
    p.add_argument('--mode', choices=['native_only', 'mixed'])
    p.add_argument('--seed', type=int)
    p.add_argument('--deadline', type=float, required=True)
    a = p.parse_args()
    calibrate(a) if a.calibrate else train(a)
