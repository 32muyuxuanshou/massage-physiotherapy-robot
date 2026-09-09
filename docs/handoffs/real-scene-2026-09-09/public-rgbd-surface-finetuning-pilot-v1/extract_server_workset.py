"""Plan from local headers; execute selective extraction and frame QA on server only."""
import argparse
import gc
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ARCHIVES = Path('/raid5/xuhd/datasets/humman/archives')
WORKSET = Path('/raid5/xuhd/public_rgbd_surface_finetuning_pilot_v1/workset_v1')
CAMERAS = ('kinect_008', 'kinect_009')
PLAN_NAME = 'SERVER_SELECTIVE_EXTRACTION_PLAN_V1.json'
SEVEN_ZIP = Path('/raid5/xuhd/MRC/dataset/tools/7zip/7zz')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def make_plan(root):
    import py7zr
    split_path = root / 'HUMMAN_SUBJECT_SPLIT_V1.json'
    split = read(split_path)
    inventory = read(root / 'HUMMAN_EXISTING_ARCHIVE_INVENTORY_V1.json')
    migration = read(root / 'SERVER_DATA_MIGRATION_V1.json')
    assert migration['status'] == 'COMPLETED_VERIFIED'
    sequences = {r['sequence']:r for r in inventory['packed_coverage']['sequence_records']}
    wanted, observations = set(), []
    for subject, candidate in split['one_sequence_per_subject_candidates'].items():
        if candidate['split'] not in ('DEV', 'TRAIN', 'VAL'):
            continue
        seq = candidate['sequence']
        bycam = {c['camera']:c for c in sequences[seq]['cameras']}
        common = None
        for camera in CAMERAS:
            ids = {f for lo,hi in bycam[camera]['paired_frame_ranges'] for f in range(lo,hi+1)}
            common = ids if common is None else common & ids
        ids = sorted(common)
        frames = sorted({ids[round((len(ids)-1)*q)] for q in (.25,.5,.75)})
        wanted.add(f'{seq}/cameras.json')
        for camera in CAMERAS:
            wanted.add(f'{seq}/kinect_color/{camera}.mp4')
            for frame in frames:
                for modality in ('kinect_depth', 'kinect_mask'):
                    wanted.add(f'{seq}/{modality}/{camera}/{frame:06d}.png')
        observations.append({'subject':subject, 'sequence':seq, 'split':candidate['split'],
            'frame_ids':frames, 'cameras':list(CAMERAS), 'action':candidate['action']})
    listed, found = [], set()
    for archive_row in inventory['archives']:
        if Path(archive_row['path']).name == 'smpl_params.7z':
            continue
        path = Path(archive_row['path'])
        members = []
        with py7zr.SevenZipFile(path, 'r') as archive:
            for item in archive.list():
                if item.filename in wanted:
                    members.append({'path':item.filename, 'uncompressed_bytes':item.uncompressed})
                    found.add(item.filename)
        if members:
            listed.append({'file':path.name, 'server_path':str(ARCHIVES/path.name),
                'sha256':archive_row['prior_report_sha256_not_rehashed_this_scan'],
                'compressed_archive_bytes':archive_row['bytes'], 'members':sorted(members,key=lambda r:r['path']),
                'selected_uncompressed_bytes':sum(r['uncompressed_bytes'] for r in members)})
        gc.collect()
        print('HEADER', path.name, len(members), flush=True)
    assert wanted == found, sorted(wanted-found)
    extracted_bytes = sum(r['selected_uncompressed_bytes'] for r in listed)
    views = sum(len(r['frame_ids'])*len(r['cameras']) for r in observations)
    # RGB dimensions 1920x1080; PNG upper planning allowance is 4 bytes/pixel.
    decoded_budget = views*1920*1080*4
    plan = {'status':'READY_FOR_NONSEALED_SERVER_SELECTIVE_EXTRACTION',
        'server_archive_root':ARCHIVES.as_posix(), 'server_workset_root':WORKSET.as_posix(),
        'source_split_sha256':sha(split_path), 'source_final_split_frozen':split['final_split_frozen'],
        'does_not_freeze_final_split':True, 'selected_subjects':len(observations),
        'counts_by_split':{k:sum(r['split']==k for r in observations) for k in ('DEV','TRAIN','VAL')},
        'sealed_pixels_selected':False, 'sealed_subjects_excluded':split['candidate_subjects']['SEALED'],
        'observations':observations, 'archives':listed, 'selected_member_count':len(found),
        'selected_uncompressed_bytes_exact_from_headers':extracted_bytes,
        'decoded_rgb_png_budget_bytes':decoded_budget,
        'estimated_new_workset_peak_bytes':extracted_bytes+decoded_budget,
        'minimum_free_space_bytes_before_execution':extracted_bytes+decoded_budget+20_000_000_000,
        'space_policy':'Measure server free bytes immediately before execution; retain 20GB operating headroom. 1.8TB is prior reported free space, not current measurement.',
        'solid_archive_warning':'Selected members alone are written, but solid archive decoding can still read/decompress earlier unrelated streams internally. No SEALED member is materialized or inspected.',
        'qa_scope':'Decode chosen RGB frames and verify depth/mask image readability, dtype, nonempty pixels and frame-ID range. Frame-ID synchronization only; no physical timing or registration validity claim.'}
    write(root/PLAN_NAME, plan)
    print(json.dumps({k:plan[k] for k in ('selected_subjects','selected_member_count','selected_uncompressed_bytes_exact_from_headers','estimated_new_workset_peak_bytes')}))


def execute(root):
    import cv2
    import numpy as np
    if sys.platform != 'linux' or not ARCHIVES.is_dir():
        raise RuntimeError('Execution is restricted to the fixed server archive/workset paths')
    plan = read(root/PLAN_NAME)
    assert plan['server_workset_root'] == str(WORKSET)
    assert not plan['sealed_pixels_selected']
    assert all(r['split'] in ('DEV','TRAIN','VAL') for r in plan['observations'])
    assert not (set(r['subject'] for r in plan['observations']) & set(plan['sealed_subjects_excluded']))
    free = shutil.disk_usage(ARCHIVES).free
    if free < plan['minimum_free_space_bytes_before_execution']:
        raise RuntimeError('Insufficient measured free space for selected workset and headroom')
    WORKSET.mkdir(parents=True,exist_ok=True)
    report = {'status':'RUNNING','free_bytes_before':free,'plan_sha256':sha(root/PLAN_NAME),
              'archives':[],'views':[],'sealed_pixels_prepared':False}
    report_path = root/'SERVER_WORKSET_EXTRACTION_QA_V1.json'
    write(report_path,report)
    for row in plan['archives']:
        source=ARCHIVES/row['file']
        # Migration manifest already independently checked these hashes; repeat
        # once here to bind this concrete extraction to the planned archive.
        assert sha(source)==row['sha256'],row['file']
        missing=[]
        for member in row['members']:
            target=WORKSET/member['path']
            assert target.resolve().is_relative_to(WORKSET.resolve())
            if not target.exists() or target.stat().st_size!=member['uncompressed_bytes']:
                missing.append(member['path'])
        if missing:
            if not SEVEN_ZIP.is_file():
                raise RuntimeError(f'Native 7-Zip missing: {SEVEN_ZIP}')
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False,
                                             dir=root, prefix='members_', suffix='.txt') as stream:
                stream.write('\n'.join(missing) + '\n')
                member_list = Path(stream.name)
            try:
                native_env = dict(os.environ)
                native_env['LD_LIBRARY_PATH'] = '/raid5/xuhd/miniconda3/lib'
                subprocess.run([str(SEVEN_ZIP), 'x', str(source), f'-o{WORKSET}',
                                '-y', '-scsUTF-8', f'@{member_list}'], check=True,
                               env=native_env)
            finally:
                member_list.unlink(missing_ok=True)
        for member in row['members']:
            assert (WORKSET/member['path']).stat().st_size==member['uncompressed_bytes']
        report['archives'].append({'file':row['file'],'selected_files':len(row['members']),'newly_extracted':len(missing),'sha256_verified':True})
        write(report_path,report)
        print('EXTRACTED',row['file'],flush=True)
    for observation in plan['observations']:
        seq=observation['sequence']
        calibration=read(WORKSET/seq/'cameras.json')
        for camera in observation['cameras']:
            cap=cv2.VideoCapture(str(WORKSET/seq/'kinect_color'/f'{camera}.mp4'))
            count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            camera_number=camera.split('_')[1]
            assert all(k in calibration for k in (f'kinect_color_{camera_number}',f'kinect_depth_{camera_number}'))
            for frame in observation['frame_ids']:
                assert frame<count
                cap.set(cv2.CAP_PROP_POS_FRAMES,frame)
                ok,rgb=cap.read()
                assert ok,(seq,camera,frame)
                actual_next_frame=int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                assert actual_next_frame==frame+1,(seq,camera,frame,actual_next_frame)
                depth=cv2.imread(str(WORKSET/seq/'kinect_depth'/camera/f'{frame:06d}.png'),cv2.IMREAD_UNCHANGED)
                mask=cv2.imread(str(WORKSET/seq/'kinect_mask'/camera/f'{frame:06d}.png'),cv2.IMREAD_UNCHANGED)
                assert depth is not None and mask is not None
                assert np.count_nonzero(depth)>0 and np.count_nonzero(mask)>0
                target=WORKSET/seq/'selected_rgb'/camera/f'{frame:06d}.png'
                target.parent.mkdir(parents=True,exist_ok=True)
                assert cv2.imwrite(str(target),rgb)
                report['views'].append({'sequence':seq,'subject':observation['subject'],'split':observation['split'],
                    'camera':camera,'frame_id':frame,'rgb_video_frame_count':count,'exact_requested_frame_decode':True,
                    'rgb_shape':list(rgb.shape),'depth_shape':list(depth.shape),'mask_shape':list(mask.shape),
                    'depth_dtype':str(depth.dtype),'mask_dtype':str(mask.dtype),
                    'depth_nonzero_fraction':float(np.count_nonzero(depth)/depth.size),
                    'mask_nonzero_fraction':float(np.count_nonzero(mask)/mask.size)})
            cap.release()
        write(report_path,report)
    report.update(status='DECODE_FRAME_ID_QA_PASS_GEOMETRY_NOT_YET_VALIDATED',free_bytes_after=shutil.disk_usage(WORKSET).free)
    write(report_path,report)
    print('WORKSET_QA_PASS',len(report['views']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan-local',action='store_true')
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    if args.plan_local:
        make_plan(root)
    elif args.execute:
        execute(root)
    else:
        parser.error('Choose --plan-local or --execute')
