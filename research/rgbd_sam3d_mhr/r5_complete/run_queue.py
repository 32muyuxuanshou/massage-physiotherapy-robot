"""Persistent scientific queue: screen, wait for QA assets, then 21 runs."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed


def main(a):
    root=a.root;code=Path(__file__).parent;cfg=json.loads((code/'R5_COMPARISON_CONFIG.json').read_text())
    assert json.loads((root/'PREFLIGHT.json').read_text())['status']=='PASS'
    ledger=dict(status='SCREEN_RUNNING',started=time.time(),completed=[],failed=[],TEST_read=False,camera_B_read=False)
    root.mkdir(parents=True,exist_ok=True)
    def save(): (root/'EXECUTION_LEDGER.json').write_text(json.dumps(ledger,indent=2))
    def execute(task):
        mode,seed,lr,epochs,stage=task
        key=f'{mode}_s{seed}_lr{lr:.0e}' if stage=='screen' else f'{mode}_s{seed}'
        folder=root/stage/key;log=root/'logs'/(stage+'_'+key+'.log')
        if (folder/'RESULTS.json').exists():return dict(stage=stage,key=key,status='ALREADY_COMPLETE')
        command=[sys.executable,str(code/'train.py'),'--config',str(code/'R5_COMPARISON_CONFIG.json'),
            '--paths',str(root/'PATHS.json'),'--out',str(folder),'--mode',mode,'--seed',str(seed),'--lr',str(lr),'--epochs',str(epochs)]
        if (folder/'last.pt').exists():command.append('--resume')
        with log.open('a') as f: result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
        return dict(stage=stage,key=key,status='COMPLETE' if result.returncode==0 else 'FAILED',exit_code=result.returncode,log=str(log))
    def phase(tasks):
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            futures=[pool.submit(execute,t) for t in tasks]
            for future in as_completed(futures):
                item=future.result();ledger['completed' if item['status']!='FAILED' else 'failed'].append(item);save()
                print('QUEUE_RESULT',json.dumps(item),flush=True)
        assert not ledger['failed'],'QUEUE_CELL_FAILED_REQUIRES_ROOT_CAUSE_FIX'
    save()
    phase([(m,cfg['lr_screen_seed'],lr,cfg['lr_screen_epochs'],'screen') for m in cfg['methods'] for lr in cfg['lr_candidates']])
    choice={}
    for mode in cfg['methods']:
        scores=[]
        for lr in cfg['lr_candidates']:
            directory=root/'screen'/f'{mode}_s7_lr{lr:.0e}'
            curve=json.loads((directory/'CURVES.json').read_text())[-1]
            scores.append((curve['val']['vertex_camera_mm'],lr))
        score,lr=min(scores);choice[mode]=dict(lr=lr,epoch5_vertex_camera_mm=score)
    (root/'LR_SELECTION.json').write_text(json.dumps(choice,indent=2))
    ledger['status']='WAITING_SCAN_DATA_AND_TRAIN_LOSS_FREEZE';save()
    while not (root/'scan_cache/CACHE_MANIFEST.json').exists() or not (root/'SCAN_LOSS_FREEZE.json').exists():time.sleep(30)
    assert json.loads((root/'scan_cache/CACHE_MANIFEST.json').read_text())['status']=='SPATIAL_SCAN_COMPLETE'
    ledger['status']='FORMAL_RUNNING';save()
    phase([(m,s,choice[m]['lr'],50,'formal') for m in cfg['methods'] for s in cfg['seeds']])
    ledger.update(status='TRAINING_COMPLETE_READY_FOR_FROZEN_EVALUATION',ended=time.time());save()
    print('ALL_21_TRAINING_COMPLETE',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--workers',type=int,default=4)
    main(p.parse_args())
