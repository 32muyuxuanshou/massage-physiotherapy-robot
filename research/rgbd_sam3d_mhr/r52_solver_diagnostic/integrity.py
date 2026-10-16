"""Actual start/end source and output identities; no new fitting."""
from concurrent.futures import ThreadPoolExecutor
import json,time
from common import W,G,CFG,sha,dump


def main():
    start=time.monotonic();freeze=json.loads((W/'EXECUTION_FREEZE.json').read_text())
    for p,h in freeze['files'].items():assert sha(W/p)==h,p
    inputs=json.loads((W/'INPUT_FREEZE.json').read_text());expected={}
    for r in inputs['records']:
        expected[r['input']]=r['sha256']
        for p,h in r['sources'].items():
            if p in expected:assert expected[p]==h
            expected[p]=h
    geometry=json.loads((G/'MANIFEST.json').read_text())
    for r in geometry['files']:expected[str(G/r['path'])]=r['sha256']
    rows=[]
    for p in sorted((W/'fits').glob('*.json')):
        r=json.loads(p.read_text());assert set(r['methods'])==set(CFG['methods']);expected[r['compact_prediction']]=r['compact_prediction_sha256']
        e=W/'evaluation'/p.name;report=json.loads(e.read_text());assert report['fit_sha256']==sha(p)
        assert set(report['methods'])==set(CFG['methods']);rows.append(dict(tag=p.stem,fit_sha256=sha(p),evaluation_sha256=sha(e)))
    assert len(rows)==2706
    def check(item):
        p,h=item;assert sha(p)==h,p;return dict(path=p,sha256=h)
    with ThreadPoolExecutor(max_workers=8) as pool:verified=list(pool.map(check,expected.items()))
    dump(W/'POST_INTEGRITY.json',dict(status='PASS',actual_files_verified=len(verified),files=verified,output_records=rows,method_frame_records=2706*len(CFG['methods']),training=False,Camera_B_fit=False,seconds=time.monotonic()-start))
    print('POST_INTEGRITY_PASS',len(verified),flush=True)


if __name__=='__main__':main()
