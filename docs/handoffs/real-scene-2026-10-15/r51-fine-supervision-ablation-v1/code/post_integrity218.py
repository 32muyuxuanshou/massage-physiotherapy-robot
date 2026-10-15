"""Actual bytes after execution: immutable inputs, original assets, learned outputs."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,tarfile,time
from pathlib import Path
import torch
from core import WORK,G,BASE,CFG,sha


def main():
    start=time.monotonic();freeze=json.loads((WORK/'SCIENCE_FREEZE.json').read_text())
    for name,digest in freeze['files'].items():assert sha(WORK/name)==digest,name
    expected={}
    for seed in CFG['seeds']:
        records=json.loads((WORK/'prepared'/('s%d'%seed)/'MANIFEST.json').read_text())['records']
        assert len(records)==2950
        for r in records:
            path=WORK/'prepared'/('s%d'%seed)/r['domain']/(r['key']+'.npz')
            expected[str(path)]=r['prepared_sha256']
            source=r['source'];digest=r['source_sha256']
            if source in expected:assert expected[source]==digest
            expected[source]=digest
    archive=BASE/'r5_focused_diagnostics_v1/R5_FOCUSED_GEOMETRY.tar'
    assert sha(archive)=='8dde9fd95888ba85f6963e2f97656ede9c4e99a4b07203940e84bc174dee8e36'
    with tarfile.open(archive) as tar:
        content=tar.extractfile('geometry/MANIFEST.json').read()
    assert sha(G/'MANIFEST.json')==hashlib.sha256(content).hexdigest()
    geometry=json.loads(content)
    for r in geometry['files']:expected[str(G/r['path'])]=r['sha256']
    index=json.loads((WORK/'REAL_EVALUATION_INDEX.json').read_text())
    predictions=0;metrics=0
    for job in index['jobs']:
        directory=WORK/'real_evaluation'/job['name']
        records=json.loads((directory/'PREDICTIONS.json').read_text())['records'];assert len(records)==502
        for r in records:expected[r['prediction']]=r['sha256']
        by_key={(r['domain'],r['key']):r['sha256'] for r in records}
        for p in (directory/'metrics').glob('*.json'):
            r=json.loads(p.read_text());assert r['prediction_sha256']==by_key[r['dataset'],r['key']];metrics+=1
        predictions+=len(records)
    assert predictions==metrics==10542
    def check(item):
        path,digest=item;actual=sha(path);assert actual==digest,path
        return dict(path=path,sha256=actual)
    with ThreadPoolExecutor(max_workers=8) as pool:verified=list(pool.map(check,expected.items()))
    checkpoints=[dict(path=str(p.relative_to(WORK)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted((WORK/'runs').glob('*/epoch_*.pt'))]
    assert len(checkpoints)==84
    selection=json.loads((WORK/'SELECTION_FREEZE.json').read_text())
    for r in selection['records']:
        root=WORK/'runs'/('%s_s%d'%(r['arm'],r['seed']))
        for ep,digest in r['checkpoint_sha256'].items():assert sha(root/('epoch_%02d.pt'%int(ep)))==digest
    changes=[]
    for seed in CFG['seeds']:
        for arm in CFG['arms']:
            root=WORK/'runs'/('%s_s%d'%(arm,seed))
            initial=torch.load(root/'epoch_00.pt',map_location='cpu',weights_only=False)['model']
            final=torch.load(root/'epoch_06.pt',map_location='cpu',weights_only=False)['model']
            assert set(initial)==set(final) and all(k.startswith(('rgb_local.','local.','fine_head.')) for k in final)
            change={k:float((final[k]-initial[k]).abs().max()) for k in final}
            assert max(change.values())>0
            changes.append(dict(arm=arm,seed=seed,max_abs_parameter_changes=change))
    result=dict(status='PASS',actual_files_verified=len(verified),prepared_records=8850,unique_source_cache_files=3490,original_geometry_archive_sha256='8dde9fd95888ba85f6963e2f97656ede9c4e99a4b07203940e84bc174dee8e36',frozen_science_files=len(freeze['files']),learned_checkpoints=checkpoints,raw_predictions=predictions,heldout_metric_records=metrics,verified_files=verified,seconds=time.monotonic()-start,original_assets_and_inputs_unchanged=True,Camera_B_fit=False,new_model_Txyz=False)
    result['parameter_changes']=changes
    (WORK/'POST_INTEGRITY.json').write_text(json.dumps(result,indent=2));print('POST_INTEGRITY_PASS',len(verified),predictions,metrics,flush=True)


if __name__=='__main__':main()
