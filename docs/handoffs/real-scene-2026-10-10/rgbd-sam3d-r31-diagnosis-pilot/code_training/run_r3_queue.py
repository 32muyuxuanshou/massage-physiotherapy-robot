"""Independent process queue, preserving each model/seed's scientific contract."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np


def main():
    p=argparse.ArgumentParser()
    for key in ['root','cache','config','out','real-cache','real-points']:
        p.add_argument('--'+key,type=Path,required=key not in ['real-cache','real-points'])
    p.add_argument('--source-commit',required=True);p.add_argument('--concurrent',type=int,required=True)
    a=p.parse_args();code=Path(__file__).parent;cfg=json.loads(a.config.read_text());a.out.mkdir(parents=True,exist_ok=True)
    def queue(cells,screen):
        waiting=list(cells);active=[]
        while waiting or active:
            while waiting and len(active)<a.concurrent:
                cell=waiting.pop(0);directory=cell['directory']
                if (directory/'CELL_COMPLETE.json').exists():continue
                command=[sys.executable,str(code/'train_r3_multiseed.py'),'--root',str(a.root),'--cache',str(a.cache),
                    '--config',str(a.config),'--out',str(directory),'--source-commit',a.source_commit,
                    '--mode',cell['mode'],'--single-seed',str(cell['seed']),'--single-lr',str(cell['lr']),
                    '--single-epochs',str(cfg['lr_screen_epochs'] if screen else cfg['epochs'])]
                if screen:command.append('--screen-only')
                elif a.real_cache:command+=['--real-cache',str(a.real_cache),'--real-points',str(a.real_points)]
                directory.parent.mkdir(parents=True,exist_ok=True)
                with directory.with_suffix('.log').open('w') as log:
                    job=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                active.append((job,cell));print('CELL_START',cell['mode'],cell['seed'],cell['lr'],job.pid,flush=True)
            for job,cell in list(active):
                if job.poll() is None:continue
                assert job.returncode==0,f"CELL_FAILED: {cell['directory']}.log"
                active.remove((job,cell));print('CELL_COMPLETE',cell['mode'],cell['seed'],flush=True)
            time.sleep(2)
    screen=[dict(mode=m,seed=cfg['lr_screen_seed'],lr=lr,directory=a.out/'lr_screen'/f'{m}_{lr}')
            for lr in cfg['lr_candidates'] for m in cfg['methods']]
    queue(screen,True)
    scores=[]
    for cell in screen:
        report=json.loads((cell['directory']/'run/RESULTS.json').read_text())
        scores.append(dict(mode=cell['mode'],lr=cell['lr'],score=report['last']['identity_equal_mean']['vertex_camera_mm']))
    means={lr:float(np.mean([s['score'] for s in scores if s['lr']==lr])) for lr in cfg['lr_candidates']}
    chosen=min(cfg['lr_candidates'],key=lambda lr:(means[lr],lr))
    (a.out/'LR_SELECTION.json').write_text(json.dumps(dict(screen=scores,mean_scores=means,chosen=chosen,rule=cfg['lr_selection']),indent=2))
    # One parent identity copy; each process still computes and saves its own.
    (a.out/'EXECUTION_IDENTITY.json').write_text((screen[0]['directory']/'EXECUTION_IDENTITY.json').read_text())
    cells=[dict(mode=m,seed=s,lr=chosen,directory=a.out/'cells'/f'{m}_seed{s}')
           for s in cfg['train_seeds'] for m in cfg['methods']]
    queue(cells,False)
    reports=[];(a.out/'training').mkdir(exist_ok=True);(a.out/'real').mkdir(exist_ok=True)
    for cell in cells:
        name=f"{cell['mode']}_seed{cell['seed']}";directory=cell['directory']
        (a.out/'training'/name).symlink_to(directory/'run',target_is_directory=True)
        if a.real_cache:(a.out/'real'/name).symlink_to(directory/'real',target_is_directory=True)
        report=json.loads((directory/'run/RESULTS.json').read_text())
        reports.append(dict(mode=cell['mode'],seed=cell['seed'],best_epoch=report['best_epoch'],
            best=report['best']['identity_equal_mean'],last=report['last']['identity_equal_mean']))
    summary={}
    for mode in cfg['methods']:
        rr=[r for r in reports if r['mode']==mode]
        summary[mode]=dict(seeds=len(rr),metrics={k:dict(mean=float(np.mean([r['best'][k] for r in rr])),
            sample_std=float(np.std([r['best'][k] for r in rr],ddof=1))) for k in rr[0]['best']})
    (a.out/'MULTISEED_SUMMARY.json').write_text(json.dumps(dict(status='COMPLETE',runs=reports,summary=summary,
        concurrency=a.concurrent,test_evaluated=False,real_training_performed=False),indent=2))
    print('MULTISEED_COMPLETE',flush=True)


if __name__=='__main__':main()
