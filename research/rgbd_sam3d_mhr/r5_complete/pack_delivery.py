"""Stream completed evidence without duplicating a large archive on the data disk."""
import argparse,json,sys,tarfile
from pathlib import Path


def main(a):
    r=a.root
    assert json.loads((r/'POSTPROCESS_LEDGER.json').read_text())['status']=='COMPLETE'
    assert json.loads((r/'POST_INTEGRITY_COMPLETE.json').read_text())['status']=='PASS'
    selected=[]
    if a.kind=='public':
        for directory in ['summary','formal','evaluation','ablations','code_qa']:
            selected += [(p,p.relative_to(r).as_posix()) for p in (r/directory).rglob('*') if p.is_file() and p.suffix in ['.json','.csv','.png']]
        selected += [(p,'visualizations/'+p.name) for p in (r/'visualizations/public').glob('*.jpg')]
        selected += [(r/'visualizations/VISUALIZATION_MANIFEST.json','visualizations/VISUALIZATION_MANIFEST.json')]
        selected += [(p,p.name) for p in r.glob('*.json')]+[(r/'FINAL_REPORT.md','FINAL_REPORT.md')]
    else:
        for name in ['code','formal','screen','evaluation','ablations','code_qa','logs','summary','visualizations','scan_cache','assets']:
            selected += [(r/name,name)]
        selected += [(p,p.name) for p in r.glob('*.json')]+[(r/'FINAL_REPORT.md','FINAL_REPORT.md')]
        paths=json.loads((r/'PATHS.json').read_text());original=Path(paths['official_root'])
        # Include exactly the real A/B frames used, no sealed TEST or extra subjects.
        rows=json.loads((Path(paths['real_cache'])/'CACHE_MANIFEST.json').read_text())['records']
        real_files=sorted({v['file'] for row in rows for name,v in row['views'].items() if name in ['kinect_000','kinect_001']})
        selected += [(original/'datasets/registered_v1'/p,'registered_real/'+p) for p in real_files]
        selected += [(original/'checkpoints/official/sam-3d-body-vith','official_checkpoint'),(original/'external/sam-3d-body','official_source')]
    with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz',compresslevel=1,dereference=True) as tar:
        for path,arc in selected:tar.add(path,arcname=arc)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--kind',choices=['public','private'],required=True);main(p.parse_args())
