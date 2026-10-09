"""Evaluate completed cells as they appear; no training/TEST-driven selection."""
import argparse,json,subprocess,sys,time
from pathlib import Path


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--cells',type=Path,required=True)
    p.add_argument('--names',nargs='+',required=True);p.add_argument('--max-workers',type=int,default=2)
    a=p.parse_args();code=Path(__file__).parent;w=a.root/'runs/r4_geometry_v1';running=[]
    waiting=[(n,k) for n in a.names for k in ['real','physical','ablations']]
    while waiting or running:
        for name,kind in list(waiting):
            cell=a.cells/name;checkpoint=cell/'run/best.pt'
            if not (cell/'run/RESULTS.json').exists() or len(running)>=a.max_workers:continue
            target=cell/(kind+'.json' if kind=='physical' else kind)
            script={'real':'evaluate_r4_humman.py','physical':'evaluate_r4_physical.py','ablations':'ablate_r4.py'}[kind]
            log=(w/'logs'/f'{a.cells.name}_{name}_{kind}.log').open('w')
            cmd=[sys.executable,'-u',str(code/script),'--root',str(a.root),'--out',str(target),'--checkpoint',str(checkpoint)]
            job=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT);running.append((job,name,kind));waiting.remove((name,kind))
            print('EVAL_START',name,kind,job.pid,flush=True)
        for job,name,kind in list(running):
            if job.poll() is not None:
                assert job.returncode==0,f'EVALUATION_FAILED {name} {kind}'
                running.remove((job,name,kind));print('EVAL_DONE',name,kind,flush=True)
        time.sleep(5)
    (a.cells/'EVALUATIONS_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',cells=a.names,tests=False)))
