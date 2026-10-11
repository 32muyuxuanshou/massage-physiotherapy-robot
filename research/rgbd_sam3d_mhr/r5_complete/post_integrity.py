"""Actual post-run hashes, exposure counts, prediction counts and Body isolation."""
import argparse,hashlib,json
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main(a):
    r=a.root;freeze=json.loads((r/'RUNTIME_ASSET_FREEZE.json').read_text());checks={}
    for key,item in freeze['assets'].items():
        checks[key]=sha(item['path'])==item['sha256'];assert checks[key],('RUNTIME_ASSET_CHANGED',key)
    source=Path('/root/autodl-tmp/rgbd_sam3d/external/sam-3d-body')
    assert {p.relative_to(source).as_posix():sha(p) for p in sorted(source.rglob('*.py'))}==freeze['official_source_sha256']
    runs=list((r/'formal').glob('*/RESULTS.json'));assert len(runs)==21
    cells=[];counts={'native':0,'scan':0,'real':0}
    for file in runs:
        state=json.loads(file.read_text());assert state['epochs_completed']==50
        identity=state['identity']
        for name,expected in identity['training_code_sha256'].items():assert sha(r/'code'/name)==expected,('TRAINING_SOURCE_CHANGED',name)
        assert sha(r/'code/r5_complete/R5_COMPARISON_CONFIG.json')==identity['config_sha256']
        assert sha(r/'PATHS.json')==identity['paths_sha256']
        paths=json.loads((r/'PATHS.json').read_text())
        assert sha(Path(paths['native_cache'])/'CACHE_MANIFEST.json')==identity['native_manifest_sha256']
        assert sha(Path(paths['scan_cache'])/'CACHE_MANIFEST.json')==identity['scan_manifest_sha256']
        assert sha(paths['weak_freeze'])==identity['weak_loss_freeze_sha256']
        curve=json.loads((file.parent/'CURVES.json').read_text())
        assert sum(v['native_samples'] for v in curve)==160000
        assert sum(v['scan_samples'] for v in curve)==46080
        assert all(v['scan_unique_samples']==2304 for v in curve[30:])
        cells.append(file.parent.name)
    for path in sorted((r/'evaluation').glob('*/*/RESULTS.json')):
        if path.parent.name not in counts:continue
        data=json.loads(path.read_text());domain=data['dataset'];assert len(data['records'])=={'native':400,'scan':768,'real':232}[domain]
        for row in data['records']:
            assert sha(row['prediction_file'])==row['prediction_sha256']
            if data['mode'] in ['pooled_mlp','coarse','full']:assert row['body_exact_equal']
        counts[domain]+=len(data['records'])
    assert counts=={'native':17200,'scan':33024,'real':9976}
    gate=json.loads((r/'evaluation/official/real_B/OFFICIAL_TXYZ_REPRODUCTION_GATE.json').read_text());assert gate['status']=='PASS'
    result=dict(status='PASS',runtime_assets=checks,Official_source_exact=True,formal_cells=cells,prediction_counts=counts,
        total_predictions=sum(counts.values()),TEST_read=False,new_model_Txyz=False,
        exposure_per_cell=dict(native=160000,scan=46080),camera_only_Body_exact=True)
    (r/'POST_INTEGRITY_COMPLETE.json').write_text(json.dumps(result,indent=2));print('POST_INTEGRITY_ALL_PASS',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args())
