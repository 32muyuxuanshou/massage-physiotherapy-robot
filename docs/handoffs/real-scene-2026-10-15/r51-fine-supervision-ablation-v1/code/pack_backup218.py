"""Three explicit private volumes; original caches and old archives stay put."""
import argparse,hashlib,json,tarfile,time
from pathlib import Path
W=Path('/raid5/xuhd/rgbd_sam3d/r51_fine_supervision_ablation_v1')


def main(scope):
    if scope=='training':
        name='TRAINING_CHECKPOINTS.tar.gz'
        files=[p for p in (W/'runs').rglob('*') if p.is_file()]
        files += list((W/'code').glob('*.py'))+list(W.glob('*.json'))
    elif scope=='inputs':
        name='PREPARED_FINE_INPUTS.tar';files=[p for p in (W/'prepared').rglob('*') if p.is_file()]
    else:
        name='R51_FINAL_RESULTS.tar.gz';files=[]
        for folder in ['code','runs','real_evaluation','reports']:
            files += [p for p in (W/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
        files+=list(W.glob('*.json'))+list(W.glob('*.log'))
    path=W/name;files=sorted(set(files))
    options=dict(compresslevel=1) if name.endswith('.gz') else {}
    with tarfile.open(path,'w:gz' if name.endswith('.gz') else 'w',**options) as archive:
        for p in files:archive.add(p,arcname=str(p.relative_to(W)),recursive=False)
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8388608),b''):h.update(block)
    result=dict(scope=scope,path=str(path),bytes=path.stat().st_size,sha256=h.hexdigest(),files=len(files),time_unix=time.time())
    (W/('ARCHIVE_'+scope+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scope',choices=['training','inputs','final'],required=True);main(p.parse_args().scope)
