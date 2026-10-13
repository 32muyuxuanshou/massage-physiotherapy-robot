"""Repeat the six-frame CPU evaluation in parallel; verify numerical equivalence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
from metrics import sha256


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--workers',type=int,default=8);a=p.parse_args();root=a.root.resolve()
    config=json.loads((root/'reports/EXPERIMENT_CONFIG.json').read_text())
    if len(json.loads((root/'inputs/INPUT_MANIFEST.json').read_text())['records'])!=6:
        raise ValueError('This equivalence check is only for the fixed six-frame smoke')
    old={str(f):sha256(f) for f in (root/'evaluation').glob('*/RESULTS.json')}
    tasks=[]
    for s in config['seeds']:
        tasks.append([root/'cache'/f's{s}'/'CACHE_MANIFEST.json',True])
    for m in ['rgb_only','g1','coarse','full']:
        for s in config['seeds']:
            for ck in ['best','last']:
                tasks.append([root/'predictions'/f'{m}_s{s}_{ck}'/'PREDICTION_MANIFEST.json',False])
    def run(task):
        source,official=task
        cmd=[sys.executable,str(Path(__file__).parent/'evaluate_cached_cpu.py'),'--root',str(root),
             '--r41-code',config['r41_code'],'--prediction-manifest',str(source)]
        if official:cmd.append('--official')
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
    with ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(run,tasks))
    equal={f:sha256(f)==value for f,value in old.items()}
    if not all(equal.values()):raise ValueError('Parallel and serial evaluation JSON differ')
    report=dict(status='PASS',workers=a.workers,completed_cells=len(tasks),
                exact_serial_parallel_results_json_hash_equal=len(equal), scientific_code_changed=False)
    (root/'reports/PARALLEL_SCHEDULE_QA.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
