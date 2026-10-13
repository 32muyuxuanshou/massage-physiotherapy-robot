"""Verify the actual cached native predictions, evidence identities and post hashes."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from metrics import sha256


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();root=a.root.resolve()
    config=json.loads((root/'reports/EXPERIMENT_CONFIG.json').read_text())
    freeze=json.loads((root/'reports/MODEL_ASSET_FREEZE.json').read_text())
    ledger=json.loads((root/'EXECUTION_LEDGER.json').read_text())
    if ledger['scope']=='formal':
        for field,path in [('experiment_config_sha256','reports/EXPERIMENT_CONFIG.json'),
                           ('model_asset_freeze_sha256','reports/MODEL_ASSET_FREEZE.json'),
                           ('input_manifest_sha256','inputs/INPUT_MANIFEST.json')]:
            if ledger[field]!=sha256(root/path):raise ValueError('Pre/post execution contract changed '+path)
    for row in freeze['assets']+freeze['checkpoints']+config['source_files']:
        if sha256(row['path'])!=row['sha256']:raise ValueError('POST_EXECUTION_ASSET_CHANGED '+row['path'])
    sys.path[:0]=[config['r5_code'],str(Path(config['r5_code']).parent)]
    from evaluate import BODY_KEYS
    manifest=json.loads((root/'inputs/INPUT_MANIFEST.json').read_text())
    expected={(r['sequence'],r['frame']):r for r in manifest['records']}
    for row in expected.values():
        for field in ['input','reference','heldout']:
            if sha256(row[field+'_file'])!=row[field+'_sha256']:raise ValueError('Frozen data changed')
    prediction_count=0;body_count=0;addition_max=0.
    for seed in [11,23,37]:
        base=json.loads((root/'cache'/f's{seed}'/'CACHE_MANIFEST.json').read_text())
        original={}
        for row in base['records']:
            if sha256(row['prediction_file'])!=row['prediction_sha256']:raise ValueError('Official prediction changed')
            original[row['sequence'],row['frame']]=row
        for mode in ['rgb_only','g1','coarse','full']:
            for ck in ['best','last']:
                report=json.loads((root/'predictions'/f'{mode}_s{seed}_{ck}'/'PREDICTION_MANIFEST.json').read_text())
                if {(r['sequence'],r['frame']) for r in report['records']}!=set(expected):raise ValueError('Incomplete predictions')
                for row in report['records']:
                    if sha256(row['prediction_file'])!=row['prediction_sha256']:raise ValueError('Prediction changed')
                    with np.load(row['prediction_file']) as z:
                        error=float(np.max(np.abs(z['vertices_camera_A']-(z['pred_vertices'][0]+z['pred_cam_t'][0]))))
                        addition_max=max(addition_max,error)
                        if error>1e-6:raise ValueError('Camera translation incorrectly applied')
                        if mode in ['coarse','full']:
                            with np.load(original[row['sequence'],row['frame']]['prediction_file']) as off:
                                if not all(np.array_equal(z[k],off[k]) for k in BODY_KEYS):raise ValueError('Actual Body isolation failed')
                            body_count+=1
                    prediction_count+=1
    actual_count=0
    for file in (root/'evaluation').glob('*/RESULTS.json'):
        for row in json.loads(file.read_text())['records']:
            source=expected[row['sequence'],row['frame']]
            if row['heldout_sha256']!=source['heldout_sha256'] or row['reference_sha256']!=source['reference_sha256']:
                raise ValueError('Unequal evaluation point/reference identity')
            actual_count+=1
    if actual_count!=len(expected)*30:raise ValueError('Incomplete 30-cell evaluation')
    result=dict(status='PASS',frames=len(expected),evaluation_records=actual_count,native_new_predictions=prediction_count,
                actual_exact_body_isolation_predictions=body_count,body_fields=BODY_KEYS,
                max_add_translation_residual_m=addition_max,evidence_identity_equal=True,
                runtime_assets_post_sha_equal=True,model_training=False,HuMMan_sealed_TEST_read=False)
    (root/'reports/POST_EXECUTION_INTEGRITY.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
