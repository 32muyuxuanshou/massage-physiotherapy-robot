"""Frozen selected architecture(s), 3 paired seeds and measured concurrency."""
import argparse,datetime,json,subprocess,sys,time
from pathlib import Path


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--modes',nargs='+',required=True)
    p.add_argument('--source-commit',required=True);a=p.parse_args();w=a.root/'runs/r4_geometry_v1';code=Path(__file__).parent
    assert json.loads((w/'PREEXECUTION_GATE.json').read_text())['status']=='PASS'
    gate=json.loads((w/'PILOT_GATE_DECISION.json').read_text());assert gate['formal_modes']==a.modes
    (w/'formal').mkdir(exist_ok=False)
    cfg=json.loads((code/'R4_CONFIG_V1.json').read_text());deadline=datetime.datetime.fromisoformat(cfg['training_stop_utc'].replace('Z','+00:00')).timestamp()
    limit=json.loads((w/'concurrency/CONCURRENCY_QA.json').read_text())['selected_concurrent']
    waiting=[(mode,seed) for mode in a.modes for seed in cfg['formal']['seeds']];running=[];finished=[]
    while waiting or running:
        if time.time()>deadline and waiting:break
        while waiting and len(running)<limit:
            mode,seed=waiting.pop(0);name=f'{mode}_seed{seed}';out=w/'formal'/name/'run';log=(w/'logs'/f'formal_{name}.log').open('w')
            cmd=[sys.executable,'-u',str(code/'train_r4.py'),'--root',str(a.root),'--out',str(out),'--mode',mode,
                '--seed',str(seed),'--epochs',str(cfg['formal']['epochs']),'--train-ids','400','--source-commit',a.source_commit,'--deadline-unix',str(deadline)]
            job=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT);running.append((job,name));print('FORMAL_START',name,job.pid,flush=True)
        for job,name in list(running):
            if job.poll() is not None:
                assert job.returncode==0,f'FORMAL_FAILED {name}'
                running.remove((job,name));finished.append(name);print('FORMAL_FINISHED',name,flush=True)
        with (w/'FORMAL_RESOURCE_MONITOR.jsonl').open('a') as f:
            gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True).strip()
            f.write(json.dumps(dict(time_unix=time.time(),running=[name for _,name in running],waiting=waiting,finished=finished,gpu=gpu))+chr(10))
        time.sleep(15)
    for job,name in running:assert job.wait()==0
    (w/'FORMAL_QUEUE_DONE.json').write_text(json.dumps(dict(status='COMPLETE' if not waiting else 'DEADLINE_PARTIAL',
        finished=finished,not_started=waiting,modes=a.modes,deadline_utc=cfg['training_stop_utc']),indent=2))
