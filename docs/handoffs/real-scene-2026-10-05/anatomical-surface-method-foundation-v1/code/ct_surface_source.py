"""CT-only posterior surface with separately derived, nonclinical vertebral proxies."""
import argparse
import csv
import hashlib
import json
import time
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import nibabel as nib
from nibabel.processing import resample_from_to, resample_to_output
import numpy as np
from scipy import ndimage as ndi

from download_ct_subset import ROOT

LEVELS = ['C7', 'T3', 'T5', 'T9', 'L2']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def posterior_surface(volume):
    """Do not use bone labels to select or crop the body input."""
    mask = np.zeros(volume.shape, bool)
    for z in range(volume.shape[2]):
        plane = ndi.binary_opening(volume[:, :, z] > -500, iterations=2)
        labels, n = ndi.label(plane)
        if n:
            counts = np.bincount(labels.ravel()); counts[0] = 0
            mask[:, :, z] = ndi.binary_fill_holes(labels == counts.argmax())
    valid = mask.any(axis=1)
    y_index = mask.argmax(axis=1).astype(np.float32)
    y_index[~valid] = np.nan
    return mask, y_index


def source_reference(subject, meta):
    start = time.monotonic()
    ct_path = ROOT / 'raw' / subject / 'ct.nii.gz'
    image = nib.as_closest_canonical(nib.load(ct_path))
    original_affine = image.affine.copy()
    resampled = not np.allclose(image.affine[:3, :3], np.diag(np.diag(image.affine[:3, :3])))
    if resampled:
        image = resample_to_output(image, voxel_sizes=nib.affines.voxel_sizes(image.affine), order=1, cval=-1024)
    affine = image.affine
    assert np.allclose(affine[:3, :3], np.diag(np.diag(affine[:3, :3])))
    volume = np.asarray(image.dataobj, np.float32)
    mask, yi = posterior_surface(volume)
    xx, zz = np.indices(yi.shape)
    points = nib.affines.apply_affine(affine, np.column_stack((xx.ravel(), yi.ravel(), zz.ravel()))).reshape(*yi.shape, 3)
    valid = np.isfinite(yi)
    targets = []
    voxel_coords = None
    for level in LEVELS:
        path = ROOT / 'raw' / subject / 'segmentations' / ('vertebrae_' + level + '.nii.gz')
        label_image = nib.as_closest_canonical(nib.load(path))
        native_label = np.asarray(label_image.dataobj) > 0
        scanner_contact = bool(any(np.take(native_label, edge, axis=axis).any()
                                   for axis in range(3) for edge in [0, -1]))
        if resampled:
            label_image = resample_from_to(label_image, (image.shape, affine), order=0, cval=0)
        assert label_image.shape == image.shape and np.allclose(label_image.affine, affine)
        coords = np.argwhere(np.asarray(label_image.dataobj) > 0)
        if not len(coords):
            targets.append(dict(level=level, status='LABEL_ABSENT'))
            continue
        centroid = coords.mean(axis=0)
        posterior = coords[coords[:, 1] <= np.quantile(coords[:, 1], .02)].mean(axis=0)
        record = dict(level=level, status='CT_SURFACE_PROXY', voxels=len(coords),
                      touches_scanner_boundary=scanner_contact)
        for name, coord in [('centroid', centroid), ('posterior_extreme', posterior)]:
            x, z = np.rint(coord[[0, 2]]).astype(int)
            surface_coord = np.array([x, yi[x, z], z])
            record[name + '_bone_xyz_mm'] = nib.affines.apply_affine(affine, coord).tolist()
            record[name + '_surface_xyz_mm'] = nib.affines.apply_affine(affine, surface_coord).tolist()
            record[name + '_surface_valid'] = bool(valid[x, z])
        record['proxy_definition_vertical_difference_mm'] = abs(record['centroid_surface_xyz_mm'][2] - record['posterior_extreme_surface_xyz_mm'][2])
        record['bone_to_skin_posterior_distance_mm'] = record['posterior_extreme_bone_xyz_mm'][1] - record['posterior_extreme_surface_xyz_mm'][1]
        targets.append(record)
    out = ROOT / 'derived' / subject
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / 'posterior_surface.npz', points_ras_mm=points.astype(np.float32), valid=valid,
                        ct_affine=affine, voxel_shape=image.shape, posterior_y_index=yi)
    public_meta = {k: meta[k] for k in ['image_id', 'split', 'study_type']}
    result = dict(subject=subject, meta=public_meta, axis='RAS mm, posterior -Y', ct_shape=list(image.shape),
                  oblique_resampled=resampled, original_canonical_affine=original_affine.tolist(),
                  processed_affine=affine.tolist(),
                  spacing_mm=list(nib.affines.voxel_sizes(affine)), ct_sha256=sha(ct_path),
                  posterior_surface_sha256=sha(out / 'posterior_surface.npz'),
                  surface_method='CT-only HU>-500 / axial opening2 / largest component / first -Y boundary',
                  surface_valid_columns=int(valid.sum()), surface_all_columns=int(valid.size),
                  posterior_boundary_contact_fraction=float(np.mean(yi[valid] <= 2)) if valid.any() else None,
                  targets=targets, medical_validated=False, seconds=time.monotonic() - start)
    (out / 'REFERENCE.json').write_text(json.dumps(result, indent=2))
    figure(volume, mask, affine, points, valid, result, out / 'CT_SURFACE_REFERENCE.png')
    print(subject, len([t for t in targets if t['status'] != 'LABEL_ABSENT']), 'levels', round(result['seconds'], 2), 's', flush=True)
    return result


def figure(volume, mask, affine, points, valid, result, dest):
    fig, axes = plt.subplots(1, 3, figsize=(15, 7))
    axes[0].imshow(volume[volume.shape[0] // 2, :, :].T, origin='lower', cmap='gray', vmin=-600, vmax=900)
    axes[0].contour(mask[volume.shape[0] // 2, :, :].T, levels=[.5], colors=['cyan'], linewidths=.7)
    axes[0].set(title='Sagittal CT + CT-only body contour', xlabel='anterior-positive voxel', ylabel='superior-positive voxel')
    y = np.ma.masked_invalid(points[:, :, 1].T)
    corners = nib.affines.apply_affine(affine, np.array([[0, 0, 0], [volume.shape[0]-1, 0, volume.shape[2]-1]]))
    extent = [corners[0, 0], corners[1, 0], corners[0, 2], corners[1, 2]]
    axes[1].imshow(y, origin='lower', extent=extent, cmap='viridis', aspect='equal')
    axes[1].set(title='Posterior CT heightfield (orthographic)', xlabel='Right +X / mm', ylabel='Superior +Z / mm')
    for target in result['targets']:
        if target['status'] == 'LABEL_ABSENT':
            continue
        for name, color in [('centroid', 'orange'), ('posterior_extreme', 'red')]:
            p = target[name + '_surface_xyz_mm']
            axes[1].scatter(p[0], p[2], s=35, c=color, edgecolors='black')
        p = target['centroid_surface_xyz_mm']; axes[1].text(p[0] + 8, p[2], target['level'], fontsize=9)
    z = volume.shape[2] // 2
    axes[2].imshow(volume[:, :, z].T, origin='lower', cmap='gray', vmin=-600, vmax=900)
    axes[2].contour(mask[:, :, z].T, levels=[.5], colors=['cyan'], linewidths=.8)
    axes[2].set(title='Middle axial CT + body contour', xlabel='right-positive voxel', ylabel='anterior-positive voxel')
    fig.suptitle(result['subject'] + ' | Real CT label proxies, not acupoint GT; acquisition not certified prone')
    fig.tight_layout(); fig.savefig(dest, dpi=140); plt.close(fig)


def extract_selected_from_complete_zip(subjects):
    receipt = json.loads((ROOT / 'DOWNLOAD_RESULT.json').read_text())
    assert receipt['status'] == 'PASS'
    with zipfile.ZipFile(ROOT / receipt['filename']) as z:
        for name in z.namelist():
            if name.split('/')[0] in subjects and (name.endswith('/ct.nii.gz') or any(k in name for k in ['vertebrae_', 'scapula_', 'hip_', 'sacrum'])):
                dest = ROOT / 'raw' / name
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(z.read(name))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--all', action='store_true'); parser.add_argument('--resume', action='store_true'); parser.add_argument('--subjects', nargs='+'); args = parser.parse_args()
    with (ROOT / 'archive_metadata' / 'meta.csv').open(encoding='utf-8-sig') as f:
        metadata = {r['image_id']: r for r in csv.DictReader(f, delimiter=';')}
    subjects = args.subjects or (sorted(metadata) if args.all else ['s0011', 's0250'])
    if args.all:
        extract_selected_from_complete_zip(subjects)
    results = []
    for subject in subjects:
        previous = ROOT / 'derived' / subject / 'REFERENCE.json'
        if args.resume and previous.exists():
            results.append(json.loads(previous.read_text()))
        else:
            results.append(source_reference(subject, metadata[subject]))
    dest = ROOT / ('ALL_SOURCE_QUALIFICATION.json' if args.all else 'DEVELOPMENT_QUALIFICATION.json')
    dest.write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
