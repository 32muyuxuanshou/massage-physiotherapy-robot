"""Export only the historical 232 development inputs needed for cached R4.1.

Run on the original data host. No inference, regenerated data, or TEST reads.
The compact A array preserves the original frozen sample values and ordering.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

import numpy as np


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main(root, out):
    rows = json.loads((root/'datasets/cache/humman_development_v1/CACHE_MANIFEST.json').read_text())['records']
    r31 = root/'runs/r31_diagnosis_pilot_v1'
    indices = json.loads((r31/'txyz/CAMERA_A_FIT_INDICES.json').read_text())
    heldout = json.loads((root/'datasets/heldout/humman_r3_k1_v1/MANIFEST.json').read_text())
    visual = json.loads((r31/'pilot_visuals/VISUALIZATION_MANIFEST.json').read_text())
    selected = {(x['sequence'], x['frame']) for x in visual['records']}
    assert len(rows) == 232 and all(r['role'] in ['TRAIN', 'VAL'] for r in rows)
    fit = {x['file']: x for x in indices}
    obs = {Path(x['file']).stem: x for x in heldout['records']}
    old_official = {Path(x['file']).stem: x for x in json.loads((r31/'txyz/CHEAP_TXYZ_COMPARISON.json').read_text())['records'] if x['method']=='official'}
    out.mkdir(parents=True, exist_ok=False)
    for name in ['inputs', 'official', 'rgb']:
        (out/name).mkdir()
    records = []
    for i, row in enumerate(rows):
        key = f"{row['sequence']}_{row['frame']:06d}"
        paths = {k: root/'datasets/registered_v1'/row['views'][k]['file'] for k in ['kinect_000', 'kinect_001']}
        hashes = {k: sha(p) for k, p in paths.items()}
        assert hashes['kinect_000'] == fit[key]['source_sha256'] == row['views']['kinect_000']['sha256']
        assert hashes['kinect_001'] == obs[key]['source_sha256'] == row['views']['kinect_001']['sha256']
        with np.load(paths['kinect_000']) as a, np.load(paths['kinect_001']) as b:
            ix = np.asarray(fit[key]['indices'], np.int64)
            sampled = a['points_color'][ix]
            assert len(sampled) <= 5000 and np.isfinite(sampled).all()
            np.savez_compressed(out/'inputs'/(key+'.npz'), points_camera_A=sampled, source_indices=ix,
                **{prefix+'_'+k: z[k] for prefix,z in [('A',a),('B',b)] for k in ['K','R','T']})
            if (row['sequence'], row['frame']) in selected:
                # Lossless original RGB, not a re-render or a resized camera input.
                from PIL import Image
                for prefix,z in [('A',a),('B',b)]:
                    Image.fromarray(z['rgb']).save(out/'rgb'/f'{key}_{prefix}.png')
        source = root/'runs/r3_multiseed_v1/real/official'/(key+'.npz')
        shutil.copy2(source, out/'official'/source.name)
        old = old_official[key]
        assert sha(source) == old['input_mesh_sha256']
        records.append(dict(key=key, identity=row['identity'], role=row['role'], sequence=row['sequence'], frame=row['frame'],
            source_hashes=hashes, compact_sha256=sha(out/'inputs'/(key+'.npz')), official_sha256=sha(source),
            fit_points=len(sampled), heldout_sha256=obs[key]['sample_sha256']))
        if i % 40 == 0: print('EXPORT',i+1,'/232',flush=True)
    shutil.copy2(root/'runs/r3_multiseed_v1/real/official/faces.npy', out/'official/faces.npy')
    shutil.copy2(r31/'pilot_visuals/VISUALIZATION_MANIFEST.json', out/'VISUAL_SELECTION.json')
    execution = dict(status='ORIGINAL_DEVELOPMENT_ASSETS_VERIFIED',records=records,test_read=False,
        compact_contract='Original Camera A frozen indices in original order; only packaging changed, no re-registration or sampling.',
        checkpoint_receipts=[])
    for mode in ['g0','g1']:
        for seed in [11,23,37]:
            cell=root/f'runs/r4_geometry_v1/formal/{mode}_seed{seed}'
            result=json.loads((cell/'real/HUMMAN_RESULTS.json').read_text())
            ck=cell/'run/best.pt'
            actual=sha(ck)
            assert actual==result['checkpoint_sha256']
            execution['checkpoint_receipts'].append(dict(cell=f'{mode}_seed{seed}',best_checkpoint_sha256=actual,
                predictions_sha256={key:sha(cell/'real'/(key+'.npz')) for key in fit}))
    (out/'SOURCE_RECEIPT.json').write_text(json.dumps(execution,indent=2))
    archive=out.with_suffix('.tar.gz')
    with tarfile.open(archive,'w:gz') as t:
        t.add(out,arcname='original_assets')
    receipt=dict(archive=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),frames=len(records),test_read=False)
    (out.parent/'ORIGINAL_ASSET_ARCHIVE_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
    print('EXPORT_COMPLETE',json.dumps(receipt),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root,a.out)
