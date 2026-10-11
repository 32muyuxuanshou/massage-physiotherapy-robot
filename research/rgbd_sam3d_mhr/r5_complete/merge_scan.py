"""Join independently exported shards; keep every TRAIN/VAL source view."""
import argparse,json,hashlib
from pathlib import Path
def main(a):
    shards=[json.loads((a.root/f'SHARD_{k:02d}.json').read_text()) for k in range(a.shards)]
    assert all(s['status']=='COMPLETE' for s in shards)
    assert len({s['source_manifest_sha256'] for s in shards})==1
    records=sorted([r for s in shards for r in s['records']],key=lambda r:r['sample_id'])
    assert len(records)==3072 and len({r['sample_id'] for r in records})==3072
    assert sum(r['role']=='TRAIN' for r in records)==2304
    assert sum(r['role']=='VAL' for r in records)==768
    for r in records:
        assert hashlib.sha256((a.root/r['cache_file']).read_bytes()).hexdigest()==r['cache_sha256']
    (a.root/'CACHE_MANIFEST.json').write_text(json.dumps(dict(status='SPATIAL_SCAN_COMPLETE',records=records,
        source_manifest_sha256=shards[0]['source_manifest_sha256'],TEST_read=False,camera_B_read=False),indent=2))
    print('SPATIAL_SCAN_FULL_HASH_PASS',len(records),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--shards',type=int,default=2)
    main(p.parse_args())
