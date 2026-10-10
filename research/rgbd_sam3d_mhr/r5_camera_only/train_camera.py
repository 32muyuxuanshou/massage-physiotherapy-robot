"""Native-GT Camera-only training, bounded vs metric output, fixed RGB Body.

Identity roles and cached Official initializations are reused. Best selection
uses native synthetic VAL Camera L2 only. Real sensor B is never opened here.
"""
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_table(data):
    m = json.loads((data/'MANIFEST.json').read_text())
    assert all(r['role'] in ['TRAIN', 'VAL'] for r in m['records'])
    keys = ['rgb', 'metric', 'original_camera', 'K', 'bbox_center', 'bbox_scale', 'available']
    table = {k: [] for k in keys}
    labels = []
    for row in m['records']:
        with np.load(data/row['compact_file']) as z:
            for k in keys:
                table[k].append(z[k])
            labels.append(z['truth_pred_cam_t'].reshape(3))
    return m['records'], {k: torch.as_tensor(np.stack(v)) for k, v in table.items()}, torch.as_tensor(np.stack(labels))


def forward(model, data, index, device):
    x = {k: v[index].to(device) for k, v in data.items()}
    return model(x['rgb'], x['metric'], x['original_camera'], x['K'],
                 x['bbox_center'], x['bbox_scale'], x['available'])


def camera_summary(prediction, target, rows):
    d = np.linalg.norm(prediction-target, axis=1)*1000
    ids = sorted({r['identity'] for r in rows})
    per = {identity: dict(camera_mean_mm=float(d[[r['identity']==identity for r in rows]].mean()),
                          camera_p95_mm=float(np.quantile(d[[r['identity']==identity for r in rows]], .95)))
           for identity in ids}
    return dict(camera_mean_mm=float(np.mean([v['camera_mean_mm'] for v in per.values()])),
                camera_p95_identity_mean_mm=float(np.mean([v['camera_p95_mm'] for v in per.values()])),
                per_identity=per)


def native_geometry(data, rows, cameras):
    records = []
    for row, camera in zip(rows, cameras):
        with np.load(data/row['compact_file']) as z:
            body = z['official_pred_vertices'].reshape(-1, 3)
            truth = z['truth_pred_vertices'].reshape(-1, 3)
            gtcam = z['truth_pred_cam_t'].reshape(3)
            joints = z['official_pred_joint_coords'].reshape(-1, 3)
            gtjoints = z['truth_pred_joint_coords'].reshape(-1, 3)
            difference = body-truth
            record = dict(identity=row['identity'], file=row['compact_file'],
                          camera_xyz_m=camera.tolist(), camera_xyz_error_mm=((camera-gtcam)*1000).tolist(),
                          camera_mm=float(np.linalg.norm(camera-gtcam)*1000),
                          vertex_body_mm=float(np.linalg.norm(difference, axis=1).mean()*1000),
                          vertex_camera_mm=float(np.linalg.norm(difference+camera-gtcam, axis=1).mean()*1000),
                          vertex_translation_removed_mm=float(np.linalg.norm(difference-difference.mean(0), axis=1).mean()*1000),
                          joint_camera_mm=float(np.linalg.norm(joints-gtjoints+camera-gtcam, axis=1).mean()*1000),
                          body_change_from_Official_mm=0., pose_change_from_Official=0.,
                          shape_change_from_Official=0., scale_change_from_Official=0.)
            records.append(record)
    names = ['camera_mm', 'vertex_body_mm', 'vertex_camera_mm', 'vertex_translation_removed_mm', 'joint_camera_mm']
    ids = sorted({r['identity'] for r in records})
    per = {identity: {k: float(np.mean([r[k] for r in records if r['identity']==identity])) for k in names} for identity in ids}
    return dict(identity_equal_mean={k: float(np.mean([r[k] for r in per.values()])) for k in names},
                per_identity=per, records=records)


def train(a):
    torch.set_num_threads(2)
    torch.manual_seed(a.seed)
    np.random.seed(a.seed)
    device = torch.device(a.device)
    rows, data, target = load_table(a.data)
    ti = np.asarray([i for i, r in enumerate(rows) if r['role']=='TRAIN'])
    vi = np.asarray([i for i, r in enumerate(rows) if r['role']=='VAL'])
    assert len(ti)==3200 and len(vi)==400
    mean = data['metric'][ti].mean(0)
    std = data['metric'][ti].std(0, unbiased=False)
    model = CameraHead(mean, std, a.mode).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    schedule = lambda e: min(1., (e+1)/2)*(.1+.9*(1+math.cos(math.pi*max(0,e-1)/max(1,a.epochs-2)))/2)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, schedule)
    rng = np.random.default_rng(a.seed)
    a.out.mkdir(parents=True, exist_ok=False)
    identity = dict(mode=a.mode, seed=a.seed, lr=a.lr, epochs=a.epochs, batch_size=16,
                    data_manifest_sha256=sha(a.data/'MANIFEST.json'),
                    source_sha256={p.name: sha(p) for p in Path(__file__).parent.glob('*.py')},
                    supervision='mean per-axis SmoothL1 native GT Camera, beta=.05 metres',
                    checkpoint_selection='native VAL identity-equal Camera L2 mean',
                    body_path='full frozen Official cached RGB output; no early fusion',
                    rgb_representation='pooled frozen backbone 1280; explicit new pilot representation',
                    test_read=False, camera_B_read=False)
    (a.out/'EXECUTION_IDENTITY.json').write_text(json.dumps(identity, indent=2))
    valrows = [rows[i] for i in vi]
    valtarget = target[vi].numpy()
    curves, best = [], float('inf')
    start = time.monotonic()
    reason = 'COMPLETE'
    for epoch in range(1, a.epochs+1):
        if time.time() >= a.deadline:
            reason = 'DEADLINE_SAVED_EPOCH'; break
        tick = time.monotonic()
        model.train()
        order = rng.permutation(ti)
        losses = []
        for b in range(0, len(order), 16):
            index = order[b:b+16]
            optimizer.zero_grad(set_to_none=True)
            pred = forward(model, data, index, device)
            loss = F.smooth_l1_loss(pred, target[index].to(device), beta=.05)
            assert torch.isfinite(loss)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            losses.append(float(loss.detach()))
        model.eval()
        with torch.no_grad():
            predicted = torch.cat([forward(model, data, vi[b:b+16], device).cpu() for b in range(0, len(vi), 16)]).numpy()
        report = camera_summary(predicted, valtarget, valrows)
        score = report['camera_mean_mm']
        curve = dict(epoch=epoch, loss=float(np.mean(losses)), val=report,
                     lr=optimizer.param_groups[0]['lr'], seconds=time.monotonic()-tick)
        curves.append(curve)
        improved = score < best
        best = min(best, score)
        scheduler.step()
        state = dict(head=model.state_dict(), optimizer=optimizer.state_dict(), scheduler=scheduler.state_dict(),
                     epoch=epoch, best_score=best, execution_identity=identity,
                     torch_rng=torch.get_rng_state(), numpy_rng=rng.bit_generator.state,
                     cuda_rng=torch.cuda.get_rng_state_all() if device.type=='cuda' else [])
        torch.save(state, a.out/'last.pt')
        if improved:
            torch.save(state, a.out/'best.pt')
            np.savez_compressed(a.out/'BEST_CAMERAS.npz', cameras=predicted, row_indices=vi)
        (a.out/'CURVES.json').write_text(json.dumps(curves, indent=2))
        print('EPOCH', a.mode, a.seed, epoch, 'VAL_CAMERA_MM', round(score, 3), 'SECONDS', round(curve['seconds'], 2), flush=True)
    if curves:
        bestcam = np.load(a.out/'BEST_CAMERAS.npz')['cameras']
        geometry = native_geometry(a.data, valrows, bestcam)
        baseline = native_geometry(a.data, valrows, data['original_camera'][vi].numpy())
        result = dict(status=reason, best=geometry, official=baseline, epochs_completed=len(curves),
                      best_camera_score_mm=best, seconds=time.monotonic()-start,
                      peak_gpu_memory_bytes=torch.cuda.max_memory_allocated() if device.type=='cuda' else 0,
                      execution_identity=identity)
        (a.out/'RESULTS.json').write_text(json.dumps(result, indent=2))
    print('TRAIN_END', a.mode, a.seed, reason, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--mode', choices=['raw_bounded', 'metric_xyz', 'rgb_only_xyz'], required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--epochs', type=int, default=50)
    p.add_argument('--device', default='cuda')
    p.add_argument('--deadline', type=float, required=True)
    train(p.parse_args())
