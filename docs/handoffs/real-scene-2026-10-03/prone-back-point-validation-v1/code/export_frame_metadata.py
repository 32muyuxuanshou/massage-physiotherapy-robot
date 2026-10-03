"""Read the completed frozen run; export JSON only, without model or fitting."""
import argparse
import hashlib
import json
from pathlib import Path


def export(root):
    out = root / 'p2_behave_crossview'
    contract = json.loads((out / 'P2_EXECUTION_CONTRACT.json').read_text())
    rows = []
    for spec in contract['frames']:
        folder = out / 'run' / spec['sequence'] / spec['frame']
        item = dict(spec=spec)
        for filename in ('evaluation.json', 'mesh_metadata.json'):
            source = folder / filename
            item[filename.removesuffix('.json')] = json.loads(source.read_text())
            item[filename + '_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        rows.append(item)
    assert len(rows) == 45
    assert sum(len(r['evaluation']) for r in rows) == 900
    target = out / 'ALL_FRAME_EVALUATIONS_AND_METADATA.json'
    target.write_text(json.dumps(dict(status='CACHE_JSON_ONLY_EXPORT', frames=rows),
                                 ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(frames=len(rows), target=str(target),
                         sha256=hashlib.sha256(target.read_bytes()).hexdigest())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    export(parser.parse_args().root)
