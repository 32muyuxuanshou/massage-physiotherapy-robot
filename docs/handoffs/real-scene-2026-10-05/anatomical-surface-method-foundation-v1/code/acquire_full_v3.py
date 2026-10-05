"""Authorized server-only official V3 acquisition with author MD5 verification."""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path('/raid5/xuhd/datasets/anatomical_surface_method_foundation_20261005')
URL = 'https://zenodo.org/api/records/22688904/files/Totalsegmentator_dataset_v300.zip/content'
BYTES = 37415622057
MD5 = '0728beea76475e92cdb3160e228265d1'
PARTS = 4


def one(i):
    start = BYTES*i//PARTS; end = BYTES*(i+1)//PARTS-1
    dest = ROOT/'download_parts'/('part'+str(i)); existing = dest.stat().st_size if dest.exists() else 0
    assert existing <= end-start+1
    if existing == end-start+1: return dest
    response = requests.get(URL, headers={'Range': f'bytes={start+existing}-{end}', 'Accept-Encoding': 'identity'}, stream=True, timeout=(30, 180))
    response.raise_for_status(); assert response.status_code == 206
    assert response.headers['Content-Range'] == f'bytes {start+existing}-{end}/{BYTES}'
    last = time.time()
    with dest.open('ab') as f:
        for block in response.iter_content(1024*1024):
            f.write(block)
            if time.time()-last > 45:
                print('part', i, 'bytes', f.tell(), 'of', end-start+1, flush=True); last = time.time()
    response.close(); assert dest.stat().st_size == end-start+1
    print('part_complete', i, dest.stat().st_size, flush=True); return dest


if __name__ == '__main__':
    start = time.time(); (ROOT/'download_parts').mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=PARTS) as pool:
        files = list(pool.map(one, range(PARTS)))
    dest = ROOT/'Totalsegmentator_dataset_v300.zip'; md5 = hashlib.md5(); sha = hashlib.sha256()
    with dest.open('wb') as f:
        for path in files:
            with path.open('rb') as part:
                for block in iter(lambda: part.read(4*1024*1024), b''):
                    f.write(block); md5.update(block); sha.update(block)
    assert dest.stat().st_size == BYTES and md5.hexdigest() == MD5
    receipt = dict(status='PASS', filename=dest.name, bytes=BYTES, author_md5=MD5,
                   actual_md5=md5.hexdigest(), sha256=sha.hexdigest(), seconds=time.time()-start,
                   source=URL, license='CC-BY-4.0', advertised_CT_images=1939)
    (ROOT/'DOWNLOAD_RESULT.json').write_text(json.dumps(receipt, indent=2)+'\n'); print(json.dumps(receipt), flush=True)
