"""Finish the same authorized ZIP with immutable prefixes and shorter ranges.

Concrete performance correction: one original long connection transferred only
~0.5MB/s. The original four-prefix download must be stopped before this starts.
No dataset/file/byte contract changes; final author MD5 is mandatory.
"""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from acquire_full_v3 import ROOT, URL, BYTES, MD5, PARTS


def chunk_one(item):
    path = ROOT/'download_chunks'/('chunk_'+str(item['id']))
    size = item['end']-item['start']+1
    existing = path.stat().st_size if path.exists() else 0
    assert existing <= size
    if existing == size:
        return path
    start = item['start']+existing
    with requests.get(URL, headers={'Range': f"bytes={start}-{item['end']}", 'Accept-Encoding': 'identity'},
                      stream=True, timeout=(30, 180)) as response:
        response.raise_for_status(); assert response.status_code == 206
        assert response.headers['Content-Range'] == f"bytes {start}-{item['end']}/{BYTES}"
        last = time.time()
        with path.open('ab') as f:
            for block in response.iter_content(1024*1024):
                f.write(block)
                if time.time()-last > 45:
                    print('chunk', item['id'], f.tell(), 'of', size, flush=True); last=time.time()
    assert path.stat().st_size == size
    print('chunk_complete', item['id'], size, flush=True)
    return path


def main():
    start = time.time(); (ROOT/'download_chunks').mkdir(exist_ok=True)
    plan_path = ROOT/'RESIDUAL_DOWNLOAD_PLAN.json'
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        prefixes, chunks = [], []
        for i in range(PARTS):
            begin, end = BYTES*i//PARTS, BYTES*(i+1)//PARTS
            path = ROOT/'download_parts'/('part'+str(i)); count=path.stat().st_size
            assert count <= end-begin
            prefixes.append(dict(part=i, bytes=count, start=begin))
            for offset in range(begin+count, end, 512*1024*1024):
                chunks.append(dict(id=len(chunks), part=i, start=offset, end=min(offset+512*1024*1024,end)-1))
        plan = dict(prefixes=prefixes, chunks=chunks, bytes=BYTES, url=URL, author_md5=MD5)
        plan_path.write_text(json.dumps(plan, indent=2)+'\n')
    print('prefix_bytes', sum(p['bytes'] for p in plan['prefixes']), 'chunks',len(plan['chunks']), flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(chunk_one, plan['chunks']))
    md5=hashlib.md5(); sha=hashlib.sha256(); dest=ROOT/'Totalsegmentator_dataset_v300.zip'
    with dest.open('wb') as output:
        for prefix in plan['prefixes']:
            path=ROOT/'download_parts'/('part'+str(prefix['part']))
            assert path.stat().st_size == prefix['bytes']
            paths=[path]+[ROOT/'download_chunks'/('chunk_'+str(c['id'])) for c in plan['chunks'] if c['part']==prefix['part']]
            for part in paths:
                with part.open('rb') as source:
                    for block in iter(lambda:source.read(4*1024*1024),b''):
                        output.write(block);md5.update(block);sha.update(block)
    assert dest.stat().st_size == BYTES and md5.hexdigest() == MD5
    result=dict(status='PASS', filename=dest.name, bytes=BYTES, author_md5=MD5, actual_md5=md5.hexdigest(),
                sha256=sha.hexdigest(), seconds_after_residual_restart=time.time()-start,
                source=URL, license='CC-BY-4.0', advertised_CT_images=1939,
                residual_plan=plan_path.name)
    (ROOT/'DOWNLOAD_RESULT.json').write_text(json.dumps(result, indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
