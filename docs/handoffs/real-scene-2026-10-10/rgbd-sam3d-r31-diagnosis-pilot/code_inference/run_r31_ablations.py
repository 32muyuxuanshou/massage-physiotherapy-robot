"""Run inference-only ablations as each pilot finishes; one GPU job at a time."""
import argparse,json,subprocess,sys,time
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--pilot',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);waiting=['rgb_only','cross_attention','geometry_attention','mhr_refinement'];done=[]
    while waiting:
        ready=next((m for m in waiting if (a.pilot/m/'PILOT_COMPLETE.json').exists()),None)
        if ready is None:time.sleep(10);continue
        command=[sys.executable,str(Path(__file__).with_name('ablate_r31_candidates.py')),'--root',str(a.root),
            '--pilot',str(a.pilot),'--out',str(a.out/ready),'--mode',ready]
        print('ABLATIONS_START',ready,flush=True)
        with (a.out/(ready+'.log')).open('w') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        assert r.returncode==0,f'ABLATIONS_FAILED {ready}: {a.out/(ready+".log")}'
        waiting.remove(ready);done.append(ready);print('ABLATIONS_COMPLETE',ready,flush=True)
    (a.out/'ALL_ABLATIONS_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',models=done,test_used=False)))


if __name__=='__main__':main()
