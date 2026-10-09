"""Download one officially indexed archive on AutoDL; URLs stay private.

usage: python download_one.py private_job.json
No authentication tokens or signed URLs are written to the public receipt.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request


def main():
    job = json.loads(Path(sys.argv[1]).read_text())
    target = Path(job['destination'])
    partial = target.with_suffix(target.suffix + '.part')
    receipt = target.with_suffix(target.suffix + '.receipt.json')
    start = time.time()
    digest = hashlib.sha256()
    size = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    last = 0
    with urllib.request.urlopen(job['url'], timeout=90) as response, partial.open('wb') as stream:
        while block := response.read(1024 * 1024):
            stream.write(block)
            digest.update(block)
            size += len(block)
            if size-last >= 64*1024*1024:
                print(json.dumps({'file': target.name, 'bytes': size,
                                  'seconds': round(time.time()-start, 1)}), flush=True)
                last = size
    assert size == job['size'], (size, job['size'])
    assert digest.hexdigest() == job['sha256'], 'OFFICIAL_SHA256_MISMATCH'
    partial.rename(target)
    result = dict(status='COMPLETE_VERIFIED', filename=target.name,
                  source_repo='caizhongang/HuMMan', source_revision=job['revision'],
                  source_path=job['source_path'], bytes=size, sha256=digest.hexdigest(),
                  seconds=time.time()-start)
    receipt.write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
