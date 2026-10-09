"""Durable R3 execution ledger: generated assets -> train -> held-out transfer."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from r3_common import sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--source-commit',required=True)
    p.add_argument('--generation-pid',type=int,required=True)
    a=p.parse_args();root=a.root;code=Path(__file__).parent;out=root/'runs/r3_multiseed_v1'
    out.mkdir(parents=True,exist_ok=True);ledger=[]
    def run(stage,script,*arguments):
        entry=dict(stage=stage,start_unix=time.time(),source_commit=a.source_commit,script_sha256=sha(code/script))
        ledger.append(entry);(out/'EXECUTION_LEDGER.json').write_text(json.dumps(ledger,indent=2))
        command=[sys.executable,str(code/script),*map(str,arguments)]
        print('STAGE_START',stage,flush=True)
        with (out/(stage+'.log')).open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        entry.update(end_unix=time.time(),returncode=result.returncode,command=command)
        (out/'EXECUTION_LEDGER.json').write_text(json.dumps(ledger,indent=2));assert result.returncode==0,f'{stage} FAILED: {out/(stage+".log")}'
        print('STAGE_COMPLETE',stage,flush=True)
    data=root/'datasets/synthetic/native_scale_v2'
    # Generation was launched after the 32-image geometric QA. Wait for its
    # completed manifest rather than evaluating a partly written data tree.
    while not (data/'GEOMETRY_QA.json').exists():
        assert Path(f'/proc/{a.generation_pid}').exists(),'GENERATION_STOPPED_BEFORE_COMPLETION; inspect generation_v2.log'
        time.sleep(5)
    manifest=json.loads((data/'MANIFEST.json').read_text());assert len(manifest['samples'])==4000
    groups={r:{x['identity'] for x in manifest['samples'] if x['role']==r} for r in ['TRAIN','VAL','TEST']}
    assert [len(groups[r]) for r in ['TRAIN','VAL','TEST']]==[400,50,50]
    assert not (groups['TRAIN']&groups['VAL'] or groups['TRAIN']&groups['TEST'] or groups['VAL']&groups['TEST'])
    for identity in groups['TRAIN']|groups['VAL']:
        rr=[r for r in manifest['samples'] if r['identity']==identity]
        assert {(r['pose_id'],r['camera_id']) for r in rr}=={(p,c) for p in range(2) for c in range(4)}
    (out/'DATA_SPLIT_QA.json').write_text(json.dumps(dict(status='PASS',sample_count=4000,
        identities={r:len(groups[r]) for r in groups},identity_disjoint=True,pose_camera_factorial=True,
        manifest_sha256=sha(data/'MANIFEST.json'),test_pixels_loaded=False),indent=2))
    cache=root/'datasets/cache/native_scale_v2';real_cache=root/'datasets/cache/humman_development_v1';points=root/'datasets/heldout/humman_r3_k1_v1'
    run('native_cache','prepare_r3_cache.py','--root',root,'--data',data,'--out',cache)
    run('heldout_points_freeze','evaluate_r3_humman.py','--root',root,'--points',points,'--freeze-points')
    run('real_cache','prepare_r3_cache.py','--root',root,'--data',root/'datasets/registered_v1','--out',real_cache,'--real')
    real_out=out/'real/official';real_out.parent.mkdir(parents=True,exist_ok=True)
    baseline_command=[sys.executable,str(code/'evaluate_r3_humman.py'),'--root',str(root),'--cache',str(real_cache),
        '--points',str(points),'--out',str(real_out)]
    with (out/'official_real.log').open('w') as log:baseline=subprocess.Popen(baseline_command,stdout=log,stderr=subprocess.STDOUT)
    while not (real_out/'GPU_STAGE_DONE.json').exists():
        if baseline.poll() is not None:raise RuntimeError('OFFICIAL_REAL_GPU_FAILED')
        time.sleep(2)
    selection=json.loads((out/'concurrency_qa/SELECTION.json').read_text())
    run('train_multiseed','run_r3_queue.py','--root',root,'--cache',cache,'--config',code/'R3_SCALE_CONFIG_V1.json',
        '--out',out/'formal','--source-commit',a.source_commit,'--real-cache',real_cache,'--real-points',points,
        '--concurrent',selection['concurrent_trainers'])
    assert baseline.wait()==0,'OFFICIAL_REAL_CPU_EVALUATION_FAILED'
    run('summary_figures','summarize_r3.py','--root',root,'--out',out)
    run('data_previews','export_native_data_preview.py','--input-dir',data,'--output-dir',root/'datasets/previews/native_scale_v2','--exclude-test')
    (out/'PIPELINE_COMPLETE.json').write_text(json.dumps(dict(status='R3_MULTISEED_AND_REAL_DEVELOPMENT_COMPLETED',
        source_commit=a.source_commit,end_unix=time.time(),test_evaluated=False),indent=2))


if __name__=='__main__':main()
