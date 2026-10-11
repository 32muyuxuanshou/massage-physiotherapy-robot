"""Matched fresh runs, complete scan passes, exact epoch-boundary resume."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0');os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,hashlib,json,math,time
from pathlib import Path
import numpy as np
import torch
from data import rows,batch
from engine import Engine,loss,native_values


def validation(engine,records,micro=2):
    values=[];engine.eval()
    with torch.no_grad():
        for offset in range(0,len(records),micro):
            rr=records[offset:offset+micro];x=batch(rr);o,tr=engine(x)
            result=native_values(o,x)
            for i,r in enumerate(rr):
                values.append(dict(identity=r['identity'],file=r['cache_file'],
                    **{k:float(v[i]) for k,v in result.items()}))
    ids=sorted({v['identity'] for v in values})
    per={i:{k:float(np.mean([v[k] for v in values if v['identity']==i])) for k in result} for i in ids}
    return dict(mean={k:float(np.mean([v[k] for v in per.values()])) for k in result},per_identity=per,records=values)


def run(a):
    torch.set_num_threads(2);torch.manual_seed(a.seed);np.random.seed(a.seed);torch.cuda.manual_seed_all(a.seed)
    cfg=json.loads(a.config.read_text());paths=json.loads(a.paths.read_text())
    n=rows(paths['native_cache'],'native')
    s=rows(paths['scan_cache'],'scan') if a.epochs>cfg['native_epochs'] else []
    train=[r for r in n if r['role']=='TRAIN'];val=[r for r in n if r['role']=='VAL'];scan=[r for r in s if r['role']=='TRAIN']
    assert (len(train),len(val))==(3200,400)
    if a.epochs>cfg['native_epochs']:assert len(scan)==2304
    engine=Engine(a.mode,paths);params=engine.trainable()
    optimizer=torch.optim.AdamW(params,lr=a.lr,weight_decay=cfg['weight_decay'])
    weak=json.loads(Path(paths['weak_freeze']).read_text())['weights'] if a.epochs>cfg['native_epochs'] else {}
    output=a.out;output.mkdir(parents=True,exist_ok=a.resume)
    identity=dict(mode=a.mode,seed=a.seed,lr=a.lr,epochs=a.epochs,config_sha256=hashlib.sha256(a.config.read_bytes()).hexdigest(),
        paths_sha256=hashlib.sha256(a.paths.read_bytes()).hexdigest(),test_read=False,camera_B_read=False,
        input_version='shared_zero_baseline_sensor_lattice_v1',checkpoint_metric=cfg['checkpoint_selection'])
    code=Path(__file__).parent
    core=[code/n for n in ['model.py','data.py','engine.py','train.py']]
    core += [code.parent/n for n in ['fusion.py','fusion_r4.py','r3_common.py','render_losses.py','geometry.py','r5_camera_only/camera_head.py']]
    identity['training_code_sha256']={str(p.relative_to(code.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in core}
    identity['native_manifest_sha256']=hashlib.sha256((Path(paths['native_cache'])/'CACHE_MANIFEST.json').read_bytes()).hexdigest()
    if a.epochs>cfg['native_epochs']:
        identity['scan_manifest_sha256']=hashlib.sha256((Path(paths['scan_cache'])/'CACHE_MANIFEST.json').read_bytes()).hexdigest()
        identity['weak_loss_freeze_sha256']=hashlib.sha256(Path(paths['weak_freeze']).read_bytes()).hexdigest()
    rng=np.random.default_rng(a.seed);first=1;best=float('inf');curves=[]
    if a.resume:
        state=torch.load(output/'last.pt',weights_only=False);assert state['identity']==identity
        engine.load_checkpoint_state(state['model']);optimizer.load_state_dict(state['optimizer'])
        torch.set_rng_state(state['torch_rng']);torch.cuda.set_rng_state_all(state['cuda_rng']);rng.bit_generator.state=state['numpy_rng']
        first=state['epoch']+1;best=state['best_score'];curves=json.loads((output/'CURVES.json').read_text())
    (output/'EXECUTION_IDENTITY.json').write_text(json.dumps(identity,indent=2))
    for epoch in range(first,a.epochs+1):
        started=time.monotonic();mixed=epoch>cfg['native_epochs']
        segment_epoch=epoch-cfg['native_epochs'] if mixed else epoch
        length=cfg['mixed_epochs'] if mixed else min(a.epochs,cfg['native_epochs'])
        multiplier=min(1.,segment_epoch/2)*(.1+.9*(1+math.cos(math.pi*max(0,segment_epoch-2)/max(1,length-2)))/2)
        for group in optimizer.param_groups:group['lr']=a.lr*multiplier
        order=rng.permutation(len(train));scan_order=rng.permutation(len(scan)) if mixed else np.asarray([],dtype=int)
        steps=math.ceil(len(train)/cfg['effective_native_batch']);scan_parts=np.array_split(scan_order,steps)
        trace=[];engine.train();enable_fine=epoch>cfg['fine_warmup_epochs']
        for step,start in enumerate(range(0,len(train),cfg['effective_native_batch'])):
            ni=order[start:start+cfg['effective_native_batch']];si=scan_parts[step]
            optimizer.zero_grad(set_to_none=True);totals={}
            for indices,pool,micro,domain in [(ni,train,cfg['native_microbatch'],'native'),(si,scan,cfg['scan_microbatch'],'scan')]:
                for offset in range(0,len(indices),micro):
                    selected=indices[offset:offset+micro];rr=[pool[i] for i in selected]
                    x=batch(rr,seed=a.seed,epoch=epoch);o,diag=engine(x,enable_fine)
                    objective,components=loss(engine,o,diag,x,cfg,weak,enable_fine)
                    assert torch.isfinite(objective),'NONFINITE_LOSS'
                    fraction=len(selected)/(len(scan)/steps if domain=='scan' else len(indices))
                    (objective*fraction).backward()
                    for k,v in components.items():totals[domain+'/'+k]=totals.get(domain+'/'+k,0)+float(v.detach())*fraction
            norm=float(torch.nn.utils.clip_grad_norm_(params,cfg['gradient_clip']))
            optimizer.step();trace.append(totals)
            if step%25==0:print('STEP',a.mode,a.seed,epoch,step,steps,'GRAD',round(norm,5),flush=True)
        result=validation(engine,val,cfg['native_microbatch']);score=result['mean']['vertex_camera_mm']
        improved=score<best;best=min(best,score)
        row=dict(epoch=epoch,lr=optimizer.param_groups[0]['lr'],val=result['mean'],seconds=time.monotonic()-started,
            train_components={k:float(np.mean([r.get(k,0) for r in trace])) for k in trace[0]},
            native_samples=len(order),scan_samples=len(scan_order),scan_unique_samples=len(set(scan_order.tolist())),
            native_order_sha256=hashlib.sha256(order.tobytes()).hexdigest(),scan_order_sha256=hashlib.sha256(scan_order.tobytes()).hexdigest(),
            peak_memory_bytes=torch.cuda.max_memory_allocated(),fine_enabled=enable_fine)
        curves.append(row)
        state=dict(model=engine.checkpoint_state(),optimizer=optimizer.state_dict(),epoch=epoch,best_score=best,identity=identity,
            torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all(),numpy_rng=rng.bit_generator.state)
        torch.save(state,output/'last.tmp.pt');(output/'last.tmp.pt').replace(output/'last.pt')
        if improved:
            torch.save(state,output/'best.tmp.pt');(output/'best.tmp.pt').replace(output/'best.pt')
            (output/'BEST_VAL.json').write_text(json.dumps(result,indent=2))
        (output/'CURVES.json').write_text(json.dumps(curves,indent=2))
        print('EPOCH',a.mode,a.seed,json.dumps(row),flush=True)
    engine.load_checkpoint_state(torch.load(output/'best.pt',weights_only=False)['model'])
    final=validation(engine,val,cfg['native_microbatch'])
    (output/'RESULTS.json').write_text(json.dumps(dict(status='TRAIN_VAL_COMPLETE_NO_TEST',best=final,
        epochs_completed=len(curves),identity=identity,trainable_parameters=sum(p.numel() for p in params)),indent=2))
    engine.close();print('TRAIN_COMPLETE',a.mode,a.seed,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['config','paths','out']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--mode',required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--lr',type=float,required=True);p.add_argument('--epochs',type=int,default=50);p.add_argument('--resume',action='store_true')
    run(p.parse_args())
