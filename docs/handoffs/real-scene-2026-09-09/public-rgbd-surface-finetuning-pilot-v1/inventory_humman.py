"""Read-only local HuMMan archive/header and extracted-file inventory. No downloads."""
import csv
import gc
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import py7zr
import cv2

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[3]
DATA = PROJECT / 'AI感知模块/outputs/内部工程证据/2026-09-09_PUBLIC_RGBD_MHR_FITABILITY_SANITY_V1'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def new_sequence():
    return {'rgb': set(), 'depth': defaultdict(set), 'mask': defaultdict(set), 'calibration': False, 'smpl': False}


def add(db, name):
    parts = name.replace('\\', '/').split('/')
    if not parts[0].startswith('p') or '_a' not in parts[0]:
        return
    r = db[parts[0]]
    if parts[-1] == 'cameras.json':
        r['calibration'] = True
    elif parts[-1] == 'smpl_params.npz':
        r['smpl'] = True
    elif len(parts) >= 3 and parts[1] == 'kinect_color' and parts[-1].endswith('.mp4'):
        r['rgb'].add(Path(parts[-1]).stem)
    elif len(parts) == 4 and parts[1] in ('kinect_depth', 'kinect_mask') and parts[-1].endswith('.png'):
        r['depth' if parts[1] == 'kinect_depth' else 'mask'][parts[2]].add(int(Path(parts[-1]).stem))


def summarize(db):
    rows = []
    for seq, r in sorted(db.items()):
        cameras = sorted(r['rgb'] | set(r['depth']) | set(r['mask']))
        coverage = []
        for camera in cameras:
            d, m = r['depth'][camera], r['mask'][camera]
            pairs = d & m
            coverage.append({'camera': camera, 'rgb_video_present': camera in r['rgb'],
                'depth_frames': len(d), 'mask_frames': len(m), 'depth_mask_same_frame_ids': len(pairs),
                'paired_frame_ranges': ranges(pairs),
                'structural_rgbd_mask_pairs': len(pairs) if camera in r['rgb'] and r['calibration'] else 0})
        usable = sum(c['structural_rgbd_mask_pairs'] for c in coverage)
        rows.append({'sequence': seq, 'subject': seq.split('_')[0], 'action': seq.split('_')[1],
            'calibration_present': r['calibration'], 'smpl_present': r['smpl'], 'cameras': coverage,
            'structurally_complete_frame_camera_pairs': usable,
            'structurally_usable': usable > 0})
    return {'sequences': len(rows), 'unique_subjects': len({r['subject'] for r in rows}),
        'unique_actions': len({r['action'] for r in rows}),
        'structurally_usable_subjects': len({r['subject'] for r in rows if r['structurally_usable']}),
        'structurally_usable_sequences': sum(r['structurally_usable'] for r in rows),
        'structurally_usable_actions': len({r['action'] for r in rows if r['structurally_usable']}),
        'camera_ids': sorted({c['camera'] for r in rows for c in r['cameras']}),
        'rgb_videos': sum(len(r['rgb']) for r in db.values()),
        'depth_frames': sum(sum(map(len, r['depth'].values())) for r in db.values()),
        'mask_frames': sum(sum(map(len, r['mask'].values())) for r in db.values()),
        'calibration_sequences': sum(r['calibration'] for r in db.values()),
        'smpl_sequences': sum(r['smpl'] for r in db.values()),
        'structurally_complete_frame_camera_pairs': sum(r['structurally_complete_frame_camera_pairs'] for r in rows),
        'sequence_records': rows}


def ranges(values):
    result = []
    for value in sorted(values):
        if result and value == result[-1][1] + 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def main():
    reports = {r['file']: r for r in read(DATA / 'DOWNLOAD_REPORT.json')['files']}
    db = defaultdict(new_sequence)
    archives = []
    for filename, prior in reports.items():
        path = DATA / 'humman_subset_archives' / filename
        before = set(db)
        with py7zr.SevenZipFile(path, 'r') as archive:
            names = archive.getnames()
            per = defaultdict(new_sequence)
            for name in names:
                add(db, name)
                add(per, name)
            summary = summarize(per)
            archives.append({'path': str(path), 'bytes': path.stat().st_size,
                'size_matches_prior_download_report': path.stat().st_size == prior['bytes'],
                'prior_report_sha256_not_rehashed_this_scan': prior['sha256'],
                'header_readable': True, 'payload_crc_retested': False, 'entry_count': len(names),
                'subjects': sorted({s.split('_')[0] for s in per}),
                'sequences': sorted(per), 'coverage': {k: v for k, v in summary.items() if k != 'sequence_records'}})
        del names, per, summary
        gc.collect()
        print(filename, 'indexed', flush=True)
    packed = summarize(db)
    del db
    extracted = defaultdict(new_sequence)
    for path in (DATA / 'humman_subset').rglob('*'):
        if path.is_file():
            add(extracted, path.relative_to(DATA / 'humman_subset').as_posix())
    unpacked = summarize(extracted)
    rgb_checks = []
    for path in sorted((DATA / 'humman_subset').rglob('*.mp4')):
        video = cv2.VideoCapture(str(path))
        count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        ok, frame = video.read()
        sequence, camera = path.parent.parent.name, path.stem
        paired = extracted[sequence]['depth'][camera] & extracted[sequence]['mask'][camera]
        rgb_checks.append({'path': str(path), 'sequence': sequence, 'camera': camera,
            'reported_frame_count': count, 'first_frame_decodes': bool(ok),
            'all_paired_ids_within_video_count': all(0 <= f < count for f in paired),
            'every_frame_decoded': False})
        video.release()
    meta = list((DATA / 'humman_meta/extracted').rglob('cameras.json'))
    calibrations = []
    for path in meta:
        cameras = read(path)
        calibrations.append({'sequence': path.parent.name, 'camera_keys': sorted(cameras),
            'all_have_K_R_T': all(all(k in value for k in ('K', 'R', 'T')) for value in cameras.values())})
    prior_subjects = sorted({r['subject_id'] for r in read(DATA / 'approved_subset.json')['observations']})
    usable = sorted({r['subject'] for r in packed['sequence_records'] if r['structurally_usable']})
    clean = [s for s in usable if s not in prior_subjects]
    clean.sort(key=lambda s: hashlib.sha256(('humman-pilot-v1-20260909:' + s).encode()).hexdigest())
    nsealed = max(1, len(clean) // 6)
    nval = max(1, len(clean) // 6)
    splits = {'DEV': prior_subjects, 'TRAIN': clean[nsealed+nval:],
              'VAL': clean[nsealed:nsealed+nval], 'SEALED': clean[:nsealed]}
    assert sum(map(len, splits.values())) == len(set(sum(splits.values(), [])))
    action_names = {int(r['Action ID']): r['Name'] for r in csv.DictReader((DATA / 'humman_meta/action_set.csv').open(encoding='utf-8-sig'))}
    for record in packed['sequence_records']:
        record['action_name'] = action_names.get(int(record['action'][1:]), 'unknown')
    result = {'status': 'ARCHIVE_STRUCTURAL_INVENTORY_NOT_TRAINING_READINESS',
        'source_root': str(DATA), 'archives': archives,
        'ignored_partial_old': [{'path': str(p), 'bytes': p.stat().st_size} for p in (DATA / 'humman_subset_archives').glob('*.partial-old')],
        'packed_coverage': packed, 'extracted_coverage': unpacked,
        'extracted_rgb_video_checks': rgb_checks,
        'other_archives_discovered': [{'path': str(p), 'bytes': p.stat().st_size,
             'note': 'Metadata duplicate or reconstruction metadata only; not additional RGBD subject evidence'}
             for p in DATA.rglob('*') if p.is_file() and p.suffix in ('.7z', '.zip') and p.parent.name != 'humman_subset_archives'],
        'metadata_calibration': {'sequence_count': len(calibrations),
            'unique_subject_count': len({r['sequence'].split('_')[0] for r in calibrations}),
            'records': calibrations},
        'counting_definition': 'Structural usable = >=1 identical depth/mask frame ID with RGB video and calibration file. RGB frame count/decode, payload CRC and pixel/geometry QA not established by archive headers.',
        'geometrically_qualified_trainable_subject_count': 'not_established',
        'readiness_blockers': ['Additional subjects remain packed: extract/decode/register and evaluate actual valid-depth torso coverage on server.',
            'RGB video frame counts and alignment with depth/mask frame IDs need verification after extraction.',
            'Current five previously inspected subjects belong to DEV; no honest held-out subject claim for them.',
            'Candidate split requires prior-exposure audit and protocol freeze before inspecting SEALED image pixels.',
            'Clothed public RGBD is surface supervision, not anatomical/medical point ground truth.']}
    (OUT / 'humman_local_inventory.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    candidate = {'status': 'CANDIDATE_NOT_FROZEN', 'unit': 'subject_id; every action/camera/frame of person stays together',
        'seed_rule': 'sha256(humman-pilot-v1-20260909:<subject>), reserve first sixth SEALED and next sixth VAL',
        'subjects': splits, 'counts': {k: len(v) for k, v in splits.items()},
        'known_previously_exposed_DEV': prior_subjects,
        'archive_structural_coverage_only': True, 'prior_exposure_outside_approved_subset': 'not_exhaustively_audited',
        'sequence_assignments': {r['sequence']: next((k for k,v in splits.items() if r['subject'] in v), 'UNASSIGNED_NO_LOCAL_COMPLETE_RGBD') for r in packed['sequence_records']}}
    (OUT / 'humman_subject_split_candidates.json').write_text(json.dumps(candidate, indent=2), encoding='utf-8')
    plan = {'status': 'NO_NEW_PUBLIC_DATA_DOWNLOAD_NEEDED_FOR_INITIAL_STRUCTURAL_PILOT',
        'new_download_destination': 'SERVER_ONLY; no further local downloads',
        'additional_public_archive_bytes_minimum': 0,
        'rationale': 'Select new subjects from already downloaded RGB/depth/mask/calibration intersection first.',
        'server_existing_data_inventory': 'not_checked_by_this_local_read_only_worker',
        'next_actions': ['Audit server existing files/checksums before any transfer.',
            'Transfer only selected missing sequence files if available; otherwise transfer existing local archives then extract on server.',
            'Reserve SEALED subjects by ID now; do not inspect their image content for method tuning.',
            'If extra action/body-type coverage is demonstrated necessary, inspect remote archive headers on server and choose smallest additional depth shard with existing color_part02 coverage.'],
        'existing_remote_archive_index': str(DATA / 'humman_meta/remote_archive_inventory.json'),
        'no_download_executed': True}
    (OUT / 'humman_minimum_download_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    print(json.dumps({'packed': {k:v for k,v in packed.items() if k!='sequence_records'},
                      'extracted': {k:v for k,v in unpacked.items() if k!='sequence_records'}, 'split_counts': candidate['counts']}))


if __name__ == '__main__':
    main()
