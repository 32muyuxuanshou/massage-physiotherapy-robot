"""Independent actual-file SHA verification after direct transfer/restoration."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time

WORK=Path('/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1')


def verify(row):
    path=Path(row.get('destination',row.get('path')));h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    assert h.hexdigest()==row['sha256'],str(path)
    return dict(path=str(path),sha256=h.hexdigest(),bytes=path.stat().st_size)


if __name__=='__main__':
    start=time.monotonic()
    native=json.loads((WORK/'LOCAL_RESTORE_RECEIPT.json').read_text())['records']
    behave=json.loads((WORK/'BEHAVE_TRANSFER_RECEIPT.json').read_text())['records']
    assert len(native)==632 and len(behave)==810
    with ThreadPoolExecutor(max_workers=8) as pool:records=list(pool.map(verify,native+behave))
    result=dict(status='ALL_1442_ACTUAL_CACHE_FILES_SHA_VERIFIED',records=records,
        total_bytes=sum(r['bytes'] for r in records),seconds=time.monotonic()-start,
        input_groups=dict(native_VAL=400,humman_TRAIN_VAL=232,behave_270_per_seed=810),
        TEST_policy='Native/HuMMan sealed TEST not read; BEHAVE previously consumed fixed official TEST subset',
        download_transport='Direct SFTP, no HTTP proxy or FlClash',new_training=False)
    (WORK/'MIGRATION_RECEIPT.json').write_text(json.dumps(result,indent=2))
    print(result['status'],result['total_bytes'],flush=True)
