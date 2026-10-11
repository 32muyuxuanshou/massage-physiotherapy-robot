"""Lossless Torch ZIP-container compression, preserving every tensor byte."""
import argparse,hashlib,json,zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
def worker(path):
    path=Path(path);temp=path.with_suffix('.compact.tmp');before=path.stat().st_size
    with zipfile.ZipFile(path) as source,zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as dest:
        entries=[(i.filename,i.CRC,i.file_size) for i in source.infolist()]
        for item in source.infolist():dest.writestr(item.filename,source.read(item.filename))
    with zipfile.ZipFile(temp) as check:
        assert entries==[(i.filename,i.CRC,i.file_size) for i in check.infolist()]
        assert check.testzip() is None
    temp.replace(path)
    return dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),before_bytes=before,after_bytes=path.stat().st_size)
def main(a):
    # No manifest/weak freeze is exposed until all files and new hashes exist.
    with ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(worker,sorted(a.root.glob('*.pt'))))
    assert len(results)==3072
    hashes={r['file']:r['sha256'] for r in results}
    for p in a.root.glob('SHARD_*.json'):
        manifest=json.loads(p.read_text())
        for r in manifest['records']:r['cache_sha256']=hashes[r['cache_file']]
        manifest['container']='lossless_ZIP_DEFLATE_level1; entry CRC and byte counts exact'
        p.write_text(json.dumps(manifest,indent=2))
    receipt=dict(status='PASS',files=len(results),before_bytes=sum(r['before_bytes'] for r in results),
        after_bytes=sum(r['after_bytes'] for r in results),records=results,
        scientific_tensor_bytes_changed=False,official_reinference=False)
    (a.root/'LOSSLESS_CONTAINER_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
    print('CACHE_CONTAINER_COMPACT_PASS',receipt['before_bytes'],receipt['after_bytes'],flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args())
