"""Frozen RGB-only Official initialization for textured scan renders, no fake GT.

Each shard writes full native outputs once. RGB backbone pooling matches the
Camera-only pilot. Input Depth is registered axial Z; no mesh-driven K fitting.
"""
import os
os.environ.setdefault('MOMENTUM_ENABLED', '0')
import argparse
import copy
import json
from pathlib import Path
import sys
import time
import numpy as np
import torch
from export_compact import features, sha


def prepare(a):
    torch.set_num_threads(2)
    sys.path.insert(0, str(a.source))
    sys.path.insert(0, str(Path(__file__).parent/'shared'))
    from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    from geometry import crop_registered_depth
    model, cfg = load_sam_3d_body(str(a.checkpoint), device='cuda', mhr_path=str(a.mhr))
    model.requires_grad_(False)
    model.eval()
    estimator = SAM3DBodyEstimator(model, cfg, human_detector=None, human_segmentor=None, fov_estimator=None)
    captured = []
    hook = model.backbone.register_forward_hook(lambda m, args, o: captured.append((o[-1] if isinstance(o, tuple) else o).detach().cpu()))
    a.out.mkdir(parents=True, exist_ok=True)
    rows = json.loads((a.data/'MANIFEST.json').read_text())['samples']
    assert len(rows)==3072 and all(r['role'] in ['TRAIN', 'VAL'] for r in rows)
    rows = rows[a.shard::a.shards]
    if a.limit:
        rows = rows[:a.limit]
    done = []
    started = time.monotonic()
    for i, row in enumerate(rows):
        if time.time() >= a.deadline:
            break
        target = a.out/(row['sample_id']+'.npz')
        if not target.exists():
            source = a.data/row['file']
            assert sha(source)==row['sha256']
            with np.load(source) as z:
                rgb, K, bbox, mask = z['rgb'], z['K'], z['bbox'], z['mask']
                d = z['depth_m']*mask
            batch = prepare_batch(rgb, estimator.transform, bbox[None], masks=mask.astype(np.uint8)[None],
                                  cam_int=torch.from_numpy(K[None]).float())
            batch = {k: v for k, v in batch.items() if torch.is_tensor(v)}
            depth, valid, rays = crop_registered_depth(torch.from_numpy(d[None, None]), batch)
            gpu = recursive_to(copy.deepcopy(batch), 'cuda')
            model._initialize_batch(gpu)
            captured.clear()
            with torch.no_grad():
                output = model.forward_step(gpu, decoder_type='body')['mhr']
            cpu = {k: v.detach().cpu() for k, v in output.items() if torch.is_tensor(v)}
            assert torch.isfinite(cpu['pred_vertices']).all() and torch.isfinite(cpu['pred_cam_t']).all()
            assert cpu['pred_vertices'].shape[-2:]==(18439, 3)
            rec = dict(batch=batch, backbone=captured[-1], depth=depth, valid=valid, rays=rays, official=cpu)
            values = features(rec)
            values.update({'official_'+k: v.float().numpy() for k, v in cpu.items()})
            np.savez_compressed(target, **values)
        done.append(dict(row, compact_file=target.name, compact_sha256=sha(target)))
        if i % 20 == 0:
            print('SCAN_CACHE', a.shard, i+1, len(rows), round(time.monotonic()-started), flush=True)
    hook.remove()
    report = dict(status='COMPLETE' if len(done)==len(rows) else 'DEADLINE_PARTIAL', records=done,
                  shard=a.shard, shards=a.shards, source_manifest_sha256=sha(a.data/'MANIFEST.json'),
                  official_checkpoint_sha256=sha(a.checkpoint), mhr_asset_sha256=sha(a.mhr),
                  seconds=time.monotonic()-started, test_read=False, MHR_root_GT_available=False,
                  official_precision=str(cfg.TRAIN.FP16_TYPE), peak_gpu_memory_bytes=torch.cuda.max_memory_allocated())
    (a.out/f'MANIFEST_{a.shard:02d}.json').write_text(json.dumps(report, indent=2))
    np.save(a.out/'faces.npy', model.head_pose.faces.detach().cpu().numpy())
    print('SCAN_CACHE_END', report['status'], a.shard, len(done), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for n in ['source', 'checkpoint', 'mhr', 'data', 'out']:
        p.add_argument('--'+n, type=Path, required=True)
    p.add_argument('--shard', type=int, default=0)
    p.add_argument('--shards', type=int, default=1)
    p.add_argument('--limit', type=int)
    p.add_argument('--deadline', type=float, required=True)
    prepare(p.parse_args())
