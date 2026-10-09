"""Measure 1/2/3 independent trainers on one GPU; no scientific results."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();code=Path(__file__).parent;out=a.root/'runs/r3_multiseed_v1/concurrency_qa';out.mkdir(exist_ok=True)
    results=[]
    for count in [1,2,3]:
        jobs=[];start=time.monotonic()
        for i in range(count):
            directory=out/f'concurrency{count}_job{i}';mode=['cross_attention','residual','rgb_only'][i]
            cmd=[sys.executable,str(code/'train_r3_multiseed.py'),'--root',str(a.root),
                '--cache',str(a.root/'datasets/cache/r3_batch_qa_v3'),'--config',str(code/'R3_SCALE_CONFIG_V1.json'),
                '--out',str(directory),'--source-commit','STRUCTURAL_THROUGHPUT_QA_ONLY','--benchmark-steps','60','--mode',mode]
            with (out/f'c{count}_job{i}.log').open('w') as log:
                jobs.append((subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT),directory))
        cells=[]
        for job,directory in jobs:
            assert job.wait()==0,f'CONCURRENCY_BENCHMARK_FAILED {directory}'
            cells.append(json.loads((directory/'benchmark/BENCHMARK.json').read_text()))
        result=dict(concurrent_trainers=count,wall_seconds=time.monotonic()-start,cells=cells,
            steady_images_per_second=sum(c['batch']/c['warmed_seconds_per_step'] for c in cells),
            peak_allocated_bytes_sum=sum(c['peak_memory_bytes'] for c in cells))
        results.append(result);print(json.dumps(result),flush=True)
        (out/'CONCURRENCY_BENCHMARK.json').write_text(json.dumps(results,indent=2))
    selected=max(results,key=lambda r:r['steady_images_per_second'])['concurrent_trainers']
    (out/'SELECTION.json').write_text(json.dumps(dict(concurrent_trainers=selected,rule='highest measured total steady images/s among 1/2/3 processes',results=results),indent=2))


if __name__=='__main__':main()
