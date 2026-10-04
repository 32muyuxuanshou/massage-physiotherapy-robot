"""Freeze role assignment and construct surface-only inputs for a new CT task."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

SOURCE = Path('/raid5/xuhd/datasets/ct_back_anatomical_reference_20261005')
OUT = Path('/raid5/xuhd/datasets/ct_anatomical_query_pilot_20261005')
LEVELS = ['C7', 'T3', 'T5', 'T9', 'L2']


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assign_roles(rows):
    ids = sorted(r['subject'] for r in rows if r['meta']['split'] == 'train')
    rng = np.random.default_rng(42); rng.shuffle(ids)
    for development in ['s0011', 's0250']:
        j = ids.index(development)
        if j >= 70:
            i = next(k for k in range(70) if ids[k] not in ['s0011', 's0250'])
            ids[i], ids[j] = ids[j], ids[i]
    assert len(ids) == 98
    return {**{s: 'train' if i < 70 else 'dev' if i < 84 else 'test' for i, s in enumerate(ids)},
            **{r['subject']: 'author_val_supporting' for r in rows if r['meta']['split'] == 'val'}}


def prepare_one(row, role):
    root = SOURCE / 'derived' / row['subject']
    flags = []; targets = []; xyz = []
    for t in row['targets']:
        good = (t['status'] == 'CT_SURFACE_PROXY' and not t['touches_scanner_boundary']
                and t['posterior_extreme_surface_valid'] and 0 <= t['bone_to_skin_posterior_distance_mm'] <= 200
                and np.all(np.isfinite(t['posterior_extreme_surface_xyz_mm'])))
        good = bool(good)
        flags.append(good)
        xyz.append(t['posterior_extreme_surface_xyz_mm'] if good else [0., 0., 0.])
    valid_z = [point[2] for point, good in zip(xyz, flags) if good]
    source_order_pass = all(b < a for a, b in zip(valid_z, valid_z[1:]))
    eligible = sum(flags) >= 3 and row['surface_valid_columns'] >= 10000 and source_order_pass
    record = dict(subject=row['subject'], role=role, author_split=row['meta']['split'], eligible=eligible,
                  target_valid=flags, anatomical_label_order_pass=source_order_pass,
                  ct_sha256=row['ct_sha256'], surface_sha256=row['posterior_surface_sha256'])
    if not eligible:
        return record
    with np.load(root / 'posterior_surface.npz') as surface:
        assert sha(root / 'posterior_surface.npz') == row['posterior_surface_sha256']
        valid = surface['valid'].T[::-1].copy()
        height = surface['points_ras_mm'][:, :, 1].T[::-1].copy()
        affine = surface['ct_affine']; shape = surface['voxel_shape']
        xmin = affine[0, 3]; xmax = xmin + (shape[0]-1) * affine[0, 0]
        zmin = affine[2, 3]; zmax = zmin + (shape[2]-1) * affine[2, 2]
    height_center = float(np.median(height[valid]))
    weighted = np.where(valid, height - height_center, 0)
    small = F.interpolate(torch.tensor(np.stack([weighted, valid.astype(np.float32)]))[None], size=(128, 128), mode='bilinear', align_corners=True)[0].numpy()
    small_height = np.divide(small[0], small[1], out=np.zeros_like(small[0]), where=small[1] > .5) / 300
    u, v = np.meshgrid(np.linspace(0, 1, 128), np.linspace(0, 1, 128))
    input_array = np.stack([small_height, (small[1] > .5).astype(float), (u-.5)*(xmax-xmin)/400, (v-.5)*(zmax-zmin)/800]).astype(np.float32)
    xyz = np.asarray(xyz, np.float32)
    uv = np.column_stack(((xyz[:, 0]-xmin)/(xmax-xmin), (zmax-xyz[:, 2])/(zmax-zmin))).astype(np.float32)
    path = OUT / 'inputs' / (row['subject'] + '.npz'); path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, input=input_array, target_uv=uv, target_xyz_mm=xyz, target_valid=flags,
                        xz_bounds_mm=[xmin,xmax,zmin,zmax], surface_height_mm=height, surface_valid=valid)
    record.update(path=str(path), input_sha256=sha(path), field_size_xz_mm=[xmax-xmin,zmax-zmin], height_center_mm=height_center)
    return record


def main():
    rows = json.loads((SOURCE / 'ALL_SOURCE_QUALIFICATION.json').read_text())
    roles = assign_roles(rows)
    manifest = [prepare_one(row, roles[row['subject']]) for row in rows]
    write(OUT / 'CASE_MANIFEST.json', manifest)
    counts = {role: dict(cases=sum(r['eligible'] and r['role']==role for r in manifest),
                        levels=np.sum([r['target_valid'] for r in manifest if r['eligible'] and r['role']==role],axis=0).astype(int).tolist())
              for role in ['train','dev','test','author_val_supporting']}
    assert counts['train']['cases'] >= 15 and counts['dev']['cases'] >= 2 and counts['test']['cases'] >= 2
    write(OUT / 'DATA_SUMMARY.json', dict(counts=counts, levels=LEVELS, original_case_count=len(rows),
            source_kind='real CT-derived posterior heightfield, no RGB/no native depth sensor',
            split_seed=42, no_label_input=True, medical_validated=False))
    print(json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
