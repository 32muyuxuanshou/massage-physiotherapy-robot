"""Same frozen SAM/MHR adapters, true batch 16, best/last and isolated runs."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import torch
from torch.nn import functional as F
from fusion import RGBDBodyAdapter
from render_losses import MeshRenderer,loss_components
from check_native_r1 import parameter_hashes
from r3_common import load_official,read_cache,combine,cached_forward,metrics,aggregate,output_change,sha


def evaluate(model,rows,cache,renderer,out=None,ablation='correct',reference=None,batch_size=16):
    records=[];lookup={(r['identity'],r['pose_id'],r['camera_id']):r for r in rows}
    identities=sorted({r['identity'] for r in rows})
    with torch.no_grad():
        for start in range(0,len(rows),batch_size):
            chunk=rows[start:start+batch_size]
            r=[read_cache(str(cache/row['cache_file'])) for row in chunk]
            b,feature,d,v,rays,gt,target,mask,K=combine(r)
            if ablation in ['cross_identity','same_identity_other_pose']:
                donors=[]
                for row in chunk:
                    identity=(identities[(identities.index(row['identity'])+1)%len(identities)] if ablation=='cross_identity' else row['identity'])
                    pose=(row['pose_id'] if ablation=='cross_identity' else 1-row['pose_id'])
                    donors.append(read_cache(str(cache/lookup[identity,pose,row['camera_id']]['cache_file'])))
                d=torch.cat([x['depth'] for x in donors],0).cuda();v=torch.cat([x['valid'] for x in donors],0).cuda()
            elif ablation=='missing':v=torch.zeros_like(v)
            elif ablation.startswith('offset_'):
                offset=float(ablation.removeprefix('offset_'));d=torch.where(v,d+offset,d)
            elif ablation=='local_shuffle':
                d=d.clone();v=v.clone();ys=slice(128,384);xs=slice(96,288)
                for j,row in enumerate(chunk):
                    rng=np.random.default_rng(int(sha(cache/row['cache_file'])[:8],16))
                    permutation=torch.from_numpy(rng.permutation(16*12)).cuda()
                    for array in [d,v]:
                        patch=array[j:j+1,:,ys,xs].float()
                        mixed=F.unfold(patch,kernel_size=16,stride=16)[:,:,permutation]
                        array[j:j+1,:,ys,xs]=F.fold(mixed,(256,192),kernel_size=16,stride=16).to(array.dtype)
            o=cached_forward(model,b,feature,d,v,rays)
            values=metrics(o,gt,target,mask,K,renderer)
            for j,row in enumerate(chunk):
                single={k:x[j:j+1] for k,x in o.items() if torch.is_tensor(x)}
                entry=dict(identity=row['identity'],file=row['file'],pose_id=row['pose_id'],camera_id=row['camera_id'],ablation=ablation,metrics=values[j])
                if reference is not None:
                    ref={k:x.cuda() for k,x in reference[row['file']].items()}
                    entry['output_change_vs_correct']=output_change(single,ref)
                if out:
                    out.mkdir(parents=True,exist_ok=True)
                    torch.save({k:x.cpu() for k,x in single.items()},out/(Path(row['file']).stem+'.pt'))
                records.append(entry)
    report=aggregate(records)
    if reference is not None:
        report['output_change_identity_equal_mean']={k:np.asarray(np.mean([
            np.mean([r['output_change_vs_correct'][k] for r in records if r['identity']==identity],axis=0)
            for identity in identities],axis=0)).tolist() for k in records[0]['output_change_vs_correct']}
    return report


def train_one(official,rows,cache,config,output,mode,seed,lr,epochs,identity,benchmark_steps=None):
    output.mkdir(parents=True,exist_ok=False)
    torch.manual_seed(seed);np.random.seed(seed);torch.cuda.manual_seed_all(seed)
    rng=np.random.default_rng(seed)
    model=RGBDBodyAdapter(official,mode=mode).cuda()
    params=[p for p in model.fusion.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(params,lr=lr,weight_decay=config['weight_decay'])
    schedule=lambda epoch: min(1.,(epoch+1)/2) * (.1+.9*(1+math.cos(math.pi*max(0,epoch-1)/max(1,epochs-2)))/2)
    scheduler=torch.optim.lr_scheduler.LambdaLR(optimizer,schedule)
    renderer=MeshRenderer(official.head_pose.faces)
    train=[r for r in rows if r['role']=='TRAIN'];val=[r for r in rows if r['role']=='VAL']
    bs=config['batch_size'];curves=[];best=float('inf');start=time.monotonic()
    if benchmark_steps:train=train*math.ceil(benchmark_steps*bs/len(train))
    before=parameter_hashes(official)
    with (output/'training.jsonl').open('w') as log:
        for epoch in range(1,epochs+1):
            losses=[];step_times=[];ep_start=time.monotonic();order=rng.permutation(len(train))
            for step,begin in enumerate(range(0,len(train),bs)):
                step_start=time.monotonic()
                rr=[train[i] for i in order[begin:begin+bs]]
                rec=[read_cache(str(cache/r['cache_file'])) for r in rr]
                b,feature,d,v,rays,gt,target,mask,K=combine(rec)
                optimizer.zero_grad(set_to_none=True)
                o=cached_forward(model,b,feature,d,v,rays)
                components=loss_components(o,gt,target,mask,K,renderer)
                loss=sum(config['loss_weights'][k]*x for k,x in components.items())
                assert torch.isfinite(loss),'NONFINITE_TRAINING_LOSS'
                loss.backward();torch.nn.utils.clip_grad_norm_(params,config['gradient_clip_norm']);optimizer.step()
                value=float(loss.detach());losses.append(value)
                step_times.append(time.monotonic()-step_start)
                log.write(json.dumps(dict(epoch=epoch,step=step,loss=value,files=[r['file'] for r in rr],lr=optimizer.param_groups[0]['lr'],
                    components={k:float(x.detach()) for k,x in components.items()}))+'\n')
                if step%50==0:print('STEP',mode,seed,epoch,step,'/',math.ceil(len(train)/bs),'loss',round(value,5),flush=True)
                if benchmark_steps and step+1==benchmark_steps:
                    report=dict(status='STRUCTURAL_BATCH_BENCHMARK_ONLY',batch=bs,steps=benchmark_steps,
                        seconds=time.monotonic()-ep_start,seconds_per_step=(time.monotonic()-ep_start)/benchmark_steps,
                        warmed_seconds_per_step=float(np.mean(step_times[4:])),
                        peak_memory_bytes=torch.cuda.max_memory_allocated(),mode=mode)
                    (output/'BENCHMARK.json').write_text(json.dumps(report,indent=2))
                    print(json.dumps(report),flush=True);model._hook.remove();return report
            validation=evaluate(model,val,cache,renderer)
            score=validation['identity_equal_mean']['vertex_camera_mm']
            curve=dict(mode=mode,seed=seed,epoch=epoch,train_loss=float(np.mean(losses)),lr=optimizer.param_groups[0]['lr'],
                       val=validation['identity_equal_mean'],seconds=time.monotonic()-ep_start)
            curves.append(curve);print(json.dumps(curve),flush=True)
            scheduler.step()
            state=dict(fusion=model.fusion.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),
                mode=mode,seed=seed,epoch=epoch,lr=lr,execution_identity=identity,trainable_parameters=sum(p.numel() for p in params),
                torch_rng_state=torch.get_rng_state(),numpy_generator_state=rng.bit_generator.state)
            torch.save(state,output/'last.pt')
            if score<best:
                best=score;torch.save(state,output/'best.pt');(output/'BEST_VAL.json').write_text(json.dumps(validation,indent=2))
            (output/'CURVES.json').write_text(json.dumps(curves,indent=2));log.flush()
    last=evaluate(model,val,cache,renderer,output/'predictions/last')
    state=torch.load(output/'best.pt',map_location='cuda',weights_only=False);model.fusion.load_state_dict(state['fusion'])
    best_result=evaluate(model,val,cache,renderer,output/'predictions/best')
    report=dict(status='SYNTHETIC_VAL_COMPLETED_NO_TEST',mode=mode,seed=seed,lr=lr,epochs=epochs,best_epoch=state['epoch'],
        best=best_result,last=last,curves=curves,trainable_parameters=sum(p.numel() for p in params),
        seconds=time.monotonic()-start,peak_memory_bytes=torch.cuda.max_memory_allocated(),execution_identity=identity)
    assert before==parameter_hashes(official),'FROZEN_OFFICIAL_VALUES_CHANGED'
    (output/'RESULTS.json').write_text(json.dumps(report,indent=2))
    model._hook.remove();return report


def ablations(official,rows,cache,config,run_dir,mode):
    model=RGBDBodyAdapter(official,mode=mode).cuda()
    model.fusion.load_state_dict(torch.load(run_dir/'best.pt',map_location='cuda',weights_only=False)['fusion'])
    reference={r['file']:torch.load(run_dir/'predictions/best'/(Path(r['file']).stem+'.pt'),map_location='cpu',weights_only=False)
               for r in rows}
    renderer=MeshRenderer(official.head_pose.faces);results={}
    for kind in ['cross_identity','same_identity_other_pose','local_shuffle','missing']+[f'offset_{x}' for x in config['depth_offsets_m']]:
        result=evaluate(model,rows,cache,renderer,ablation=kind,reference=reference)
        results[kind]=result
        (run_dir/'DEPTH_ABLATIONS.json').write_text(json.dumps(results,indent=2))
        print('ABLATION',mode,kind,result['identity_equal_mean']['vertex_camera_mm'],flush=True)
    model._hook.remove()


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--source-commit',required=True)
    p.add_argument('--benchmark-steps',type=int);p.add_argument('--mode',default='cross_attention')
    p.add_argument('--real-cache',type=Path);p.add_argument('--real-points',type=Path)
    p.add_argument('--single-seed',type=int);p.add_argument('--single-lr',type=float)
    p.add_argument('--single-epochs',type=int);p.add_argument('--screen-only',action='store_true')
    a=p.parse_args();config=json.loads(a.config.read_text());manifest=json.loads((a.cache/'CACHE_MANIFEST.json').read_text())
    rows=manifest['records'];assert all(r['role']!='TEST' for r in rows)
    code=Path(__file__).parent
    identity=dict(source_commit=a.source_commit,config_sha256=sha(a.config),cache_manifest_sha256=sha(a.cache/'CACHE_MANIFEST.json'),config=config,
        runtime_code_sha256={p.name:sha(p) for p in code.glob('*.py')},
        checkpoint_sha256=sha(a.root/'checkpoints/official/sam-3d-body-vith/model.ckpt'),
        mhr_sha256=sha(a.root/'checkpoints/official/sam-3d-body-vith/assets/mhr_model.pt'))
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'EXECUTION_IDENTITY.json').write_text(json.dumps(identity,indent=2))
    official,_=load_official(a.root)
    if a.benchmark_steps:
        train_one(official,rows,a.cache,config,a.out/'benchmark',a.mode,0,config['lr_candidates'][0],1,identity,a.benchmark_steps);return
    if a.single_seed is not None:
        directory=a.out/'run'
        train_one(official,rows,a.cache,config,directory,a.mode,a.single_seed,a.single_lr,a.single_epochs,identity)
        if not a.screen_only and a.mode!='rgb_only':
            ablations(official,[r for r in rows if r['role']=='VAL'],a.cache,config,directory,a.mode)
        if not a.screen_only and a.real_cache:
            # Release the parent's frozen model before independent real inference.
            del official;torch.cuda.empty_cache()
            command=[sys.executable,str(code/'evaluate_r3_humman.py'),'--root',str(a.root),'--cache',str(a.real_cache),
                '--points',str(a.real_points),'--out',str(a.out/'real'),'--checkpoint',str(directory/'best.pt')]
            with (a.out/'real.log').open('w') as log:
                result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
            assert result.returncode==0,f'REAL_HELDOUT_EVALUATION_FAILED: {a.out}'
        (a.out/'CELL_COMPLETE.json').write_text(json.dumps(dict(mode=a.mode,seed=a.single_seed,screen=a.screen_only)))
        return
    # Frozen screen uses synthetic VAL only; complete all six cells before selection.
    screen=[]
    for lr in config['lr_candidates']:
        for mode in config['methods']:
            directory=a.out/'lr_screen'/f'{mode}_{lr}'
            report=(json.loads((directory/'RESULTS.json').read_text()) if (directory/'RESULTS.json').exists() else
                train_one(official,rows,a.cache,config,directory,mode,config['lr_screen_seed'],lr,config['lr_screen_epochs'],identity))
            screen.append(dict(mode=mode,lr=lr,score=report['last']['identity_equal_mean']['vertex_camera_mm']))
    scores={lr:float(np.mean([s['score'] for s in screen if s['lr']==lr])) for lr in config['lr_candidates']}
    chosen=min(config['lr_candidates'],key=lambda lr:(scores[lr],lr))
    (a.out/'LR_SELECTION.json').write_text(json.dumps(dict(screen=screen,mean_scores=scores,chosen=chosen,rule=config['lr_selection']),indent=2))
    reports=[];val=[r for r in rows if r['role']=='VAL'];real_jobs=[]
    for seed in config['train_seeds']:
        for mode in config['methods']:
            directory=a.out/'training'/f'{mode}_seed{seed}'
            report=(json.loads((directory/'RESULTS.json').read_text()) if (directory/'RESULTS.json').exists() else
                train_one(official,rows,a.cache,config,directory,mode,seed,chosen,config['epochs'],identity))
            reports.append(dict(mode=mode,seed=seed,best_epoch=report['best_epoch'],best=report['best']['identity_equal_mean'],last=report['last']['identity_equal_mean']))
            if mode!='rgb_only' and not (directory/'DEPTH_ABLATIONS.json').exists():ablations(official,val,a.cache,config,directory,mode)
            if a.real_cache:
                real_out=a.out/'real'/f'{mode}_seed{seed}'
                log_path=a.out/f'real_{mode}_seed{seed}.log'
                command=[sys.executable,str(code/'evaluate_r3_humman.py'),'--root',str(a.root),'--cache',str(a.real_cache),
                         '--points',str(a.real_points),'--out',str(real_out),'--checkpoint',str(directory/'best.pt')]
                with log_path.open('w') as log:
                    job=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                real_jobs.append((job,real_out))
                while not (real_out/'GPU_STAGE_DONE.json').exists():
                    if job.poll() is not None:raise RuntimeError(f'REAL_GPU_EVALUATION_FAILED: {log_path}')
                    time.sleep(2)
            summary={}
            for mm in config['methods']:
                rr=[r for r in reports if r['mode']==mm]
                if not rr:continue
                summary[mm]=dict(seeds=len(rr),metrics={k:dict(mean=float(np.mean([r['best'][k] for r in rr])),
                    sample_std=float(np.std([r['best'][k] for r in rr],ddof=1)) if len(rr)>1 else None) for k in rr[0]['best']})
            (a.out/'MULTISEED_SUMMARY.json').write_text(json.dumps(dict(status='COMPLETE' if len(reports)==9 else 'PARTIAL',runs=reports,
                summary=summary,test_evaluated=False,real_training_performed=False),indent=2))
    for job,path in real_jobs:
        assert job.wait()==0 and (path/'HUMMAN_RESULTS.json').exists(),f'REAL_HELDOUT_EVALUATION_FAILED: {path}'
    print('MULTISEED_COMPLETE',flush=True)


if __name__=='__main__':main()
