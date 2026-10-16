"""Finite serial stages, existing units resume only by their completed outputs."""
import json,subprocess,sys,time
from common import W,dump


def main():
    assert json.loads((W/'INPUT_FREEZE.json').read_text())['status']=='PASS'
    stages=[('solver_qa',['fit.py','--pilot']),('evaluator_qa',['evaluate.py','--pilot','--workers','8']),
        ('all_fits',['fit.py','--workers','24']),('all_evaluation',['evaluate.py','--workers','32'])]
    completed=[];start=time.monotonic()
    for name,args in stages:
        dump(W/'EXECUTION_LEDGER.json',dict(status='RUNNING',stage=name,completed=completed,training=False))
        with (W/(name+'.log')).open('w') as f:
            result=subprocess.run([sys.executable,str(W/'code'/args[0]),*args[1:]],stdout=f,stderr=subprocess.STDOUT)
        if result.returncode:
            dump(W/'EXECUTION_LEDGER.json',dict(status='FAILED',stage=name,exit_code=result.returncode,completed=completed,training=False));raise SystemExit(result.returncode)
        completed.append(name)
    dump(W/'EXECUTION_LEDGER.json',dict(status='SCIENCE_COMPLETE',completed=completed,seconds=time.monotonic()-start,training=False))


if __name__=='__main__':main()
