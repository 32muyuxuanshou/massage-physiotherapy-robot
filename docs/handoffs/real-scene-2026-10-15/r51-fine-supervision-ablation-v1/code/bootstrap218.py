"""Finish preparation, validate main path, then run only the approved 12 units."""
import json,os,subprocess,time,hashlib
from pathlib import Path
W=Path('/raid5/xuhd/rgbd_sam3d/r51_fine_supervision_ablation_v1')
PY='/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python'


def launch(name,gpu,args=()):
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),LD_LIBRARY_PATH='/raid5/xuhd/rgbd_sam3d/runtime218/env/lib')
    return subprocess.Popen([PY,'-u',str(W/'code'/name),*args],env=env)


def main():
    while True:
        paths=[W/'prepared'/('s%d'%s)/'MANIFEST.json' for s in [11,23,37]]
        if all(p.exists() and json.loads(p.read_text())['status']=='COMPLETE' for p in paths):break
        (W/'BOOTSTRAP_STATE.json').write_text(json.dumps(dict(status='WAITING_PREPARED_3_SEEDS',time=time.time())))
        time.sleep(30)
    proc=launch('preflight218.py',6);assert proc.wait()==0,'Preflight failed; training not launched'
    jobs=[launch('baseline218.py',gpu,['--seed',str(seed)]) for gpu,seed in enumerate([11,23,37])]
    assert all(p.wait()==0 for p in jobs),'Baseline evaluation failed'
    names=['EXPERIMENT.json','DATA_MANIFEST.json','L2_CALIBRATION.json']
    names+=['code/'+n for n in ['core.py','train218.py','prepare_queries218.py','preflight218.py','baseline218.py','run_queue218.py','frozen_model.py','frozen_render_losses.py']]
    frozen={n:hashlib.sha256((W/n).read_bytes()).hexdigest() for n in names}
    (W/'SCIENCE_FREEZE.json').write_text(json.dumps(dict(status='FROZEN_BEFORE_TRAINING',files=frozen),indent=2))
    (W/'BOOTSTRAP_STATE.json').write_text(json.dumps(dict(status='PREFLIGHT_PASS_BASELINES_COMPLETE_TRAINING_STARTED',time=time.time())))
    proc=launch('run_queue218.py',0);assert proc.wait()==0,'Queue failed; read unit log'
    (W/'BOOTSTRAP_STATE.json').write_text(json.dumps(dict(status='ALL_12_TRAIN_VAL_COMPLETE_REAL_EVALUATION_PENDING',time=time.time())))


if __name__=='__main__':main()
