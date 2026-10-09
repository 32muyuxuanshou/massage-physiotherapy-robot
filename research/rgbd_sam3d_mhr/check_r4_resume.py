"""Two full-batch TRAIN steps/epoch: uninterrupted versus fresh-process resume."""
import argparse, json, subprocess, sys
from pathlib import Path
import torch


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--source-commit',required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    common=[sys.executable,'-u',str(Path(__file__).with_name('train_r4.py')),'--root',str(a.root),'--mode','g1',
        '--epochs','2','--train-ids','4','--seed','11','--source-commit',a.source_commit]
    for name,extra in [('uninterrupted',[]),('resumed',['--stop-after','1']),('resumed',['--resume'])]:
        with (a.out/(name+('_resume' if '--resume' in extra else '')+'.log')).open('w') as log:
            subprocess.run(common+['--out',str(a.out/name)]+extra,stdout=log,stderr=subprocess.STDOUT,check=True)
    first=torch.load(a.out/'uninterrupted/last.pt',map_location='cpu',weights_only=False)
    second=torch.load(a.out/'resumed/last.pt',map_location='cpu',weights_only=False)
    differences={k:float((first['fusion'][k]-second['fusion'][k]).abs().max()) for k in first['fusion']}
    # CUDA MHR scatter/rasterizer reductions are not bitwise deterministic.
    # Verify exact restored state, then tight output agreement after new steps.
    assert max(differences.values())<1e-4,differences
    assert first['scheduler']==second['scheduler'] and first['numpy_generator_state']==second['numpy_generator_state']
    assert torch.equal(first['torch_rng_state'],second['torch_rng_state'])
    optimizer_max=0.
    for key,values in first['optimizer']['state'].items():
        for name,x in values.items():
            y=second['optimizer']['state'][key][name]
            if torch.is_tensor(x):optimizer_max=max(optimizer_max,float((x-y).abs().max()))
            else:assert x==y
    assert optimizer_max<1e-5
    restored=json.loads((a.out/'resumed/RESUME_STATE_RESTORE.json').read_text());assert restored['fusion_reloaded_exact']
    scores=[json.loads((a.out/n/'RESULTS.json').read_text())['last']['identity_equal_mean']['vertex_camera_mm']
            for n in ['uninterrupted','resumed']]
    assert abs(scores[0]-scores[1])<.001
    report=dict(status='PASS',batch_size=16,train_ids=4,train_images=32,epochs=2,fresh_process_resume=True,
        fusion_max_abs=max(differences.values()),optimizer_max_abs=optimizer_max,scheduler_rng_equal=True,
        restored_state=restored,final_val_difference_mm=abs(scores[0]-scores[1]),
        tolerances=dict(fusion=1e-4,optimizer=1e-5,val_mm=.001),
        bitwise_training=False,note='exact checkpoint restore; CUDA reduction roundoff allowed in subsequent training, geometry agreement reported')
    (a.out/'RESUME_QA.json').write_text(json.dumps(report,indent=2));print('RESUME_QA_PASS',flush=True)
