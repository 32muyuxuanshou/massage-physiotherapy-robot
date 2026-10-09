"""Controlled pilot queue, only after actual native/resume/physical QA."""
import argparse,json,subprocess,sys,time
from pathlib import Path


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--source-commit',required=True)
    a=p.parse_args();w=a.root/'runs/r4_geometry_v1';code=Path(__file__).parent
    required=[w/'qa/NATIVE_SELF_REVIEW_QA.json',w/'resume_qa_v2/RESUME_QA.json',w/'physical_camera_data/GEOMETRY_QA.json',w/'physical_camera_cache/CACHE_MANIFEST.json',w/'concurrency/CONCURRENCY_QA.json']
    while not all(p.exists() for p in required):time.sleep(3)
    for p in required:assert json.loads(p.read_text())['status'].startswith(('PASS','CACHE_COMPLETE')),(p,json.loads(p.read_text())['status'])
    (w/'PREEXECUTION_GATE.json').write_text(json.dumps(dict(status='PASS',assets=[str(p) for p in required],test_read=False),indent=2))
    limit=json.loads(required[-1].read_text())['selected_concurrent'];waiting=['g0','g1','g2','g3'];running=[]
    while waiting or running:
        while waiting and len(running)<limit:
            mode=waiting.pop(0);out=w/'pilots'/mode/'run';log=(w/'logs'/f'pilot_{mode}.log').open('w')
            cmd=[sys.executable,'-u',str(code/'train_r4.py'),'--root',str(a.root),'--out',str(out),'--mode',mode,
                '--seed','11','--epochs','8','--train-ids','100','--source-commit',a.source_commit]
            job=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT);running.append((job,mode));print('START',mode,job.pid,flush=True)
        for job,mode in list(running):
            if job.poll() is not None:
                assert job.returncode==0,f'PILOT_FAILED {mode}'
                assert (w/'pilots'/mode/'run/RESULTS.json').exists()
                running.remove((job,mode));print('FINISHED',mode,flush=True)
        with (w/'RESOURCE_MONITOR.jsonl').open('a') as f:
            gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True).strip()
            f.write(json.dumps(dict(time_unix=time.time(),running=[m for _,m in running],waiting=waiting,gpu=gpu))+chr(10))
        time.sleep(10)
    (w/'PILOTS_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',modes=['g0','g1','g2','g3'])))
