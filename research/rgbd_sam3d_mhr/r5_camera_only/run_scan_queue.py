"""Five frozen Official inference workers, deterministic scan shards."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def run_shard(root, data, shard, deadline):
    command = [sys.executable, str(Path(__file__).parent/'prepare_scan.py'),
               '--source', str(root/'assets/official_source'),
               '--checkpoint', str(root/'assets/checkpoint/model.ckpt'),
               '--mhr', str(root/'assets/checkpoint/assets/mhr_model.pt'),
               '--data', str(data), '--out', str(root/'assets/compact_scan'),
               '--shard', str(shard), '--shards', '5', '--deadline', str(deadline)]
    with (root/'logs'/f'scan_{shard}.log').open('w') as log:
        job = subprocess.Popen(command, env=dict(os.environ, CUDA_VISIBLE_DEVICES=str(shard+3)),
                               stdout=log, stderr=subprocess.STDOUT)
        (root/f'SCAN_JOB_{shard}.json').write_text(json.dumps(dict(
            pid=job.pid, command=command, gpu=shard+3, started_unix=time.time()), indent=2))
        code = job.wait()
    return dict(shard=shard, exit_code=code)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--deadline', type=float, required=True)
    a = p.parse_args()
    pilot = json.loads((a.root/'assets/scan_preflight/MANIFEST_00.json').read_text())
    assert pilot['status'] == 'COMPLETE' and len(pilot['records']) == 2
    (a.root/'assets/compact_scan').mkdir(exist_ok=False)
    with ThreadPoolExecutor(5) as pool:
        jobs = [pool.submit(run_shard, a.root, a.data, k, a.deadline) for k in range(5)]
        result = [job.result() for job in jobs]
    records = []
    for k in range(5):
        path = a.root/'assets/compact_scan'/f'MANIFEST_{k:02d}.json'
        if path.exists():
            records.extend(json.loads(path.read_text())['records'])
    records.sort(key=lambda r:r['sample_id'])
    assert len({r['sample_id'] for r in records}) == len(records)
    complete = all(r['exit_code'] == 0 for r in result) and len(records) == 3072
    report = dict(status='COMPLETE' if complete else 'INCOMPLETE', records=records,
                  shards=result, test_read=False, MHR_root_GT_available=False)
    (a.root/'assets/compact_scan/MANIFEST.json').write_text(json.dumps(report, indent=2))
    (a.root/'SCAN_QUEUE_RESULT.json').write_text(json.dumps({k:v for k,v in report.items() if k!='records'}, indent=2))
