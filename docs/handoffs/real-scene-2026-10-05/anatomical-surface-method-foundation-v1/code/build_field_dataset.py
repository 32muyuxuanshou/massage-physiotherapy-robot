"""CT surface/vertebral proxy field pack; keeps source roles and partial coverage.

Dense anatomy supervision is interpolation between CT posterior bone proxies,
not observed skin landmarks or clinical acupoints. CT-derived input has no RGB,
SAM features, MHR vertices, or native RGB-D sensor validation.
"""
import argparse
import csv
import importlib.util
import json
import os
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from acquire_full_v3 import ROOT

LEVELS = ['C7'] + ['T'+str(i) for i in range(1, 13)] + ['L'+str(i) for i in range(1, 6)]


def load_surface_source(work):
    # Frozen helper is copied byte-for-byte from the earlier verified CT stage.
    spec = importlib.util.spec_from_file_location('ct_surface_source', Path(__file__).with_name('ct_surface_source.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.ROOT = work
    module.LEVELS = LEVELS
    return module


def pack(result, role, work, sha):
    flags, xyz = [], []
    for t in result['targets']:
        good = (t['status'] == 'CT_SURFACE_PROXY' and not t['touches_scanner_boundary']
                and t['posterior_extreme_surface_valid']
                and 0 <= t['bone_to_skin_posterior_distance_mm'] <= 200
                and np.all(np.isfinite(t['posterior_extreme_surface_xyz_mm'])))
        flags.append(bool(good))
        xyz.append(t['posterior_extreme_surface_xyz_mm'] if good else [0., 0., 0.])
    xyz = np.asarray(xyz, np.float32); flags = np.asarray(flags, bool)
    order_pass = bool(np.all(np.diff(xyz[flags, 2]) < 0))
    record = dict(case=result['subject'], role=role, valid_levels=flags.tolist(),
                  label_order_pass=order_pass, ct_sha256=result['ct_sha256'],
                  surface_sha256=result['posterior_surface_sha256'],
                  eligible=bool(flags.sum() >= 3 and order_pass and result['surface_valid_columns'] >= 10000),
                  anatomy_target='CT posterior-2-percent-voxel skin projection; interpolated field is proxy supervision',
                  clinical_ground_truth=False)
    if not record['eligible']:
        return record
    source = work/'derived'/result['subject']/'posterior_surface.npz'
    with np.load(source) as data:
        flat = data['points_ras_mm'].reshape(-1, 3)
        indices = np.flatnonzero(data['valid'].ravel())
        rng = np.random.default_rng(int(result['ct_sha256'][:8], 16))
        sample_indices = rng.choice(indices, min(8192, len(indices)), replace=False)
        points = flat[sample_indices]
    reverse = np.flatnonzero(flags)[::-1]
    zz = xyz[reverse, 2]
    longitudinal = (np.interp(points[:, 2], zz, reverse) - 3.) / 11.
    midline_x = np.interp(points[:, 2], zz, xyz[reverse, 0])
    lateral_mm = points[:, 0] - midline_x
    anatomy_valid = ((points[:, 2] >= zz[0]) & (points[:, 2] <= zz[-1]) & (np.abs(lateral_mm) < 150))
    # Missing/clipped levels remain masked; they are not background examples.
    references = xyz[[3, 14]]
    reference_present = flags[[3, 14]]
    path = work/'field_packs'/(result['subject']+'.npz'); path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, points_ras_mm=points, sample_surface_indices=sample_indices,
                        anatomical_coordinates=np.column_stack([longitudinal, lateral_mm/500.]).astype(np.float32),
                        anatomy_valid=anatomy_valid, references_ras_mm=references,
                        reference_present=reference_present, level_xyz_mm=xyz, level_valid=flags)
    record.update(pack=str(path), pack_sha256=sha(path), points=len(points),
                  anatomical_supervision_points=int(anatomy_valid.sum()))
    return record


def extract_complete(role_rows, work):
    receipt = json.loads((ROOT/'DOWNLOAD_RESULT.json').read_text())
    assert receipt['status'] == 'PASS'
    raw = work/'raw'
    wanted = {r['case'] for r in role_rows}
    labels = {'vertebrae_'+level+'.nii.gz' for level in LEVELS + ['L6']}
    with zipfile.ZipFile(ROOT/receipt['filename']) as archive:
        for info in archive.infolist():
            parts = info.filename.split('/')[1:]
            if parts[0] in wanted and (parts[-1] == 'ct.nii.gz' or parts[-1] in labels):
                path = raw/Path(*parts)
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(info))


def initialize_worker(work):
    global WORK, HELPER
    WORK = Path(work)
    HELPER = load_surface_source(WORK)


def process_case(item):
    row, metadata, resume = item
    case = row['case']; previous = WORK/'derived'/case/'REFERENCE.json'
    result = json.loads(previous.read_text()) if resume and previous.exists() else HELPER.source_reference(case, metadata)
    return pack(result, row['role'], WORK, HELPER.sha)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--structure-check', action='store_true')
    parser.add_argument('--all-adult', action='store_true')
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    work = ROOT/('v2_train_structure_check' if args.structure_check else 'v3_dataset')
    work.mkdir(parents=True, exist_ok=True)
    if args.structure_check:
        cases = ['s0011', 's0344', 's0358', 's0511']
        source = Path('/raid5/xuhd/datasets/ct_back_anatomical_reference_20261005')
        metadata = {r['image_id']: r for r in csv.DictReader((source/'archive_metadata/meta.csv').open(encoding='utf-8-sig'), delimiter=';')}
        roles = [dict(case=case, role='TRAIN_STRUCTURE_CHECK') for case in cases]
        for case in cases:
            path = work/'raw'/case; path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                os.symlink(source/'raw'/case, path)
    else:
        role_freeze = json.loads((ROOT/'SOURCE_ROLE_FREEZE.json').read_text())
        roles = [r for r in role_freeze['rows'] if r['age_years'] is not None and r['age_years'] >= 18]
        if args.cases:
            roles = [r for r in roles if r['case'] in args.cases]
        assert args.all_adult or args.cases
        metadata = {r['image_id']: r for r in csv.DictReader((ROOT/'archive_metadata/meta.csv').open(encoding='utf-8-sig'), delimiter=';')}
        extract_complete(roles, work)
    records = []
    items = [(row, metadata[row['case']], args.resume) for row in roles]
    with ProcessPoolExecutor(max_workers=args.workers, initializer=initialize_worker, initargs=(str(work),)) as pool:
        for record in pool.map(process_case, items):
            records.append(record)
            (work/'CASE_MANIFEST.json').write_text(json.dumps(records, indent=2)+'\n')
            print('field', record['case'], record['role'], 'eligible', record['eligible'], 'levels', sum(record['valid_levels']), flush=True)
    summary = dict(status='SOURCE_PROCESSING_COMPLETE_NOT_MODEL_EVAL', cases=len(records),
                   eligible=sum(r['eligible'] for r in records), levels=LEVELS,
                   role_counts={role:sum(r['role']==role and r['eligible'] for r in records)
                                for role in sorted({r['role'] for r in records})},
                   full_V3_source=not args.structure_check,
                   acquisition_prone_certified=False, independent_patient_ID_available=False,
                   labels_are_not_acupoints=True)
    (work/'DATA_SUMMARY.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
