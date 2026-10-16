"""One private final volume, before its external backup receipt."""
import tarfile,time,json
from common import W,sha,dump


def main():
    assert json.loads((W/'POST_INTEGRITY.json').read_text())['status']=='PASS'
    files=[]
    for folder in ['code','inputs','fits','evaluation','reports']:
        files.extend(p for p in (W/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files+=list(W.glob('*.json'))+list(W.glob('*.log'))
    path=W/'R52_SOLVER_DIAGNOSTIC.tar.gz'
    with tarfile.open(path,'w:gz',compresslevel=1) as tar:
        for p in sorted(files):tar.add(p,arcname=str(p.relative_to(W)),recursive=False)
    receipt=dict(scope='final',path=str(path),bytes=path.stat().st_size,sha256=sha(path),files=len(files),time_unix=time.time())
    dump(W/'ARCHIVE_final.json',receipt);print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
