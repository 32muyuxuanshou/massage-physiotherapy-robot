"""Pilot -> frozen complete A fits on three GPUs -> unchanged B evaluation."""
import json,os,subprocess,sys,time
from common import W,R52,BASE,CFG,sha,dump


def main():
    start=time.monotonic();completed=[]
    frozen={str(p.relative_to(W)):sha(p) for p in sorted((W/'code').glob('*.py'))}
    frozen['EXPERIMENT.json']=sha(W/'EXPERIMENT.json')
    dump(W/'EXECUTION_FREEZE.json',dict(status='FROZEN_BEFORE_PILOT_AND_FULL_RESULTS',files=frozen,
        inherited_R52_execution_freeze_sha256=sha(R52/'EXECUTION_FREEZE.json'),
        inherited_renderer_sha256=sha(BASE/'r51_fine_supervision_ablation_v1/code/frozen_render_losses.py')))
    for stage,pilot in [('solver_qa',True),('all_fits',False)]:
        dump(W/'EXECUTION_LEDGER.json',dict(status='RUNNING',stage=stage,completed=completed,training=False))
        children=[]
        for gpu,seed in enumerate(CFG['seeds']):
            env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu));args=[sys.executable,str(W/'code/fit.py'),'--seed',str(seed)]+(['--pilot'] if pilot else [])
            f=(W/('%s_s%d.log'%(stage,seed))).open('w');children.append((subprocess.Popen(args,env=env,stdout=f,stderr=subprocess.STDOUT),f))
        returns=[]
        for p,f in children:returns.append(p.wait());f.close()
        if any(returns):
            dump(W/'EXECUTION_LEDGER.json',dict(status='FAILED',stage=stage,exit_codes=returns,completed=completed));raise RuntimeError(returns)
        if pilot:
            records=[r for s in CFG['seeds'] for r in json.loads((W/('PILOT_s%d.json'%s)).read_text())['records']]
            dump(W/'SOLVER_PREFLIGHT.json',dict(status='PASS',records=records))
            with (W/'evaluator_qa.log').open('w') as f:subprocess.run([sys.executable,str(W/'code/evaluate.py'),'--pilot','--workers','8'],stdout=f,stderr=subprocess.STDOUT,check=True)
        else:
            records=[r for s in CFG['seeds'] for r in json.loads((W/('FITS_s%d.json'%s)).read_text())['records']]
            assert len(records)==2706
            dump(W/'INPUT_FREEZE.json',dict(status='PASS',records=records,actual_source_SHA_checked=True,Camera_B_fit=False))
            dump(W/'FITS_COMPLETE.json',dict(status='COMPLETE',frames=len(records),method_frame_records=len(records)*len(CFG['methods']),Camera_B_read=False))
        completed.append(stage)
    for stage,script,args in [('all_evaluation','evaluate.py',['--workers','32']),('summary','summarize.py',[]),('integrity','integrity.py',[])]:
        dump(W/'EXECUTION_LEDGER.json',dict(status='RUNNING',stage=stage,completed=completed,training=False))
        with (W/(stage+'.log')).open('w') as f:subprocess.run([sys.executable,str(W/'code'/script),*args],stdout=f,stderr=subprocess.STDOUT,check=True)
        completed.append(stage)
    dump(W/'EXECUTION_LEDGER.json',dict(status='SCIENCE_COMPLETE',completed=completed,seconds=time.monotonic()-start,training=False))
    dump(W/'FINALIZATION_STATE.json',dict(status='SCIENCE_COMPLETE_AWAITING_REVIEW_BACKUP_GIT',training=False,server_shutdown=False))


if __name__=='__main__':main()
