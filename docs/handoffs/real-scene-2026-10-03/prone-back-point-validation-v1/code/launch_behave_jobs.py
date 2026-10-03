"""Five independent subject jobs on five GPUs; never split a fit across GPUs."""
import os,subprocess,sys,time
from pathlib import Path
from run_cached_point_diagnostics import read,write,sha

ROOT=Path('/raid5/xuhd/datasets/prone_back_point_validation_20261003')
BEHAVE=Path('/raid5/xuhd/behave_rgbd_mesh_v1')
OUT=ROOT/'p2_behave_crossview'
assert read(OUT/'SMOKE_GATE.json')['status']=='PASS'
assert read(OUT/'P2_AGGREGATION_VISUAL_FREEZE.json')['code_sha256']==sha(ROOT/'code/summarize_behave_cached.py')
config=Path('/raid5/xuhd/sam3d_s01_pilot_20260906/weights/model_config.yaml')
before=dict(model_config=dict(path=str(config),sha256=sha(config)),launcher_sha256=sha(Path(__file__)),
    runner_sha256=sha(ROOT/'code/run_behave_rigid_d.py'),postprocessor_sha256=sha(ROOT/'code/summarize_behave_cached.py'))
write(OUT/'P2_SUPPLEMENTAL_EXECUTION_FREEZE_PRE.json',before)
jobs=[]
for gpu,subject in enumerate(['Sub03','Sub04','Sub05','Sub06','Sub07']):
    env={**os.environ,'CUDA_VISIBLE_DEVICES':str(gpu),'OMP_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'4'}
    log=OUT/f'run_{subject}.log';stream=log.open('w')
    args=[sys.executable,'-u',str(ROOT/'code/run_behave_rigid_d.py'),'--root',str(ROOT),'--behave',str(BEHAVE),'--phase','full','--subject',subject]
    process=subprocess.Popen(args,env=env,stdout=stream,stderr=subprocess.STDOUT)
    jobs.append((subject,process,stream,log));print('LAUNCHED',subject,'GPU',gpu,'PID',process.pid,flush=True)
statuses=[]
for subject,process,stream,log in jobs:
    code=process.wait();stream.close();statuses.append(dict(subject=subject,returncode=code,log=str(log)))
    print('EXIT',subject,code,flush=True)
assert before['model_config']['sha256']==sha(config)
assert before['runner_sha256']==sha(ROOT/'code/run_behave_rigid_d.py')
assert before['postprocessor_sha256']==sha(ROOT/'code/summarize_behave_cached.py')
write(OUT/'P2_SUPPLEMENTAL_EXECUTION_INTEGRITY_POST.json',dict(status='PASS',identities=before,jobs=statuses))
assert all(s['returncode']==0 for s in statuses),statuses
print('FIVE_SUBJECT_JOBS_COMPLETE',flush=True)
