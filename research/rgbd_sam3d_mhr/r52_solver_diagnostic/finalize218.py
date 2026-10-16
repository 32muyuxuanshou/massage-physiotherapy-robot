"""Finish only the approved summary and integrity stages after evaluation."""
import json,subprocess,sys,time
from common import W,dump


def main():
    while not (W/'EVALUATION_COMPLETE.json').exists():
        if (W/'EXECUTION_LEDGER.json').exists():
            ledger=json.loads((W/'EXECUTION_LEDGER.json').read_text())
            if ledger['status']=='FAILED':raise RuntimeError(ledger)
        time.sleep(10)
    for script in ['summarize.py','integrity.py']:
        dump(W/'FINALIZATION_STATE.json',dict(status='RUNNING',stage=script,training=False))
        with (W/(script+'.log')).open('w') as f:subprocess.run([sys.executable,str(W/'code'/script)],stdout=f,stderr=subprocess.STDOUT,check=True)
    dump(W/'FINALIZATION_STATE.json',dict(status='SUMMARY_AND_INTEGRITY_COMPLETE_AWAITING_REVIEW_BACKUP_GIT',training=False,server_shutdown=False))
    print('SUMMARY_AND_INTEGRITY_COMPLETE',flush=True)


if __name__=='__main__':main()
