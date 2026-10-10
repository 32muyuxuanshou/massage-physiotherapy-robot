"""Export TRAIN/VAL read-only Official caches, without decoding or changing Body.

Used on the existing AutoDL CPU instance. No Camera B points enter this export.
The RGB feature is pooled frozen backbone (1280), NOT the final 1024 pose token.
This explicit practical variant permits a Camera-only pilot without redecoding.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import torch


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8*1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def features(record):
    d = record['depth'][0, 0].float().numpy()
    valid = record['valid'][0, 0].numpy().astype(bool) & np.isfinite(d) & (d > 0)
    ray = record['rays'][0].float().numpy()
    z = d[valid]
    # All valid input pixels; identical summaries for native, scan, and real.
    xyz = np.column_stack((ray[:, valid].T*z[:, None], z))
    if len(z):
        q = np.quantile(z, [.1, .25, .5, .75, .9])
        s = np.r_[q, xyz.mean(0), xyz.std(0), q[-1]-q[0], valid.mean()]
    else:
        s = np.zeros(13)
    b = record['batch']
    K = b['cam_int'][0].float().numpy()
    size = b['ori_img_size'].reshape(-1, 2)[0].float().numpy()
    box = b['bbox_scale'].reshape(-1, 2)[0].float().numpy()
    center = b['bbox_center'].reshape(-1, 2)[0].float().numpy()
    camera = record['official']['pred_cam_t'].reshape(3).float().numpy()
    body = record['official']['pred_vertices'].reshape(-1, 3).float().numpy()
    body_summary = np.r_[np.quantile(body, [.25, .5, .75], axis=0).ravel(), body.mean(0), body.std(0)]
    metric = np.r_[s, K[0, 0]/size[0], K[1, 1]/size[1], K[0, 2]/size[0],
                   K[1, 2]/size[1], box[0]/size[0], camera, body_summary]
    rgb = record['backbone'].float().mean((2, 3)).reshape(-1).numpy()
    # Preserve deterministic input-only pixels for later controlled perturbations.
    indices = np.linspace(0, max(len(z)-1, 0), min(len(z), 5000), dtype=np.int64)
    return dict(rgb=rgb.astype('float32'), metric=metric.astype('float32'),
                available=np.bool_(len(z) > 0), original_camera=camera,
                K=K, bbox_center=center, bbox_scale=box,
                depth_valid_fraction=np.float32(valid.mean()),
                measured_z=z[indices], measured_rays=ray[:, valid].T[indices],
                ablation_sample_indices=indices)


def export(cache, out, dataset):
    torch.set_num_threads(1)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = cache/'CACHE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    rows = manifest['records']
    assert all(r['role'] in ['TRAIN', 'VAL'] for r in rows)
    exported = []
    start = time.monotonic()
    for i, row in enumerate(rows):
        source = cache/row['cache_file']
        name = source.stem
        r = torch.load(source, map_location='cpu', weights_only=False)
        values = features(r)
        for k, v in r['official'].items():
            if torch.is_tensor(v):
                values['official_'+k] = v.float().numpy()
        for k, v in r.get('truth', {}).items():
            values['truth_'+k] = v.float().numpy()
        # The training set does not need RGB pixels, raw B observations, or labels.
        target = out/(name+'.npz')
        np.savez_compressed(target, **values)
        exported.append(dict(row, compact_file=target.name,
                             source_cache_sha256=sha(source), compact_sha256=sha(target)))
        if i % 100 == 0:
            print('EXPORTED', dataset, i+1, len(rows), round(time.monotonic()-start), flush=True)
    report = dict(status='COMPLETE', dataset=dataset, records=exported,
                  source_cache_manifest_sha256=sha(manifest_path), seconds=time.monotonic()-start,
                  RGB_representation='pooled frozen Official backbone 1280; not final pose token',
                  body_source='full unmodified cached Official output',
                  test_read=False, camera_B_points_read=False)
    (out/'MANIFEST.json').write_text(json.dumps(report, indent=2))
    print('COMPLETE', dataset, len(rows), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--dataset', required=True)
    a = p.parse_args()
    export(a.cache, a.out, a.dataset)
