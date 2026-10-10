"""Autonomous original-renderer continuation -> frozen scan/Depth diagnostics.

No model is selected by scan or real results. No dependency on Codex quota.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import time


def diagnostics(root,checkpoint,deadline):
    cell=checkpoint.parent.parent.name+'__'+checkpoint.parent.name
    jobs=[]
    for program,extra in [('evaluate_scan.py',['--root',str(root)]),
                          ('ablate_depth.py',['--data',str(root/'assets/compact_native')])]:
        if time.time()>=deadline:break
        name=program.removesuffix('.py')
        command=[sys.executable,str(Path(__file__).parent/program),*extra,
                 '--checkpoint',str(checkpoint),'--out',str(root/'diagnostics'/f'{cell}_{name}.json')]
        with (root/'logs'/f'{cell}_{name}.log').open('w') as log:
            code=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
        jobs.append(dict(cell=cell,program=program,exit_code=code))
        if code:break
    return jobs


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--deadline',type=float,required=True);p.add_argument('--closeout',type=float,required=True)
    a=p.parse_args()
    ledger=a.root/'GPU_NIGHT_LEDGER.json'
    state=dict(started_unix=time.time(),phase='CONTINUATION',codex_quota_dependency=False)
    ledger.write_text(json.dumps(state,indent=2))
    command=[sys.executable,str(Path(__file__).parent/'run_continuation_queue.py'),
             '--root',str(a.root),'--deadline',str(a.deadline)]
    code=subprocess.call(command)
    result=json.loads((a.root/'CONTINUATION_QUEUE_RESULT.json').read_text())
    assert code==0 and len(result['jobs'])==6 and all(r['exit_code']==0 for r in result['jobs'])
    state['phase']='FROZEN_DIAGNOSTICS';ledger.write_text(json.dumps(state,indent=2))
    checkpoints=[a.root/f'native/metric_xyz_s{seed}/best.pt' for seed in [11,23,37]]
    checkpoints+=[a.root/f'continuation/{mode}_s{seed}/best.pt' for mode in ['native_only','mixed'] for seed in [11,23,37]]
    with ThreadPoolExecutor(3) as pool:
        futures=[pool.submit(diagnostics,a.root,checkpoint,a.closeout) for checkpoint in checkpoints]
        jobs=[r for future in futures for r in future.result()]
    state.update(phase='READY_FOR_BACKUP_AND_CPU_REAL_EVAL',ended_unix=time.time(),diagnostics=jobs,
                 shutdown=False,reason='backup verification and held-out CPU evaluation remain')
    ledger.write_text(json.dumps(state,indent=2))
