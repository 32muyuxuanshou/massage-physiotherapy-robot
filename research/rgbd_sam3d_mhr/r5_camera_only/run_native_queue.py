"""Three independent seed workers; detached from SSH and Codex quota."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def run_seed(root, seed, gpu, deadline):
    results = []
    for mode in ['raw_bounded', 'metric_xyz', 'rgb_only_xyz']:
        if time.time() >= deadline:
            break
        cell = f'{mode}_s{seed}'
        out = root/'native'/cell
        command = [sys.executable, str(Path(__file__).parent/'train_camera.py'),
                   '--data', str(root/'assets/compact_native'), '--out', str(out),
                   '--mode', mode, '--seed', str(seed), '--epochs', '30',
                   '--deadline', str(deadline)]
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), OMP_NUM_THREADS='2')
        with (root/'logs'/(cell+'.log')).open('w') as log:
            job = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            (root/'native'/(cell+'_JOB.json')).write_text(json.dumps(dict(
                pid=job.pid, command=command, gpu=gpu, started_unix=time.time()), indent=2))
            code = job.wait()
        result = dict(cell=cell, exit_code=code,
                      status='COMPLETE' if code == 0 and (out/'RESULTS.json').exists() else 'FAILED')
        results.append(result)
        (root/'native'/f'SEED_{seed}_LEDGER.json').write_text(json.dumps(results, indent=2))
        if code:
            break  # a real failure is reported, not converted to a new experiment
    return results


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--deadline', type=float, required=True)
    a = p.parse_args()
    assert json.loads((a.root/'PREFLIGHT.json').read_text())['status'] == 'PASS'
    (a.root/'native').mkdir(exist_ok=False)
    started = time.time()
    with ThreadPoolExecutor(3) as pool:
        jobs = [pool.submit(run_seed, a.root, seed, gpu, a.deadline)
                for gpu, seed in enumerate([11, 23, 37])]
        results = [item for job in jobs for item in job.result()]
    (a.root/'NATIVE_QUEUE_RESULT.json').write_text(json.dumps(dict(
        jobs=results, started_unix=started, ended_unix=time.time(),
        server_shutdown=False, codex_quota_dependency=False), indent=2))
