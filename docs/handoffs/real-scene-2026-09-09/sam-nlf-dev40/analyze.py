"""Analyze existing predictions and overlays only; no model imports or inference."""
from pathlib import Path
import argparse
import ast
import csv
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

OUT = Path(__file__).resolve().parent
METADATA = OUT.parents[3] / 'AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/sam-3d-body/sam_3d_body/metadata/__init__.py'
COCO = list(range(5, 17))
SMPL = [16, 17, 18, 19, 20, 21, 1, 2, 4, 5, 7, 8]
CAUTION = ('Development images only. Joint definitions across models are not completely equivalent. '
           'These are 2D coarse-joint metrics, not surface or acupoint accuracy. '
           'B1-B5/N1 have no ground truth and receive no scores. Identity independence is unknown. '
           'This development batch is biased toward clothed/sports scenes; lying poses are insufficiently covered, not full coverage.')


def official_mapping(path):
    values = {}
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('MHR70_TO_OPENPOSE', 'OPENPOSE_TO_COCO'):
                    values[target.id] = ast.literal_eval(node.value)
    mapping = [values['MHR70_TO_OPENPOSE'][i] for i in values['OPENPOSE_TO_COCO']]
    assert len(mapping) == 17
    return [mapping[i] for i in COCO]


def compare_image(record, folder, sam_overlay, nlf_overlay):
    tile_w, tile_h, header = 640, 640, 40
    board = Image.new('RGB', (tile_w*3, tile_h+header+32), (28, 28, 32))
    draw = ImageDraw.Draw(board)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 23)
    paths = [OUT / record['input_relative'], folder / sam_overlay, folder / nlf_overlay]
    for i, (label, path) in enumerate(zip(['Original', 'SAM', 'NLF'], paths)):
        with Image.open(path) as source:
            image = ImageOps.contain(source.convert('RGB'), (tile_w, tile_h))
        board.paste(image, (i*tile_w+(tile_w-image.width)//2, header+(tile_h-image.height)//2))
        draw.text((i*tile_w+10, 8), record['id']+'  '+label+'  DEV', font=font, fill='white')
    draw.text((10, header+tile_h+4), 'Development only; clothed/sports bias; insufficient lying-pose coverage; 2D joints do not establish surface/acupoint accuracy.',
              font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19), fill='white')
    board.save(folder / 'comparison.jpg', quality=92)
    return board


def grid(images, columns, tile_width, path):
    tile_height = round(images[0].height * tile_width / images[0].width)
    board = Image.new('RGB', (columns*tile_width, ((len(images)+columns-1)//columns)*tile_height), (28, 28, 32))
    for i, image in enumerate(images):
        board.paste(image.resize((tile_width, tile_height), Image.Resampling.LANCZOS),
                    (i % columns * tile_width, i // columns * tile_height))
    board.save(path, quality=94)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, default=METADATA)
    parser.add_argument('--sam-overlay', default='sam_overlay.jpg')
    parser.add_argument('--nlf-overlay', default='nlf_overlay.jpg')
    args = parser.parse_args()
    sam_indices = official_mapping(args.metadata)
    records = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
    assert len(records) == 40
    rows, all_images, back_images = [], [], []
    for record in records:
        folder = OUT / record['id']
        annotation = record['coco17_annotation']
        if annotation is not None:
            ref = np.asarray(annotation['keypoints'], dtype=float).reshape(17, 3)[COCO]
            valid = ref[:, 2] > 0
            _, _, w, h = annotation['bbox']
            scale = float(np.sqrt(w*h))
            with np.load(folder / 'sam.npz', allow_pickle=False) as data:
                sam = data['pred_keypoints_2d']
            with np.load(folder / 'nlf.npz', allow_pickle=False) as data:
                nlf = data['joints2d']
            assert sam.shape == (70, 2), (record['id'], sam.shape)
            assert nlf.shape == (1, 24, 2), (record['id'], nlf.shape)
            for name, prediction in [('sam', sam[sam_indices]), ('nlf', nlf[0, SMPL])]:
                assert np.isfinite(prediction).all(), (record['id'], name)
                distance = np.linalg.norm(prediction[valid] - ref[valid, :2], axis=1)
                rows.append(dict(id=record['id'], group=record['group'], model=name,
                    labeled_joint_count=int(valid.sum()), normalization_px=scale,
                    mean_error_px=float(distance.mean()) if valid.any() else None,
                    mean_error_normalized=float(distance.mean()/scale) if valid.any() else None,
                    pck05=float((distance/scale < .05).mean()) if valid.any() else None,
                    status='scored' if valid.any() else 'no_labeled_common_joints'))
        else:
            for name in ['sam', 'nlf']:
                rows.append(dict(id=record['id'], group=record['group'], model=name,
                    labeled_joint_count=0, normalization_px=None, mean_error_px=None,
                    mean_error_normalized=None, pck05=None, status='no_ground_truth'))
        comparison = compare_image(record, folder, args.sam_overlay, args.nlf_overlay)
        all_images.append(comparison)
        if record['id'] in ['B1', 'B2', 'B3', 'B4', 'B5', 'N1']:
            back_images.append(comparison)
    with (OUT / 'metrics.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(caution=CAUTION, total_images=len(records),
        ground_truth_images=sum(r['coco17_annotation'] is not None for r in records),
        coco_indices=COCO, smpl_indices=SMPL, sam_indices=sam_indices,
        sam_mapping_source=str(args.metadata.resolve()),
        metric='Per-image mean Euclidean pixel distance divided by sqrt(COCO annotation bbox area); PCK uses distance/scale < 0.05; COCO visibility >0.',
        aggregation='Unweighted macro average over scored images, separately for each model.',
        coordinate_contract='joints2d in original-image pixels. NLF vertices3d are millimeters and are unused by 2D metrics; overlays supplied separately.',
        models={})
    for name in ['sam', 'nlf']:
        scored = [r for r in rows if r['model'] == name and r['status'] == 'scored']
        summary['models'][name] = dict(scored_images=len(scored),
            labeled_joint_count=sum(r['labeled_joint_count'] for r in scored),
            **{key: float(np.mean([r[key] for r in scored])) if scored else None
               for key in ['mean_error_px', 'mean_error_normalized', 'pck05']})
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    grid(all_images, 4, 960, OUT / 'overview.jpg')
    grid(back_images, 2, 1440, OUT / 'back6_comparison.jpg')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
