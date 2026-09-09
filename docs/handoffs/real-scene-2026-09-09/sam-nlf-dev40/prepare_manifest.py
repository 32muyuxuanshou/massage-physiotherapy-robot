"""Freeze development inputs only; never import or run either model."""
from pathlib import Path
import hashlib
import json
import math
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / 'AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/parquet_runtime'))
import pyarrow.parquet as pq

SEED = 20260908
DATA = BASE / '2026-09-08_COCO2014_DATASET'
COCO20 = BASE / '2026-09-08_COCO20_MHR_COMPARISON/selection.json'
REMOTE = '/raid5/xuhd/sam3d_surface_propagation_20260907'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def iou(a, b):
    a, b = np.asarray(a), np.asarray(b)
    inter = np.maximum(np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2]), 0).prod()
    return float(inter / (np.prod(a[2:] - a[:2]) + np.prod(b[2:] - b[:2]) - inter + 1e-9))


def main():
    selected = read(COCO20)
    assert len(selected) == 20
    by_image = {}
    for ann in read(DATA / 'subset_annotations/person_keypoints_train2014.json')['annotations']:
        by_image.setdefault(ann['image_id'], []).append(ann)
    candidates = []
    for row in pq.read_table(BASE / '2026-09-08_SAM_MHR_DOWNLOAD/matched_existing_images.parquet').to_pylist():
        bb = row['bbox']
        if min(bb[2] - bb[0], bb[3] - bb[1]) < 80 or not row['mhr_valid']:
            continue
        iid = int(Path(row['image']).stem.split('_')[-1])
        matches = []
        for ann in by_image[iid]:
            x, y, w, h = ann['bbox']
            matches.append((iou(bb, [x, y, x+w, y+h]), ann))
        score, ann = max(matches, key=lambda item: item[0])
        if score < .5 or ann['num_keypoints'] < 6 or ann['iscrowd']:
            continue
        row.update(image_id=iid, coco_annotation=ann, coco_bbox_iou=score)
        candidates.append(row)
    used = {r['image'] for r in selected}
    for row in sorted(candidates, key=lambda r: hashlib.sha256(f"{SEED}:{r['image']}:{r['subject_idx']}".encode()).hexdigest()):
        if row['image'] in used:
            continue
        row.update(id=f'C{len(selected)+1:02d}', selection_group='additional_paired_coco')
        selected.append(row)
        used.add(row['image'])
        if len(selected) == 34:
            break
    assert len(selected) == 34
    (OUT / 'inputs').mkdir(exist_ok=True)
    records = []

    def add(identifier, source, remote, bbox, group, provenance, annotation=None, extra=None):
        with Image.open(source) as im:
            w, h = im.size
        assert len(bbox) == 4 and all(math.isfinite(float(v)) for v in bbox)
        assert bbox[2] > bbox[0] and bbox[3] > bbox[1]
        assert bbox[2] > 0 and bbox[3] > 0 and bbox[0] < w and bbox[1] < h
        dest = OUT / 'inputs' / f'{identifier}{source.suffix.lower()}'
        shutil.copyfile(source, dest)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert hashlib.sha256(dest.read_bytes()).hexdigest() == digest
        focal = math.hypot(w, h)
        record = dict(id=identifier, source_local=str(source.resolve()), source_remote=remote,
                      source_remote_status='expected_path_not_verified_on_server_this_run',
                      input_local=str(dest.resolve()), input_relative=dest.relative_to(OUT).as_posix(),
                      bbox_xyxy=bbox, sha256=digest, width=w, height=h,
                      K=[[focal, 0, w/2], [0, focal, h/2], [0, 0, 1]],
                      split='development', group=group, provenance=provenance,
                      identity_independence='unknown', coco17_annotation=annotation,
                      anatomical37_position_labels=None)
        if extra:
            record.update(extra)
        records.append(record)

    for index, row in enumerate(selected):
        add(row['id'], DATA / 'images/train2014' / row['image'],
            '/raid5/xuhd/datasets/coco2014_person_seed20260908/images/train2014/' + row['image'],
            row['bbox'], 'retained_coco20' if index < 20 else 'additional_coco14',
            'COCO2014 image with existing paired SAM/MHR person bbox; existing COCO17 annotation',
            row['coco_annotation'], dict(image_id=row['image_id'], subject_idx=row['subject_idx'],
            coco_bbox_iou=row['coco_bbox_iou'], selection_group=row['selection_group'],
            bbox_provenance='existing paired SAM/MHR bbox',
            original_selection=str(COCO20.resolve()) if index < 20 else None))
        if index < 20:
            assert records[-1]['sha256'] == row['source_sha256']
    for folder, ids, remote_folder, group in [
        ('2026-09-07_PUBLIC_BACK_PILOT', ['B1', 'B2', 'B3', 'B4', 'B5'], 'public_back', 'public_back5'),
        ('2026-09-08_SEATED_AND_ATLAS_AUDIT', ['N1'], 'seated_atlas_audit', 'seated_back1')]:
        sources = {r['id']: r for r in read(BASE / folder / 'sources.json')}
        for identifier in ids:
            case = BASE / folder / identifier
            run = read(case / 'run.json')
            add(identifier, case / 'input.jpg', f'{REMOTE}/{remote_folder}/{identifier}/input.jpg',
                run['bbox'], group, sources[identifier], extra=dict(bbox_provenance=str(case / 'run.json')))
            assert records[-1]['sha256'] == run['source_sha256'] == sources[identifier]['sha256']
    assert len(records) == len({r['id'] for r in records}) == len({r['sha256'] for r in records}) == 40
    protocol = dict(status='DEVELOPMENT_INPUTS_FROZEN_NO_MODEL_RUN', seed=SEED,
        counts=dict(retained_coco20=20, additional_coco14=14, public_back5=5, seated_back1=1, total=40),
        selection='Retain all historical COCO20; sort remaining eligible paired candidates by SHA256(seed:image:subject_idx), take 14 unique images.',
        eligibility='Same as COCO20: valid MHR; bbox dimensions >=80; best COCO bbox IoU >=0.5; >=6 labeled joints; non-crowd.',
        candidate_count=len(candidates), split='All 40 are development images; no validation/test split in this round.',
        identity_independence='unknown; unique image hashes do not imply unique people; B3/B4 provenance names the same person',
        pretraining_overlap='COCO/SAM-source development images; not an unseen test set.',
        controls='Every model receives the same copied original image, fixed bbox_xyxy and K. Any required internal preprocessing must map outputs back to original image coordinates.',
        camera=dict(fx='hypot(width,height)', fy='hypot(width,height)', cx='width/2', cy='height/2', units='pixels', calibrated=False),
        labels='Existing COCO17 annotations are retained for 34 images. No 37-point position labels were created. Prior model predictions are not ground truth.',
        remote_paths='Expected existing server paths only; not verified on server in this preparation run.',
        execution='No model inference or training performed.')
    (OUT / 'manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding='utf-8')
    board = Image.new('RGB', (1600, 1440), (28, 28, 32))
    draw = ImageDraw.Draw(board)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    for i, record in enumerate(records):
        with Image.open(record['input_local']) as raw:
            thumb = raw.convert('RGB')
        thumb.thumbnail((200, 250))
        x, y = i % 8 * 200, i // 8 * 288
        board.paste(thumb, (x + (200-thumb.width)//2, y+34))
        draw.text((x+4, y+5), record['id'] + '  DEV', font=font, fill='white')
    board.save(OUT / 'contact_sheet.jpg', quality=93)
    print(json.dumps(protocol['counts']))


if __name__ == '__main__':
    main()
