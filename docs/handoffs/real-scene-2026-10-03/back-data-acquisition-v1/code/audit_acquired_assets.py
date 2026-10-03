import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path('/raid5/xuhd/datasets/back_prone_acquisition_20261003')
OUT = ROOT / 'quality_audit'
OUT.mkdir(exist_ok=True)


def read_ply(path):
    types = {'char': 'i1', 'uchar': 'u1', 'short': 'i2', 'ushort': 'u2',
             'int': 'i4', 'uint': 'u4', 'float': 'f4', 'double': 'f8'}
    with path.open('rb') as stream:
        assert stream.readline().strip() == b'ply'
        fields = []
        vertex = False
        while True:
            line = stream.readline().decode('ascii').strip()
            if line.startswith('format '):
                fmt = line.split()[1]
            elif line.startswith('element '):
                vertex = line.split()[1] == 'vertex'
                if vertex:
                    count = int(line.split()[2])
            elif line.startswith('property ') and vertex:
                _, typ, name = line.split()
                fields.append((name, typ))
            elif line == 'end_header':
                break
        if fmt == 'ascii':
            columns = [name for name, _ in fields]
            values = np.loadtxt(stream, max_rows=count, usecols=[columns.index(key) for key in ('x', 'y', 'z')], ndmin=2)
        else:
            assert fmt == 'binary_little_endian', fmt
            dtype = np.dtype([(name, '<' + types[typ]) for name, typ in fields])
            values = np.fromfile(stream, dtype=dtype, count=count)
            values = np.column_stack([values[key] for key in ('x', 'y', 'z')])
        assert len(values) == count
        return values.astype(np.float64), [name for name, _ in fields]


def audit_pcdare():
    root = ROOT / 'pcdare_35f7a1d9'
    rows = []
    example_points = []
    for path in sorted(root.rglob('*.ply')):
        points, columns = read_ply(path)
        finite = np.isfinite(points).all(axis=1)
        good = points[finite]
        raw = '/Output/' not in path.as_posix()
        row = {'path': str(path.relative_to(root)), 'vertices': len(points),
               'nonfinite_vertices': int((~finite).sum()), 'columns': columns,
               'bbox_min_native': good.min(axis=0).tolist(), 'bbox_max_native': good.max(axis=0).tolist(),
               'bbox_extent_native': np.ptp(good, axis=0).tolist(),
               'derived_output_path': not raw,
               'units': 'Native coordinates retained; per-file unit/annotation binding not yet approved'}
        rows.append(row)
        if raw:
            example_points.append((row['path'], good))
    json_keys = Counter()
    pc_marker_files = pc_line_files = 0
    for path in root.rglob('*.json'):
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            json_keys.update(data.keys())
            pc_marker_files += int(bool(data.get('pcMarkers')))
            pc_line_files += int(bool(data.get('pcLinePts')))
    report = {'status': 'POINTCLOUD_AND_JSON_DECODE_PASS', 'ply_count': len(rows),
              'non_output_ply_count': sum(not row['derived_output_path'] for row in rows),
              'output_ply_count': sum(row['derived_output_path'] for row in rows),
              'nonfinite_vertices': sum(row['nonfinite_vertices'] for row in rows),
              'marker_json_files': pc_marker_files, 'line_json_files': pc_line_files,
              'json_top_level_field_counts': dict(json_keys),
              'scope': 'Real back-surface support data; not prone RGB-D or acupoint truth; file counts are not subject counts',
              'files': rows}
    (OUT / 'PCDARE_STRUCTURE_AUDIT.json').write_text(json.dumps(report, indent=2))

    # PCA is a display coordinate system only, with no claimed anatomy/camera geometry.
    canvas = Image.new('RGB', (1200, 960), 'white')
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 8), 'PCdare / Kaiser et al. / CC BY-NC-SA 4.0 -- PCA displays, not RGB camera images', fill='black')
    indices = np.linspace(0, len(example_points) - 1, 12).astype(int)
    for tile_index, index in enumerate(indices):
        _, points = example_points[index]
        points = points[::max(1, len(points) // 14000)]
        centered = points - points.mean(axis=0)
        _, _, basis = np.linalg.svd(centered, full_matrices=False)
        display = centered @ basis.T
        span = np.ptp(display[:, :2], axis=0)
        scale = min(260 / span[0], 255 / span[1])
        xy = (display[:, :2] - display[:, :2].min(axis=0)) * scale
        order = np.argsort(display[:, 2])
        x0, y0 = (tile_index % 4) * 300 + 15, (tile_index // 4) * 310 + 35
        depth = display[:, 2]
        colors = np.clip((depth - depth.min()) / max(np.ptp(depth), 1e-12), 0, 1)
        for point_index in order:
            value = colors[point_index]
            color = (int(45 + 160 * value), int(80 + 130 * value), int(225 - 100 * value))
            draw.point((int(x0 + xy[point_index, 0]), int(y0 + xy[point_index, 1])), fill=color)
        draw.text((x0, y0 + 270), f'Native scan {index:03d}; PCA axes only', fill='black')
    canvas.save(OUT / 'pcdare_surface_contact.jpg', quality=91)
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}), flush=True)


def audit_dmd():
    root = ROOT / 'dmd_bak/historical_v1_quality_audit'
    manifest = json.loads((root / 'DOWNLOAD_AUDIT.json').read_text())
    rows = []
    label_counts = Counter()
    labels_per_image = Counter()
    for index, record in enumerate(manifest['records']):
        image_file, annotation_file = record['files']
        annotation = json.loads(Path(annotation_file['path']).read_text())
        with Image.open(image_file['path']) as image:
            image.load()
            width, height = image.size
        point_shapes = [row for row in annotation.get('shapes', []) if row.get('shape_type') == 'point']
        counts = Counter(row['label'] for row in point_shapes)
        label_counts.update(counts)
        labels_per_image.update(counts.keys())
        outside = sum(not (0 <= float(point[0]) < width and 0 <= float(point[1]) < height)
                      for shape in annotation.get('shapes', []) for point in shape['points'])
        rows.append({'sample_id': f'dmd_audit_{index:03d}', 'image_path': image_file['path'],
                     'annotation_path': annotation_file['path'], 'image_sha256': image_file['sha256'],
                     'image_size': [width, height],
                     'annotation_size_matches': [width, height] == [annotation.get('imageWidth'), annotation.get('imageHeight')],
                     'point_count': len(point_shapes), 'point_label_counts': dict(counts),
                     'points_outside_image': outside,
                     'imagePath_basename_matches': Path(annotation.get('imagePath', '')).name == Path(image_file['path']).name})
    duplicates = len(rows) - len({row['image_sha256'] for row in rows})
    report = {'status': 'HISTORICAL_IMAGES_DECODED_LABELS_QUARANTINED', 'pair_count': len(rows),
              'directory_proxies_not_verified_subjects': manifest['directory_proxies'],
              'dimension_mismatch_count': sum(not row['annotation_size_matches'] for row in rows),
              'images_with_outside_points': sum(row['points_outside_image'] > 0 for row in rows),
              'exact_duplicate_images': duplicates, 'point_count_histogram': dict(Counter(row['point_count'] for row in rows)),
              'label_instance_counts': dict(label_counts), 'label_image_counts': dict(labels_per_image),
              'imagePath_basename_mismatch_count': sum(not row['imagePath_basename_matches'] for row in rows),
              'limits': ['Version 1 withdrawn for collection/annotation quality review',
                         'No sensor depth, calibrated 3D coordinates or verified subject-level split established',
                         'Repeated raw labels need anatomical definition before any DMD37 mapping',
                         'Source point markings/label leakage and prone coverage require visual review'], 'files': rows}
    (OUT / 'DMD_PILOT_STRUCTURE_AUDIT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    for page in range((len(rows) + 5) // 6):
        canvas = Image.new('RGB', (1240, 1440), 'white')
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 8), f'DMD-BAK archived V1 quality audit / page {page + 1} / raw | supplied labels (NO inference)', fill='black')
        for position, row in enumerate(rows[page * 6:page * 6 + 6]):
            annotation = json.loads(Path(row['annotation_path']).read_text())
            raw = Image.open(row['image_path']).convert('RGB')
            annotated = raw.copy()
            painter = ImageDraw.Draw(annotated)
            radius = max(3, raw.width // 170)
            for shape in annotation.get('shapes', []):
                if shape.get('shape_type') == 'point':
                    x, y = shape['points'][0]
                    painter.ellipse((x - radius, y - radius, x + radius, y + radius), outline='yellow', width=max(2, radius // 2))
            x0, y0 = (position % 2) * 620, (position // 2) * 465 + 30
            for offset, image in enumerate((raw, annotated)):
                thumb = ImageOps.contain(image, (300, 425))
                canvas.paste(thumb, (x0 + offset * 310 + (300 - thumb.width) // 2, y0))
            draw.text((x0 + 8, y0 + 430), f"{row['sample_id']} / {row['point_count']} supplied points", fill='black')
        canvas.save(OUT / f'dmd_raw_labels_contact_{page + 1:02d}.jpg', quality=89)
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    audit_pcdare()
    audit_dmd()
