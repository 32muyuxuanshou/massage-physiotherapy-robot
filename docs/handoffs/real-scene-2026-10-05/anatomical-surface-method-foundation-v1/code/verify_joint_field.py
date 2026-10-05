"""Normal-path train-only prototype check, not an evaluation of method accuracy."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from joint_surface_field import JointSurfaceField

ROOT = Path('/raid5/xuhd/datasets/anatomical_surface_method_foundation_20261005')
SOURCE = Path('/raid5/xuhd/datasets/ct_anatomical_query_pilot_20261005')
LEVEL_INDEX = np.array([6., 9., 11., 15., 20.], np.float32)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one_case(row, rng):
    path = Path(row['path'])
    assert sha(path) == row['input_sha256']
    with np.load(path) as data:
        height = data['surface_height_mm']
        valid = data['surface_valid']
        xmin, xmax, zmin, zmax = data['xz_bounds_mm']
        xx, zz = np.meshgrid(np.linspace(xmin, xmax, height.shape[1]), np.linspace(zmax, zmin, height.shape[0]))
        surface = np.column_stack([xx[valid], height[valid], zz[valid]])
        target = data['target_xyz_mm'].copy()
        label_valid = data['target_valid'].astype(bool)
    assert label_valid[1] and label_valid[4]
    references = target[[1, 4]]
    # Geometry-only centering, fixed physical scale: the unprompted pathway does
    # not receive endpoint coordinates through a label-dependent normalization.
    origin = np.median(surface, axis=0)
    scale = 500.
    surface = (surface - origin) / scale
    target = (target - origin) / scale
    references = (references - origin) / scale
    observed_index = rng.choice(len(surface), 512, replace=False)
    # Query targets are disjoint clean surface samples, not copied observed points.
    remaining = np.setdiff1d(np.arange(len(surface)), observed_index)
    query_index = rng.choice(remaining, 256, replace=False)
    assert len(np.intersect1d(observed_index, query_index)) == 0
    clean_query = surface[query_index]
    observed = surface[observed_index] + rng.normal(0, 2. / scale, (512, 3))
    query = clean_query + rng.normal(0, 10. / scale, (256, 3))
    indices = np.where(label_valid)[0][::-1]
    zz = target[indices, 2]
    # Dense supervision interpolates CT proxies; it is not a measured anatomical
    # coordinate field and must not be called a clinical vertebral depression.
    level = (np.interp(clean_query[:, 2], zz, LEVEL_INDEX[indices]) - 9.) / 11.
    midline_x = np.interp(clean_query[:, 2], zz, target[indices, 0])
    lateral = clean_query[:, 0] - midline_x
    anatomical = np.column_stack([level, lateral])
    anatomy_valid = ((clean_query[:, 2] >= zz[0]) & (clean_query[:, 2] <= zz[-1]) & (np.abs(lateral) < 150. / scale))
    assert anatomy_valid.sum() >= 8
    record = dict(subject=row['subject'], role=row['role'], source_sha256=sha(path),
                  normalization_origin_mm=origin.tolist(), normalization_scale_mm=scale,
                  observed_indices=observed_index.tolist(), query_indices=query_index.tolist(),
                  anatomical_supervision_points=int(anatomy_valid.sum()),
                  clinical_ground_truth=False)
    arrays = dict(observed=observed, query=query, surface_delta=clean_query-query,
                  anatomical_coordinates=anatomical, anatomy_valid=anatomy_valid,
                  references=references)
    return arrays, record


def loss(prediction, batch):
    surface = F.smooth_l1_loss(prediction['surface_delta'], batch['surface_delta'], beta=.02)
    anatomy = F.smooth_l1_loss(prediction['anatomical_coordinates'][batch['anatomy_valid']],
                             batch['anatomical_coordinates'][batch['anatomy_valid']], beta=.05)
    return surface + anatomy, dict(surface=float(surface.detach()), anatomy=float(anatomy.detach()))


def main():
    start = time.time()
    torch.manual_seed(17)
    rng = np.random.default_rng(17)
    torch.set_num_threads(4)
    rows = json.loads((SOURCE / 'CASE_MANIFEST.json').read_text())
    selected = [r for r in rows if r['eligible'] and r['role'] == 'train' and r['target_valid'][1] and r['target_valid'][4]][:4]
    assert len(selected) == 4
    examples = [one_case(r, rng) for r in selected]
    device = torch.device('cuda:0')
    batch = {key: torch.as_tensor(np.stack([a[key] for a, _ in examples]), device=device,
                                  dtype=torch.bool if key == 'anatomy_valid' else torch.float32)
             for key in examples[0][0]}
    present = torch.ones(4, 2, dtype=torch.bool, device=device)
    model = JointSurfaceField().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
    torch.cuda.reset_peak_memory_stats()
    model.train()
    with torch.no_grad():
        initial, initial_components = loss(model(batch['observed'], batch['query'], batch['references'], present), batch)
    trace = []
    for step in range(80):
        prediction = model(batch['observed'], batch['query'], batch['references'], present)
        total, components = loss(prediction, batch)
        optimizer.zero_grad(); total.backward(); optimizer.step()
        trace.append(dict(step=step, total=float(total.detach()), **components))
    model.eval()
    with torch.no_grad():
        prediction = model(batch['observed'], batch['query'], batch['references'], present)
        final, final_components = loss(prediction, batch)
        unprompted = model(batch['observed'], batch['query'], batch['references'], torch.zeros_like(present))
        assert all(torch.isfinite(t).all() for t in [*prediction.values(), *unprompted.values()])
    assert float(final) < float(initial)
    dest = ROOT / 'prototype_check'; dest.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dest / 'normal_path_cache.npz',
                        **{k: v.detach().cpu().numpy() for k, v in batch.items()},
                        predicted_surface_delta=prediction['surface_delta'].cpu().numpy(),
                        predicted_anatomical_coordinates=prediction['anatomical_coordinates'].cpu().numpy())
    torch.save(model.state_dict(), dest / 'train_only_prototype.pt')
    (dest / 'CASE_INPUT_IDENTITY.json').write_text(json.dumps([r for _, r in examples], indent=2) + '\n')
    receipt = dict(status='NORMAL_PATH_PASS_NOT_SCIENTIFIC_EVAL', train_cases=[r['subject'] for r in selected],
                   test_cases_used=0, steps=80, parameters=sum(p.numel() for p in model.parameters()),
                   initial_loss=float(initial), final_loss=float(final), initial_components=initial_components,
                   final_components=final_components, trace=trace, input_noise_mm=2., query_noise_mm=10.,
                   units='RAS mm, skin-only median centering, fixed 500mm scale; CT-only train verification',
                   outputs={k:list(v.shape) for k,v in prediction.items()},
                   unprompted_forward_finite=True, peak_GPU_MB=torch.cuda.max_memory_allocated()/1024**2,
                   seconds=time.time()-start, checkpoint_sha256=sha(dest/'train_only_prototype.pt'),
                   cache_sha256=sha(dest/'normal_path_cache.npz'),
                   source_manifest_sha256=sha(SOURCE/'CASE_MANIFEST.json'),
                   code_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')})
    (dest / 'PROTOTYPE_CHECK.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['trace','code_sha256']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
