"""Execute existing evaluation/figures and cached-output analysis with actual timings."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    root=parser.parse_args().root
    completion=json.loads((root/'TRAINING_COMPLETE.json').read_text())
    assert completion['models']==6
    for asset in json.loads((root/'analysis/ANALYSIS_FREEZE.json').read_text()):
        assert sha(asset['path'])==asset['sha256']
    training=json.loads((root/'TRAINING_LEDGER.json').read_text())
    ledger=dict(status='RUNNING',started_server_utc=stamp(),server='172.18.18.151:436',gpu='0',
                training_models=6,training_epochs_per_model=120,
                training_monotonic_seconds=sum(r['seconds'] for r in training),
                scientific_protocol_sha256=sha(root/'PROTOCOL.md'),
                source_freeze_sha256=sha(root/'SOURCE_FREEZE.json'),
                analysis_freeze_sha256=sha(root/'analysis/ANALYSIS_FREEZE.json'),stages=[])
    output=root/'EXECUTION_LEDGER.json'
    def save():
        output.write_text(json.dumps(ledger,indent=2)+'\n')
    save()
    for name,script in [('evaluation',root/'code/evaluate_line.py'),
                        ('figures',root/'code/make_figures.py'),
                        ('cached_analysis',root/'analysis/analyze_completed.py')]:
        begin=stamp();start=time.monotonic();log=root/(name+'.log')
        command=[sys.executable,'-u',str(script),'--root',str(root)]
        print('STAGE_STARTED',name,begin,flush=True)
        with log.open('w') as f:
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            for line in process.stdout:
                f.write(line);f.flush();print(line,end='',flush=True)
            code=process.wait()
        ledger['stages'].append(dict(name=name,command=command,started_server_utc=begin,
            ended_server_utc=stamp(),monotonic_seconds=time.monotonic()-start,
            returncode=code,log_path=str(log),log_sha256=sha(log)))
        save()
        if code:
            ledger['status']='FAILED';save();raise SystemExit(code)
    ledger.update(status='COMPLETE',ended_server_utc=stamp())
    save()
    print('EXECUTION_COMPLETE',flush=True)
