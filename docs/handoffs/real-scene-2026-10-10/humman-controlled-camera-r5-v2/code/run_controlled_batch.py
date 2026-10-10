"""Eight disjoint render/pack lanes; finalize and verify the entire frozen plan."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--workers',type=int,default=8)
    a=p.parse_args();root=a.root.resolve()
    plan=json.loads((root/'RENDER_PLAN.json').read_text())
    blender=root/'runtime/blender-3.3.21-linux-x64/blender'
    dataset=root/'dataset';code=root/'code';logs=root/'logs'
    env=dict(os.environ,PYTHONPATH=str(root/'runtime/pack_deps'),OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1')
    start=time.monotonic()
    ledger=dict(status='RUNNING',started_utc=datetime.now(timezone.utc).isoformat(),
                expected_samples=plan['expected_samples'],workers=a.workers,device='CUDA',
                plan_sha256=hashlib.sha256((root/'RENDER_PLAN.json').read_bytes()).hexdigest(),
                training_started=False,TEST_read=False)
    (root/'EXECUTION_LEDGER.json').write_text(json.dumps(ledger,indent=2))
    size=(len(plan['assets'])+a.workers-1)//a.workers

    def command(cmd,log):
        with log.open('w') as f:
            subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,env=env,check=True)

    def worker(i):
        offset=i*size
        command([blender,'--background','--factory-startup','--python-exit-code','1','--python',code/'render_blender.py','--',
                 '--plan',root/'RENDER_PLAN.json','--source',root/'source','--out',dataset,
                 '--hdri',root/'assets/studio_small_03_1k.hdr','--offset',offset,'--limit-assets',size,
                 '--device','CUDA','--device-index',i,'--threads','4'],logs/f'render_{i:02d}.log')
        command([sys.executable,code/'pack_dataset.py','--root',dataset,'--plan',root/'RENDER_PLAN.json',
                 '--offset-assets',offset,'--limit-assets',size,'--shard-name',f'{i:02d}'],logs/f'pack_{i:02d}.log')
        print('LANE_COMPLETE',i,'elapsed_s',round(time.monotonic()-start,1),flush=True)
        return i

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        completed=list(pool.map(worker,range(a.workers)))
    manifests=[json.loads((dataset/f'MANIFEST_{i:02d}.json').read_text()) for i in completed]
    reports=[json.loads((dataset/f'GEOMETRY_QA_{i:02d}.json').read_text()) for i in completed]
    rows=sorted([r for m in manifests for r in m['samples']],key=lambda r:r['sample_id'])
    assert len(rows)==len({r['sample_id'] for r in rows})==plan['expected_samples']
    assert len({m['source_plan_sha256'] for m in manifests})==1
    from collections import Counter
    manifest=dict(manifests[0],samples=rows,roles=dict(Counter(r['role'] for r in rows)))
    qa_rows=[r for q in reports for r in q['records']]
    qa=dict(reports[0],records=qa_rows,samples=len(rows),
            max_ray_error_mm=max(r['max_z_error_mm'] for r in qa_rows),
            min_rgb_depth_mask_iou=min(r['rgb_object_mask_iou'] for r in qa_rows),
            max_independent_cycles_depth_p95_mm=max(r['independent_cycles_z_to_camera_z_p95_mm'] for r in qa_rows),
            max_scene_floor_under_20m_depth_p95_mm=max(r['scene_floor_under_20m_depth_p95_mm'] for r in qa_rows
                                                     if r['scene_floor_under_20m_depth_p95_mm'] is not None))
    (dataset/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    (dataset/'GEOMETRY_QA.json').write_text(json.dumps(qa,indent=2))
    command([sys.executable,code/'verify_dataset.py','--root',dataset,'--source',root/'source','--plan',root/'RENDER_PLAN.json'],logs/'verify.log')
    command([sys.executable,code/'verify_camera_factors.py','--root',dataset],logs/'camera_factors.log')
    command([sys.executable,code/'controlled_previews.py','--root',dataset,'--out',root/'previews','--plan',root/'RENDER_PLAN.json'],logs/'previews.log')
    ledger.update(status='COMPLETE',completed_utc=datetime.now(timezone.utc).isoformat(),
                  elapsed_s=time.monotonic()-start,samples=len(rows),lanes=completed,
                  final_dataset_qa='PASS',camera_factor_qa='PASS',previews='COMPLETE')
    (root/'EXECUTION_LEDGER.json').write_text(json.dumps(ledger,indent=2))
    print(json.dumps(ledger),flush=True)


if __name__=='__main__':
    main()
