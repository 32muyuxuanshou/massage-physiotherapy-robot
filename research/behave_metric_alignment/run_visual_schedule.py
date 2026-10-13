"""Eight independent fixed frame ranges; render actual caches, retain all frames."""
import argparse,json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess,sys,time
from metrics import sha256


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--workers',type=int,default=8)
    p.add_argument('--verify-smoke',action='store_true');a=p.parse_args();root=a.root.resolve()
    rows=json.loads((root/'inputs/INPUT_MANIFEST.json').read_text())['records'];n=len(rows)
    original={f.name:sha256(f) for f in (root/'visualizations').glob('*.jpg')} if a.verify_smoke else {}
    if a.verify_smoke and (n!=6 or len(original)!=36):raise ValueError('Expected complete six-frame serial visualization')
    data=root.parent/'data' if a.verify_smoke else root/'data'
    code=Path(__file__).parent;workers=min(a.workers,n);started=time.time()
    def run(i):
        lo,hi=n*i//workers,n*(i+1)//workers
        with (root/'reports'/f'visual_part{i}.log').open('w') as log:
            subprocess.run([sys.executable,str(code/'visualize_scheduled.py'),'--root',str(root),'--data-root',str(data),
                '--start',str(lo),'--stop',str(hi),'--part',str(i)],check=True,stdout=log,stderr=subprocess.STDOUT)
    with ThreadPoolExecutor(max_workers=workers) as pool:list(pool.map(run,range(workers)))
    allrows=[]
    for i in range(workers):allrows.extend(json.loads((root/'visualizations'/f'VISUALIZATION_MANIFEST.{i}.json').read_text())['records'])
    if len(allrows)!=n*6 or len({r['file'] for r in allrows})!=n*6:raise ValueError('Incomplete actual visual coverage')
    if a.verify_smoke:
        if not all(sha256(root/'visualizations'/name)==value for name,value in original.items()):
            raise ValueError('Serial/parallel rendered JPEG actual SHA changed')
        (root/'reports/PARALLEL_VISUAL_QA.json').write_text(json.dumps(dict(status='PASS',exact_JPEG_SHA_equal=36,workers=workers),indent=2))
    report=dict(status='COMPLETE',records=allrows,panels=len(allrows),expected=n*6,images_private=True,meshes_refitted=False,
                selection='Every fixed frame x all three seeds x Best/Last; no positive-case filtering',workers=workers,elapsed_seconds=time.time()-started)
    (root/'visualizations/VISUALIZATION_MANIFEST.json').write_text(json.dumps(report,indent=2))
    print('ALL_CACHED_VISUALS_COMPLETE',n*6,'seconds',time.time()-started,flush=True)


if __name__=='__main__':main()
