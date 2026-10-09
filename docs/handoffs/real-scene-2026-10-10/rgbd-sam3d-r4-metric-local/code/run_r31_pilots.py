"""Four matched eight-epoch pilots, at most two independent GPU processes."""
import argparse,json,subprocess,sys,time
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--source-commit',required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);code=Path(__file__).parent
    waiting=['rgb_only','cross_attention','geometry_attention','mhr_refinement'];active=[];done=[];last=0
    while waiting or active:
        while waiting and len(active)<2:
            mode=waiting.pop(0);command=[sys.executable,str(code/'train_r31_pilot.py'),'--root',str(a.root),'--out',str(a.out/mode),
                '--config',str(a.config),'--mode',mode,'--source-commit',a.source_commit]
            with (a.out/(mode+'.log')).open('w') as f:job=subprocess.Popen(command,stdout=f,stderr=subprocess.STDOUT)
            active.append((mode,job));print('PILOT_START',mode,job.pid,flush=True)
        for mode,job in list(active):
            if job.poll() is not None:
                assert job.returncode==0,f'PILOT_FAILED {mode}: {a.out/(mode+".log")}'
                active.remove((mode,job));done.append(mode);print('PILOT_COMPLETE',mode,flush=True)
        if time.monotonic()-last>30:
            gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()
            state=dict(active=[dict(mode=m,pid=j.pid) for m,j in active],completed=done,waiting=waiting,gpu=gpu,time_unix=time.time())
            (a.out/'PROGRESS.json').write_text(json.dumps(state,indent=2))
            with (a.out/'RESOURCE_MONITOR.jsonl').open('a') as f:f.write(json.dumps(state)+'\n')
            last=time.monotonic()
        time.sleep(2)
    (a.out/'ALL_PILOTS_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',models=done,test_used=False)))


if __name__=='__main__':main()
