"""Explicit GPU queue followed by cached CPU evaluation; never train models."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--scope',choices=['smoke','formal'],required=True);a=p.parse_args()
    base=a.root.resolve();config=json.loads((base/'reports/EXPERIMENT_CONFIG.json').read_text())
    freeze=json.loads((base/'reports/MODEL_ASSET_FREEZE.json').read_text())
    for r in freeze['assets']+freeze['checkpoints']+config['source_files']:
        if sha(r['path'])!=r['sha256']:raise ValueError('Actual frozen execution asset changed: '+r['path'])
    job=base/'smoke' if a.scope=='smoke' else base;job.mkdir(exist_ok=True)
    if a.scope=='smoke':
        (job/'reports').mkdir(exist_ok=True);(job/'inputs').mkdir(exist_ok=True)
        for name in ['PATHS.json'] :shutil.copyfile(base/name,job/name)
        for name in ['MODEL_ASSET_FREEZE.json','EXPERIMENT_CONFIG.json']:shutil.copyfile(base/'reports'/name,job/'reports'/name)
        shutil.copyfile(base/'inputs_smoke/INPUT_MANIFEST.json',job/'inputs/INPUT_MANIFEST.json')
    inputs=json.loads((job/'inputs/INPUT_MANIFEST.json').read_text())
    if len(inputs['records'])!=(6 if a.scope=='smoke' else 270):raise ValueError('Wrong cohort size')
    code=Path(__file__).parent;ledger={'scope':a.scope,'status':'GPU_REQUIRED_NEXT','completed':[],'failed':[],'training':False,'started_unix':time.time()}
    logs=job/'logs';logs.mkdir(exist_ok=True)
    def run(key,args):
        with (logs/(key+'.log')).open('w') as f:result=subprocess.run([sys.executable,str(code/args[0]),*args[1:]],stdout=f,stderr=subprocess.STDOUT)
        ledger['failed' if result.returncode else 'completed'].append({'task':key,'exit_code':result.returncode})
        (job/'EXECUTION_LEDGER.json').write_text(json.dumps(ledger,indent=2))
        if result.returncode:raise RuntimeError('Task failed; inspect '+str(logs/(key+'.log')))
        print('COMPLETE',key,flush=True)
    for seed in config['seeds']:
        ledger['status']='OFFICIAL_K0_CACHE'
        run('official_'+str(seed),['cache_official_gpu.py','--root',str(job),'--r5-code',config['r5_code'],'--inputs',str(job/'inputs'),'--seed',str(seed)])
    for mode in ['rgb_only','g1','coarse','full']:
        for seed in config['seeds']:
            for ck in ['best','last']:
                ledger['status']='EXISTING_RAW_PREDICTIONS'
                run(f'{mode}_{seed}_{ck}',['predict_existing_gpu.py','--root',str(job),'--r5-code',config['r5_code'],'--mode',mode,'--seed',str(seed),'--checkpoint',ck])
    for seed in config['seeds']:
        ledger['status']='CPU_GEOMETRY_EVALUATION'
        run('eval_official_'+str(seed),['evaluate_cached_cpu.py','--root',str(job),'--r41-code',config['r41_code'],
            '--prediction-manifest',str(job/'cache'/f's{seed}'/'CACHE_MANIFEST.json'),'--official'])
    for mode in ['rgb_only','g1','coarse','full']:
        for seed in config['seeds']:
            for ck in ['best','last']:
                run(f'eval_{mode}_{seed}_{ck}',['evaluate_cached_cpu.py','--root',str(job),'--r41-code',config['r41_code'],
                    '--prediction-manifest',str(job/'predictions'/f'{mode}_s{seed}_{ck}'/'PREDICTION_MANIFEST.json')])
    run('aggregate',['summarize_benchmark.py','--root',str(job)])
    ledger.update(status='SMOKE_COMPLETE_AWAITING_REVIEW' if a.scope=='smoke' else 'FORMAL_NUMERIC_COMPLETE_AWAITING_VISUAL_REVIEW',ended_unix=time.time())
    (job/'EXECUTION_LEDGER.json').write_text(json.dumps(ledger,indent=2))
    print(ledger['status'],flush=True)

if __name__=='__main__':main()
