"""Save all estimates before opening any marker or surface-line packet."""
import argparse, csv, hashlib, importlib.util, json, time
from pathlib import Path
import numpy as np
from extract_geometry import extract

PARENT = Path('/raid5/xuhd/datasets/real_back_reference_qualification_v1_20261004')
SOURCE = Path('/raid5/xuhd/datasets/back_prone_acquisition_20261003/pcdare_35f7a1d9')
SCAN_INDEX = Path('/raid5/xuhd/datasets/prone_back_point_validation_20261003/p3_data_qualification/SCAN_REFERENCE_BINDING.csv')
READER = Path('/raid5/xuhd/datasets/back_prone_acquisition_20261003/back-data-acquisition-v1/code/audit_acquired_assets.py')


def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((json.dumps(value, indent=2, allow_nan=False) + '\n').encode('utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def reader():
    spec = importlib.util.spec_from_file_location('ply_source_reader', READER)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.read_ply


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(); root = args.root; config = read(root / 'CONFIG.json'); start = time.time()
    packets = read(PARENT / 'REFERENCE_PACKET_MANIFEST.json')
    scans = {r['scan_id']: r for r in csv.DictReader(SCAN_INDEX.open())}
    inputs = [PARENT / 'REFERENCE_PACKET_MANIFEST.json', SCAN_INDEX, READER, root / 'CONFIG.json', root / 'PROTOCOL.md', *(root / 'code').glob('*.py')]
    inputs += [SOURCE / scans[p['scan_id']]['path'] for p in packets]
    freeze = [dict(path=str(p), sha256=sha(p)) for p in inputs]
    write(root / 'SOURCE_FREEZE.json', freeze)
    load = reader(); output = []; (root / 'curves').mkdir(exist_ok=True); (root / 'grids').mkdir(exist_ok=True)
    for packet in packets:
        source = SOURCE / scans[packet['scan_id']]['path']; points, columns = load(source)
        assert sha(source) == packet['scan_sha256']
        predictions, grid = extract(points, config)
        grid_path = root / 'grids' / (packet['candidate_id'] + '.npz'); np.savez_compressed(grid_path, **grid)
        for name in config['methods']:
            estimate = predictions[name]
            row = dict(candidate_id=packet['candidate_id'], scan_id=packet['scan_id'], method=name,
                       status=estimate['status'], scan_sha256=sha(source), input_columns=columns,
                       annotation_read_by_estimator=False)
            if estimate['status'] == 'COMPLETE':
                path = root / 'curves' / (packet['candidate_id'] + '_' + name + '.npz')
                np.savez_compressed(path, **{k: v for k, v in estimate.items() if k != 'status'})
                row.update(path=str(path), sha256=sha(path), curve_points=len(estimate['curve_m']),
                           xy_snap_max_mm=float(np.max(estimate['xy_snap_distance_m']) * 1000))
            output.append(row)
        print('EXTRACTED', packet['scan_id'], [predictions[n]['status'] for n in config['methods']], flush=True)
    write(root / 'PREDICTION_MANIFEST.json', output)
    write(root / 'PREDICTION_FREEZE.json', dict(completed_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
          manifest_sha256=sha(root / 'PREDICTION_MANIFEST.json'), config_sha256=sha(root / 'CONFIG.json'),
          outputs=output, annotation_packets_opened=0))
    for r in freeze: assert sha(r['path']) == r['sha256']
    write(root / 'EXTRACTION_LEDGER.json', dict(status='COMPLETE', scans=len(packets), method_records=len(output),
          curves=sum(r['status'] == 'COMPLETE' for r in output), seconds=time.time() - start,
          sam_inference=0, mesh_fits=0, training=0, source_unchanged=True))


if __name__ == '__main__': main()
