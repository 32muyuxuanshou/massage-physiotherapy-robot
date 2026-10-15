"""Restore only existing diagnostic inputs from SHA-verified 218 archives."""
import hashlib
import json
from pathlib import Path
import tarfile
import time

BASE=Path('/raid5/xuhd/rgbd_sam3d')
WORK=BASE/'r5_fine_negative_update_audit_v1'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def run():
    WORK.mkdir(exist_ok=True);receipts=[]
    archives=[('r5_focused_diagnostics_v1/R5_FOCUSED_GEOMETRY.tar','8dde9fd95888ba85f6963e2f97656ede9c4e99a4b07203940e84bc174dee8e36'),
        ('r5_focused_diagnostics_v1/OFFLINE_RESULTS.tar.gz','bfdf9aedec6706ad9023b76a6c2f3274c7b2965e18eecb66915b8e97c871b665')]
    for relative,expected in archives:
        source=BASE/relative;assert sha(source)==expected
        with tarfile.open(source) as tar:tar.extractall(WORK/'previous')
        receipts.append(dict(path=str(source),sha256=expected,status='VERIFIED_REUSED'))
    manifest=json.loads((WORK/'previous/geometry/MANIFEST.json').read_text())
    wanted={}
    for t in manifest['tasks']:
        if t['seed']==11 and t['dataset'] in ['native','real']:
            sub='native_scale_v2' if t['dataset']=='native' else 'humman_development_v1'
            name='cache/'+sub+'/'+t['key']+'.pt';wanted[name]=WORK/name
    assert len(wanted)==632
    source=BASE/'r5_complete_comparison_v1/assets/SPATIAL_INPUT_BACKUP.tar.gz'
    expected='85044a00e3d18302198959fae69cd8bcae1a4292a47f129cdfb0f58cae7b18a1'
    print('VERIFYING_SPATIAL_ARCHIVE',flush=True);assert sha(source)==expected
    records=[];start=time.monotonic()
    with tarfile.open(source,'r|gz') as tar:
        for item in tar:
            if item.name in wanted:
                target=wanted[item.name];target.parent.mkdir(parents=True,exist_ok=True)
                src=tar.extractfile(item);h=hashlib.sha256()
                with target.open('wb') as dst:
                    for b in iter(lambda:src.read(4*1024*1024),b''):dst.write(b);h.update(b)
                records.append(dict(path=str(target),archive_member=item.name,bytes=item.size,sha256=h.hexdigest()))
                if len(records)%50==0:print('RESTORED',len(records),632,round(time.monotonic()-start,1),flush=True)
    assert len(records)==632
    result=dict(status='NATIVE_VAL_HUMMAN_DEVELOPMENT_RESTORED',records=records,
        source_archives=receipts+[dict(path=str(source),sha256=expected)],
        sealed_TEST_read=False,training=False)
    (WORK/'LOCAL_RESTORE_RECEIPT.json').write_text(json.dumps(result,indent=2))
    print('LOCAL_RESTORE_COMPLETE',len(records),flush=True)


if __name__=='__main__':run()
