"""Matched R4 synthetic training with epoch-boundary exact state resumption."""
import os
os.environ.setdefault('MOMENTUM_ENABLED', '0')
os.environ.setdefault('PYOPENGL_PLATFORM', 'egl')
import argparse, json, math, time
from pathlib import Path
import numpy as np
import torch
from fusion_r4 import R4Adapter
from r3_common import load_official, read_cache, combine, cached_forward, sha
from render_losses import MeshRenderer, loss_components
from check_native_r1 import parameter_hashes
from train_r3_multiseed import evaluate


def train(root, output, mode, seed, epochs, train_ids, source_commit, resume=False, stop_after=None, deadline=None):
    torch.set_num_threads(2);torch.manual_seed(seed);np.random.seed(seed);torch.cuda.manual_seed_all(seed)
    rng=np.random.default_rng(seed);cache=root/'datasets/cache/native_scale_v2'
    rows=json.loads((cache/'CACHE_MANIFEST.json').read_text())['records']
    assert all(r['role']!='TEST' for r in rows)
    ids=sorted({r['identity'] for r in rows if r['role']=='TRAIN'})[:train_ids]
    training=[r for r in rows if r['role']=='TRAIN' and r['identity'] in ids]
    validation=[r for r in rows if r['role']=='VAL']
    cfg=json.loads((Path(__file__).parent/'R3_SCALE_CONFIG_V1.json').read_text())
    identity=dict(source_commit=source_commit,mode=mode,seed=seed,epochs=epochs,train_ids=ids,
        cache_manifest_sha256=sha(cache/'CACHE_MANIFEST.json'),test_loaded=False,
        config=cfg,code_sha256={n:sha(Path(__file__).parent/n) for n in ['fusion_r4.py','train_r4.py','fusion.py','render_losses.py','r3_common.py']})
    output.mkdir(parents=True,exist_ok=resume)
    official,_=load_official(root);before=parameter_hashes(official)
    model=R4Adapter(official,mode).cuda();params=[p for p in model.fusion.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(params,lr=3e-4,weight_decay=cfg['weight_decay'])
    schedule=lambda epoch:min(1.,(epoch+1)/2)*(.1+.9*(1+math.cos(math.pi*max(0,epoch-1)/max(1,epochs-2)))/2)
    scheduler=torch.optim.lr_scheduler.LambdaLR(optimizer,schedule)
    renderer=MeshRenderer(official.head_pose.faces);curves=[];best=float('inf');first=1
    if resume:
        state=torch.load(output/'last.pt',map_location='cpu',weights_only=False)
        assert state['execution_identity']==identity,'R4_RESUME_CONTRACT_CHANGED'
        model.fusion.load_state_dict(state['fusion']);optimizer.load_state_dict(state['optimizer']);scheduler.load_state_dict(state['scheduler'])
        torch.set_rng_state(state['torch_rng_state']);torch.cuda.set_rng_state_all(state['cuda_rng_state'])
        rng.bit_generator.state=state['numpy_generator_state'];best=state['best_score'];first=state['epoch']+1
        curves=json.loads((output/'CURVES.json').read_text())
    (output/'EXECUTION_IDENTITY.json').write_text(json.dumps(identity,indent=2))
    started=time.monotonic();bs=16;reason='COMPLETED'
    with (output/'training.jsonl').open('a' if resume else 'w') as log:
        for epoch in range(first,epochs+1):
            # All interruption points are after a complete, saved epoch.
            if deadline and time.time()>deadline:reason='DEADLINE_EPOCH_BOUNDARY';break
            ep=time.monotonic();order=rng.permutation(len(training));losses=[];times=[]
            for step, begin in enumerate(range(0,len(training),bs)):
                tick=time.monotonic();rr=[training[i] for i in order[begin:begin+bs]]
                b,f,d,v,rays,gt,target,mask,K=combine([read_cache(str(cache/r['cache_file'])) for r in rr])
                optimizer.zero_grad(set_to_none=True);o=cached_forward(model,b,f,d,v,rays)
                components=loss_components(o,gt,target,mask,K,renderer)
                loss=sum(cfg['loss_weights'][k]*x for k,x in components.items());assert torch.isfinite(loss)
                loss.backward();torch.nn.utils.clip_grad_norm_(params,cfg['gradient_clip_norm']);optimizer.step()
                value=float(loss.detach());losses.append(value);times.append(time.monotonic()-tick)
                log.write(json.dumps(dict(epoch=epoch,step=step,loss=value,lr=optimizer.param_groups[0]['lr'],files=[r['file'] for r in rr],
                    components={k:float(x.detach()) for k,x in components.items()}))+chr(10))
                if step%25==0:log.flush();print('STEP',mode,seed,epoch,step,'/',math.ceil(len(training)/bs),'LOSS',value,flush=True)
            val=evaluate(model,validation,cache,renderer,batch_size=16);score=val['identity_equal_mean']['vertex_camera_mm']
            curve=dict(mode=mode,seed=seed,epoch=epoch,train_loss=float(np.mean(losses)),val=val['identity_equal_mean'],
                lr=optimizer.param_groups[0]['lr'],seconds=time.monotonic()-ep,steady_batch16_seconds=float(np.mean(times[4:] or times)))
            curves.append(curve);print('EPOCH',json.dumps(curve),flush=True);scheduler.step()
            improved=score<best;best=min(best,score)
            state=dict(fusion=model.fusion.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),
                mode=mode,seed=seed,epoch=epoch,lr=3e-4,execution_identity=identity,best_score=best,
                torch_rng_state=torch.get_rng_state(),cuda_rng_state=torch.cuda.get_rng_state_all(),numpy_generator_state=rng.bit_generator.state,
                trainable_parameters=sum(p.numel() for p in params))
            torch.save(state,output/'last.pt')
            if improved:torch.save(state,output/'best.pt');(output/'BEST_VAL.json').write_text(json.dumps(val,indent=2))
            (output/'CURVES.json').write_text(json.dumps(curves,indent=2));log.flush()
            if stop_after and epoch>=stop_after:reason='REQUESTED_EPOCH_BOUNDARY';break
    assert before==parameter_hashes(official),'OFFICIAL_WEIGHT_CHANGED'
    if reason=='COMPLETED':
        last=evaluate(model,validation,cache,renderer,output/'predictions/last')
        state=torch.load(output/'best.pt',weights_only=False);model.fusion.load_state_dict(state['fusion'])
        best_result=evaluate(model,validation,cache,renderer,output/'predictions/best')
        report=dict(status='SYNTHETIC_VAL_COMPLETED_NO_TEST',mode=mode,seed=seed,epochs=epochs,best_epoch=state['epoch'],
            best=best_result,last=last,curves=curves,trainable_parameters=sum(p.numel() for p in params),
            peak_memory_bytes=torch.cuda.max_memory_allocated(),seconds=time.monotonic()-started,execution_identity=identity)
        (output/'RESULTS.json').write_text(json.dumps(report,indent=2))
    else:
        (output/'PAUSE_RECORD.json').write_text(json.dumps(dict(reason=reason,last_epoch=curves[-1]['epoch'] if curves else 0,resumable=True)))
    model.remove_hooks();print('R4_TRAINING_END',mode,seed,reason,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mode',choices=['g0','g1','g2','g3'],required=True);p.add_argument('--seed',type=int,default=11)
    p.add_argument('--epochs',type=int,default=30);p.add_argument('--train-ids',type=int,default=400)
    p.add_argument('--source-commit',required=True);p.add_argument('--resume',action='store_true');p.add_argument('--stop-after',type=int)
    p.add_argument('--deadline-unix',type=float)
    a=p.parse_args();train(a.root,a.out,a.mode,a.seed,a.epochs,a.train_ids,a.source_commit,a.resume,a.stop_after,a.deadline_unix)
