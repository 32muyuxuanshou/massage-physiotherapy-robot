"""Immutable epoch checkpoints for independent transfer during the long run."""
import argparse,hashlib,json,os,time
from pathlib import Path
import torch
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(a):
    r=a.root;out=r/'checkpoint_snapshots';out.mkdir(exist_ok=True);manifest=out/'MANIFEST.json'
    records=json.loads(manifest.read_text())['records'] if manifest.exists() else []
    seen={x['cell']:x['observed_epoch'] for x in records}
    while True:
        for cell in sorted((r/'formal').glob('*')):
            source=cell/'last.pt'
            if not source.exists():continue
            temporary=out/(cell.name+'.tmp.pt');os.link(source,temporary)
            state=torch.load(temporary,map_location='cpu',weights_only=False);epoch=state['epoch']
            if epoch<seen.get(cell.name,0)+5 and not ((cell/'RESULTS.json').exists() and epoch>seen.get(cell.name,0)):
                temporary.unlink();continue
            target=out/f'{cell.name}_e{epoch:02d}_last.pt';temporary.replace(target)
            best=out/f'{cell.name}_e{epoch:02d}_best.pt';os.link(cell/'best.pt',best)
            copied=[]
            for p in [target,best]:copied.append(dict(file=p.name,bytes=p.stat().st_size,sha256=sha(p)))
            item=dict(cell=cell.name,observed_epoch=epoch,files=copied,time=time.time())
            records.append(item);seen[cell.name]=epoch
            temp=manifest.with_suffix('.tmp.json');temp.write_text(json.dumps(dict(status='SNAPSHOTS_AVAILABLE',records=records),indent=2));temp.replace(manifest)
            print('CHECKPOINT_SNAPSHOT',cell.name,epoch,flush=True)
        complete=r/'POSTPROCESS_LEDGER.json'
        if complete.exists() and json.loads(complete.read_text())['status']=='COMPLETE':break
        time.sleep(20)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);run(p.parse_args())
