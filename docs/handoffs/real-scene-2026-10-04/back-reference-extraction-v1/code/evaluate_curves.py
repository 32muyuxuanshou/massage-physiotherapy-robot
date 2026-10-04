"""Annotation-only evaluator. It never calls the XYZ estimator."""
import argparse, csv, time
from collections import defaultdict
from pathlib import Path
import numpy as np
from run_extraction import PARENT, read, write, sha


def polyline_distance(points, line):
    a, vector = line[:-1], np.diff(line, axis=0)
    length2 = (vector * vector).sum(axis=1)
    keep = length2 > 0; a, vector, length2 = a[keep], vector[keep], length2[keep]
    displacement = points[:, None] - a[None]
    t = np.clip((displacement * vector[None]).sum(axis=2) / length2[None], 0, 1)
    projected = a[None] + t[:, :, None] * vector[None]
    return np.linalg.norm(points[:, None] - projected, axis=2).min(axis=1)


def metrics(values):
    return dict(median=float(np.median(values)), p95=float(np.percentile(values, 95)), max=float(np.max(values)))


def csv_write(path, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def evaluate(root):
    frozen = read(root / 'PREDICTION_FREEZE.json')
    assert sha(root / 'PREDICTION_MANIFEST.json') == frozen['manifest_sha256']
    predictions = read(root / 'PREDICTION_MANIFEST.json'); groups = defaultdict(list)
    for row in predictions:
        if row['status'] == 'COMPLETE': assert sha(row['path']) == row['sha256']
        groups[row['candidate_id']].append(row)
    packets = read(PARENT / 'REFERENCE_PACKET_MANIFEST.json')
    results, point_rows = [], []
    evaluation_started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    for packet in packets:
        assert sha(packet['path']) == packet['sha256']
        reference = np.load(packet['path'])['line_m']
        rows = groups[packet['candidate_id']]
        complete = [r for r in rows if r['status'] == 'COMPLETE']
        curves = {r['method']: np.load(r['path']) for r in complete}
        minimum = max(c['query_y_m'].min() for c in curves.values())
        maximum = min(c['query_y_m'].max() for c in curves.values())
        common = (reference[:, 1] >= minimum) & (reference[:, 1] <= maximum)
        target = reference[common]
        for row in rows:
            base = dict(candidate_id=packet['candidate_id'], scan_id=packet['scan_id'], method=row['method'],
                        status=row['status'], reference_points=len(reference), common_points=len(target),
                        common_coverage=float(common.mean()), source_reference='author_drawn_surface_line',
                        clinical_acupoint_accuracy=False)
            if row['status'] != 'COMPLETE':
                base.update(median_xyz_mm=None, p95_xyz_mm=None, max_xyz_mm=None, median_lateral_mm=None,
                            p95_lateral_mm=None, polyline_median_mm=None)
            else:
                curve = curves[row['method']]
                predicted = np.column_stack([np.interp(target[:, 1], curve['query_y_m'], curve['curve_m'][:, j]) for j in range(3)])
                xyz = np.linalg.norm(predicted - target, axis=1) * 1000
                lateral = np.abs(predicted[:, 0] - target[:, 0]) * 1000
                support = polyline_distance(target, curve['curve_m']) * 1000
                base.update(median_xyz_mm=float(np.median(xyz)), p95_xyz_mm=float(np.percentile(xyz, 95)),
                            max_xyz_mm=float(xyz.max()), median_lateral_mm=float(np.median(lateral)),
                            p95_lateral_mm=float(np.percentile(lateral, 95)), polyline_median_mm=float(np.median(support)))
                for k, index in enumerate(np.flatnonzero(common)):
                    point_rows.append(dict(candidate_id=packet['candidate_id'], scan_id=packet['scan_id'], method=row['method'],
                        reference_index=int(index), reference_y_m=float(target[k, 1]), predicted_x_m=float(predicted[k, 0]),
                        predicted_y_m=float(predicted[k, 1]), predicted_z_m=float(predicted[k, 2]),
                        xyz_mm=float(xyz[k]), lateral_mm=float(lateral[k]), continuous_polyline_mm=float(support[k])))
            results.append(base)
    csv_write(root / 'PER_SCAN_RESULTS.csv', results); csv_write(root / 'PER_REFERENCE_POINT.csv', point_rows)
    summary = {}
    for method in read(root / 'CONFIG.json')['methods']:
        subset = [r for r in results if r['method'] == method and r['status'] == 'COMPLETE']
        summary[method] = dict(scans=len(subset), failures=30-len(subset),
            median_of_scan_median_xyz_mm=float(np.median([r['median_xyz_mm'] for r in subset])),
            median_of_scan_p95_xyz_mm=float(np.median([r['p95_xyz_mm'] for r in subset])),
            median_of_scan_median_lateral_mm=float(np.median([r['median_lateral_mm'] for r in subset])),
            median_common_coverage=float(np.median([r['common_coverage'] for r in subset])),
            minimum_common_coverage=float(min(r['common_coverage'] for r in subset)))
    write(root / 'RESULTS.json', dict(status='COMPLETE', scans=30, records=len(results), point_records=len(point_rows),
          independent_subject_count=None, primary='same-native-Y correspondence on common annotation points',
          reference_scope='author-drawn surface curve; not acupoint/vertebral GT or prone deployment validation', methods=summary))
    for row in predictions:
        if row['status'] == 'COMPLETE': assert sha(row['path']) == row['sha256']
    for row in read(root / 'SOURCE_FREEZE.json'): assert sha(row['path']) == row['sha256']
    write(root / 'EVALUATION_INTEGRITY.json', dict(status='PASS', prediction_complete_before_evaluation=True,
          prediction_completed_at_utc=frozen['completed_at_utc'], evaluation_started_at_utc=evaluation_started,
          prediction_manifest_sha256=frozen['manifest_sha256'], curve_hashes_unchanged=True, source_hashes_unchanged=True,
          estimator_reference_packet_reads=0, shared_reference_point_indices=True))
    print('EVALUATION_COMPLETE', summary, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True)
    evaluate(parser.parse_args().root)
