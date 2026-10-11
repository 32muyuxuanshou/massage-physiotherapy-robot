"""Automatic full best/last evaluation after the fixed 21-run training queue."""
import argparse,json,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
def main(a):
    root=a.root;code=Path(__file__).parent;cfg=json.loads((code/'R5_COMPARISON_CONFIG.json').read_text())
    history=root/'assets/real_evaluation'
    ledger=dict(status='WAITING_FROZEN_TRAINING',completed=[],failed=[],TEST_read=False,new_model_Txyz=False)
    def save():
        p=root/'POSTPROCESS_LEDGER.json';tmp=p.with_suffix('.tmp.json');tmp.write_text(json.dumps(ledger,indent=2));tmp.replace(p)
    def run_command(key,command,done):
        if done.exists():return dict(key=key,status='ALREADY_COMPLETE')
        with (root/'logs'/('post_'+key+'.log')).open('a') as f:
            result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
        return dict(key=key,status='COMPLETE' if result.returncode==0 else 'FAILED',exit_code=result.returncode)
    def execute(cell,mode,seed,checkpoint,dataset):
        key=cell+'_'+dataset;out=root/'evaluation'/cell/dataset
        command=[sys.executable,str(code/'evaluate.py'),'--paths',str(root/'PATHS.json'),
            '--out',str(out),'--mode',mode,'--seed',str(seed),'--dataset',dataset]
        if checkpoint:command+=['--checkpoint',str(checkpoint)]
        return run_command(key,command,out/'RESULTS.json')
    def account(item):
        ledger['failed' if item['status']=='FAILED' else 'completed'].append(item);save()
        assert item['status']!='FAILED',('POSTPROCESS_FAILED',item)
    save()
    while not (root/'scan_cache/CACHE_MANIFEST.json').exists():time.sleep(30)
    ledger['status']='OFFICIAL_BASELINES';save()
    for dataset in ['native','scan','real']:account(execute('official','official',0,None,dataset))
    out=root/'evaluation/official/real_B'
    command=[sys.executable,str(code/'evaluate_real_cpu.py'),'--history',str(history),
        '--predictions',str(root/'evaluation/official/real/predictions'),'--out',str(out),'--mode','official','--workers',str(a.cpu_workers)]
    account(run_command('official_real_B',command,out/'RESULTS.json'))
    ledger['status']='WAITING_FROZEN_TRAINING';save()
    while True:
        training=json.loads((root/'EXECUTION_LEDGER.json').read_text())
        assert not training['failed'],'FORMAL_TRAINING_FAILED'
        if training['status']=='TRAINING_COMPLETE_READY_FOR_FROZEN_EVALUATION':break
        time.sleep(30)
    ledger['status']='RAW_BEST_LAST_PREDICTIONS';save();tasks=[]
    for mode in cfg['methods']:
        for seed in cfg['seeds']:
            directory=root/'formal'/f'{mode}_s{seed}'
            assert json.loads((directory/'RESULTS.json').read_text())['epochs_completed']==50
            for checkpoint in ['best','last']:
                cell=f'{mode}_s{seed}_{checkpoint}'
                for dataset in ['native','scan','real']:tasks.append((cell,mode,seed,directory/(checkpoint+'.pt'),dataset))
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for future in as_completed([pool.submit(execute,*t) for t in tasks]):account(future.result())
    ledger['status']='INDEPENDENT_CAMERA_B';save()
    for mode in cfg['methods']:
        for seed in cfg['seeds']:
            for checkpoint in ['best','last']:
                cell=f'{mode}_s{seed}_{checkpoint}';out=root/'evaluation'/cell/'real_B'
                command=[sys.executable,str(code/'evaluate_real_cpu.py'),'--history',str(history),
                    '--predictions',str(root/'evaluation'/cell/'real/predictions'),'--out',str(out),
                    '--mode',cell,'--workers',str(a.cpu_workers)]
                account(run_command(cell+'_real_B',command,out/'RESULTS.json'))
    ledger['status']='DEPTH_ABLATIONS';save()
    for mode in cfg['methods']:
        for seed in cfg['seeds']:
            cell=f'{mode}_s{seed}';out=root/'ablations'/cell
            command=[sys.executable,str(code/'ablate_depth.py'),'--paths',str(root/'PATHS.json'),
                '--mode',mode,'--seed',str(seed),'--checkpoint',str(root/'formal'/cell/'best.pt'),'--out',str(out)]
            account(run_command(cell+'_depth_ablation',command,out/'RESULTS.json'))
    ledger['status']='REPORT_AND_VISUALIZATION';save()
    for name in ['summarize.py','visualize.py','post_integrity.py']:
        command=[sys.executable,str(code/name),'--root',str(root)]
        key=name.removesuffix('.py');account(run_command(key,command,root/(key.upper()+'_COMPLETE.json')))
    ledger.update(status='COMPLETE',ended=time.time());save();print('FULL_PIPELINE_COMPLETE',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--cpu-workers',type=int,default=8);main(p.parse_args())
