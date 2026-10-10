"""Three matched seed pairs on the available AutoDL GPU, no expanded research."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def run(root,seed,deadline):
    result=[]
    for mode in ['native_only','mixed']:
        if time.time()>=deadline:break
        cmd=[sys.executable,str(Path(__file__).parent/'train_continuation.py'),
             '--root',str(root),'--scan-source',str(root/'assets/scan_labels'),
             '--anchors',str(root/'assets/compact_scan/faces.npy'),
             '--seed',str(seed),'--mode',mode,'--deadline',str(deadline)]
        with (root/'logs'/f'continuation_{mode}_s{seed}.log').open('w') as log:
            job=subprocess.Popen(cmd,env=dict(os.environ,CUDA_VISIBLE_DEVICES='0'),stdout=log,stderr=subprocess.STDOUT)
            (root/f'CONTINUATION_JOB_{mode}_s{seed}.json').write_text(json.dumps(dict(pid=job.pid,command=cmd),indent=2))
            code=job.wait()
        result.append(dict(mode=mode,seed=seed,exit_code=code))
        (root/f'CONTINUATION_SEED_{seed}.json').write_text(json.dumps(result,indent=2))
        if code:break
    if len(result)==2 and all(r['exit_code']==0 for r in result):
        control=json.loads((root/f'continuation/native_only_s{seed}/CURVES.json').read_text())
        mixed=json.loads((root/f'continuation/mixed_s{seed}/CURVES.json').read_text())
        assert [r['native_order_sha256'] for r in control]==[r['native_order_sha256'] for r in mixed]
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--deadline',type=float,required=True);a=p.parse_args()
    assert json.loads((a.root/'WEAK_SUPERVISION_FREEZE.json').read_text())['status']=='PASS'
    started=time.time()
    with ThreadPoolExecutor(3) as pool:
        jobs=[pool.submit(run,a.root,seed,a.deadline) for seed in [11,23,37]]
        result=[r for job in jobs for r in job.result()]
    (a.root/'CONTINUATION_QUEUE_RESULT.json').write_text(json.dumps(dict(jobs=result,
        started_unix=started,ended_unix=time.time(),server_shutdown=False,codex_quota_dependency=False),indent=2))
