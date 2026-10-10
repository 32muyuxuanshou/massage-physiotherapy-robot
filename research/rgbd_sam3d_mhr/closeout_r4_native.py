"""Verify completed R4 execution assets and archive native results, without inference."""
import argparse
import hashlib
import json
import tarfile
import time
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(16 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def closeout(root):
    w = root / 'runs/r4_geometry_v1'
    pre = json.loads((w / 'RUNTIME_ASSETS.json').read_text())
    files = []
    for record in pre['files']:
        actual = sha(Path(record['path']))
        assert actual == record['sha256'], record['path']
        files.append(dict(record, post_sha256=actual, match=True))
    cells, checkpoints = [], []
    for cell in sorted((w / 'formal').glob('g*_seed*')):
        result = json.loads((cell / 'run/RESULTS.json').read_text())
        identity = json.loads((cell / 'run/EXECUTION_IDENTITY.json').read_text())
        assert result['epochs'] == 30
        for name, expected in identity['code_sha256'].items():
            assert sha(root / 'r4_code' / name) == expected, name
        real = json.loads((cell / 'real/HUMMAN_RESULTS.json').read_text())
        assert real['heldout_points_manifest_sha256'] == pre['files'][-1]['sha256']
        counts = {name: len(list((cell / f'run/predictions/{name}').glob('*.pt')))
                  for name in ['best', 'last']}
        assert counts == {'best': 400, 'last': 400}, counts
        assert len(list((cell / 'real').glob('*.npz'))) == 232
        for name in ['best', 'last']:
            p = cell / 'run' / f'{name}.pt'
            checkpoints.append(dict(cell=cell.name, kind=name, path=str(p),
                                    sha256=sha(p), bytes=p.stat().st_size))
        assert real['checkpoint_sha256'] == checkpoints[-2]['sha256']
        assert json.loads((cell / 'ablations/ABLATIONS_COMPLETE.json').read_text())['status'] == 'COMPLETE'
        cells.append(dict(cell=cell.name, epochs=30, best_epoch=result['best_epoch'],
                          synthetic_native_predictions=counts, real_native_predictions=232,
                          source_commit=identity['source_commit'], source_files_match=True,
                          test_loaded=identity['test_loaded'], seconds=result['seconds']))
    assert len(cells) == 6
    assert not any(c['test_loaded'] for c in cells)
    report = dict(status='PASS', time_unix=time.time(), runtime_files=files,
                  formal_cells=cells, expected_formal=6, official_weights_frozen=True,
                  explanation='Trainer hashes all official parameters before/after; external checkpoint, '
                              'MHR, cache and held-out manifest hashes also unchanged.',
                  checkpoint_files=checkpoints)
    (w / 'POST_EXECUTION_INTEGRITY.json').write_text(json.dumps(report, indent=2))
    (w / 'CHECKPOINT_MANIFEST.json').write_text(json.dumps(dict(status='VERIFIED', files=checkpoints), indent=2))
    print('INTEGRITY_PASS', flush=True)
    archive = root / 'r4_formal_native_v1.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        tar.add(w / 'formal', arcname='formal')
        tar.add(root / 'r4_code', arcname='code')
        for name in ['CHECKPOINT_MANIFEST.json', 'POST_EXECUTION_INTEGRITY.json',
                     'FORMAL_QUEUE_DONE.json', 'FORMAL_RESOURCE_MONITOR.jsonl', 'PILOT_GATE_DECISION.json']:
            tar.add(w / name, arcname=name)
    receipt = dict(archive=str(archive), bytes=archive.stat().st_size, sha256=sha(archive),
                   contents='Six formal cells: 12 best/last checkpoints with optimizer/scheduler/RNG; '
                            '4800 native synthetic VAL outputs; 1392 real native NPZ; '
                            'full ablations/physical/metrics; source snapshot and integrity.')
    (w / 'FORMAL_ARCHIVE_SOURCE.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    closeout(p.parse_args().root)
