"""Final private volume includes new query and preserved pilot evidence."""
import json,tarfile,time
from common import W,sha,dump


def main():
    assert json.loads((W/'POST_INTEGRITY.json').read_text())['status']=='PASS'
    files=[]
    for folder in ['code','inputs','fits','evaluation','reports','query_review','pilot_evaluation']:
        files.extend(p for p in (W/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files+=list(W.glob('*.json'))+list(W.glob('*.log'))+list(W.glob('*.npz'))
    path=W/'R52B_PROJECTIVE_DIAGNOSTIC.tar.gz'
    with tarfile.open(path,'w:gz',compresslevel=1) as tar:
        for p in sorted(files):tar.add(p,arcname=str(p.relative_to(W)),recursive=False)
    receipt=dict(scope='final',path=str(path),bytes=path.stat().st_size,sha256=sha(path),files=len(files),time_unix=time.time(),
        source_geometry_dependency='Previous R5_FOCUSED_GEOMETRY.tar, SHA8dde9fd95888ba85f6963e2f97656ede9c4e99a4b07203940e84bc174dee8e36; already backed up218/Windows. New A grids and saved body/Coarse support cache-only replay without original ViT feature files.')
    dump(W/'ARCHIVE_final.json',receipt);print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
