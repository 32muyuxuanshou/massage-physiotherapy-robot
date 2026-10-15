"""Finite 12-unit queue on existing 218 GPUs; no automatic extra experiments."""
import json,os,subprocess,time
from pathlib import Path
from core import WORK,CFG,sha


def main():
    assert json.loads((WORK/'PREFLIGHT.json').read_text())['status']=='PASS'
    freeze=json.loads((WORK/'SCIENCE_FREEZE.json').read_text())
    for name,digest in freeze['files'].items():assert sha(WORK/name)==digest,name
    tasks=[(arm,seed) for seed in CFG['seeds'] for arm in CFG['arms']]
    done=[];pending=[];running={};errors=[]
    for arm,seed in tasks:
        p=WORK/'runs'/('%s_s%d'%(arm,seed))/'RESULTS.json'
        if p.exists() and json.loads(p.read_text())['status']=='TRAIN_VAL_COMPLETE':done.append(dict(arm=arm,seed=seed))
        else:pending.append((arm,seed))
    start=time.monotonic()
    while pending or running:
        for gpu in range(8):
            if not pending or errors:break
            if gpu in running:continue
            arm,seed=pending.pop(0);env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),LD_LIBRARY_PATH='/raid5/xuhd/rgbd_sam3d/runtime218/env/lib')
            log=(WORK/('train_%s_s%d.log'%(arm,seed))).open('a')
            proc=subprocess.Popen(['/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python','-u',str(WORK/'code/train218.py'),'--seed',str(seed),'--arm',arm],env=env,stdout=log,stderr=subprocess.STDOUT)
            running[gpu]=(proc,log,arm,seed);print('START',gpu,arm,seed,proc.pid,flush=True)
        for gpu,(proc,log,arm,seed) in list(running.items()):
            result=proc.poll()
            if result is None:continue
            log.close();del running[gpu]
            item=dict(arm=arm,seed=seed,exit_code=result)
            if result:errors.append(item)
            else:done.append(item)
            print('FINISH',gpu,item,flush=True)
        state=dict(status='FAILED' if errors else 'RUNNING',done=done,pending=pending,running=[dict(gpu=g,arm=v[2],seed=v[3],pid=v[0].pid) for g,v in running.items()],errors=errors,seconds=time.monotonic()-start)
        (WORK/'EXECUTION_LEDGER.json').write_text(json.dumps(state,indent=2))
        if errors and not running:break
        time.sleep(15)
    if errors:raise RuntimeError(errors)
    assert len(done)==12
    for name,digest in freeze['files'].items():assert sha(WORK/name)==digest,name
    selections=[]
    for arm,seed in tasks:
        p=WORK/'runs'/('%s_s%d'%(arm,seed));r=json.loads((p/'RESULTS.json').read_text())
        selections.append(dict(arm=arm,seed=seed,old_best_epoch=r['old_best_epoch'],joint_best_epoch=r['joint_best_epoch'],last_epoch=r['last_epoch'],checkpoint_sha256={str(ep):sha(p/('epoch_%02d.pt'%ep)) for ep in set([r['old_best_epoch'],r['joint_best_epoch'],r['last_epoch']])}))
    (WORK/'SELECTION_FREEZE.json').write_text(json.dumps(dict(status='FROZEN_BEFORE_ANY_REAL_EVAL',records=selections,config_sha256=sha(WORK/'EXPERIMENT.json')),indent=2))
    state.update(status='TRAIN_VAL_COMPLETE_AWAITING_REAL_EVALUATION',running=[],pending=[])
    (WORK/'EXECUTION_LEDGER.json').write_text(json.dumps(state,indent=2));print('ALL_12_COMPLETE',flush=True)


if __name__=='__main__':main()
