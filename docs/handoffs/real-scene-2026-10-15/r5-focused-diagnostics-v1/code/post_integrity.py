"""Verify the concrete inputs, completed cohort, and cached transforms."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def verify_local(root,official):
    manifest=json.loads((root/'geometry/MANIFEST.json').read_text())
    for row in manifest['files']:
        assert sha(root/'geometry'/row['path'])==row['sha256']
    tasks=manifest['tasks']
    records=[json.loads(p.read_text()) for p in (root/'q1/records').rglob('*.json')]
    expected={(r['dataset'],r['seed'],r['key']) for r in tasks}
    assert len(records)==len(expected)==2706
    assert {(r['dataset'],r['seed'],r['key']) for r in records}==expected
    assert all(r['camera_sum_max_abs_m']<1e-6 for r in records)
    for t in tasks:
        if 'original_record' in t:assert t['original_record']['body_exact_equal']
    rigid=[json.loads(p.read_text()) for p in (root/'rigid/records').glob('*.json')]
    rr=[t for t in tasks if t['dataset']=='real' and t['seed']==11]
    assert len(rr)==len(rigid)==232
    assert {t['key'] for t in rr}=={t['key'] for t in rigid}
    for t in rr:assert sha(official/(t['key']+'.npz'))==t['baseline']['prediction_sha256']
    for r in rigid:
        assert r['historical_Txyz_reproduced']
        with np.load(root/'rigid/transforms'/(r['key']+'.npz')) as z:
            for name in ['matched_translation','matched_rigid']:
                R=z[name+'_R'];np.testing.assert_allclose(R.T@R,np.eye(3),atol=1e-12)
                assert abs(np.linalg.det(R)-1)<1e-12
    summary=json.loads((root/'reports/SUMMARY.json').read_text())
    assert summary['native_root']['status']=='PASS' and len(summary['native_root']['physical_checks'])==400
    return dict(status='PASS',geometry_files_rehashed=len(manifest['files']),
        actual_source_official_files_rehashed=232,Q1_actual_records=2706,rigid_actual_records=232,
        native_parameter_substitutions=400,heldout_fitting=False,training=False,
        full_GPU_timing='DEFERRED_BY_USER',code_files={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')})


def verify_remote(root):
    manifest=json.loads((root/'geometry/MANIFEST.json').read_text())
    checked={}
    for path,expected in manifest['source_sha256'].items():
        actual=sha(Path(path));assert actual==expected,('ORIGINAL_SOURCE_CHANGED',path)
        checked[path]=actual
    native=json.loads((root/'native_root_substitution/MANIFEST.json').read_text())
    asset=Path('/root/autodl-tmp/rgbd_sam3d/checkpoints/official/sam-3d-body-vith/assets/mhr_model.pt')
    assert sha(asset)==native['asset_sha256']
    return dict(status='PASS',original_source_files_rehashed=len(checked),
                source_sha256=checked,MHR_asset_sha256=native['asset_sha256'],
                original_experiment_mutations=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--official',type=Path);p.add_argument('--remote',action='store_true')
    a=p.parse_args();result=verify_remote(a.root) if a.remote else verify_local(a.root,a.official)
    target=a.root/('REMOTE_POST_INTEGRITY.json' if a.remote else 'POST_INTEGRITY.json')
    target.write_text(json.dumps(result,indent=2));print('POST_INTEGRITY_PASS',len(result.get('source_sha256',{})),flush=True)
