"""Twelve matched Fine continuations; selection never reads real results."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import torch
from core import WORK,CFG,G,FineOnly,load_parent,batch,objective,gradients,evaluate,sha
from frozen_render_losses import MeshRenderer


def rank(r):return hashlib.sha256(('r51-probe-20261015:'+r['key']).encode()).hexdigest()


def selected_rows(seed):
    return json.loads((WORK/'prepared'/('s%d'%seed)/'MANIFEST.json').read_text())['records']


def gradient_ledger(model,renderer,rows,seed,arm,lam):
    result={}
    with torch.enable_grad():
        for domain in ['native','scan']:
            probe=sorted([r for r in rows if r['domain']==domain and r['role']=='TRAIN'],key=rank)[:8]
            x=batch(probe,seed);value,weighted,terms,_,_=objective(model,renderer,x,domain,arm,lam)
            result[domain]=dict(last_layer=gradients(model,weighted),losses={k:float(v.detach()) for k,v in terms.items()})
    return result


def selection(value,baseline):
    n=value['native']['aggregate']['equal_mean'];s=value['scan']['aggregate']['equal_mean']
    bn=baseline['native']['aggregate']['equal_mean'];bs=baseline['scan']['aggregate']['equal_mean']
    eligible=all(current[k]>=start[k]-.01 for current,start in [(n,bn),(s,bs)] for k in ['hit_rate','iou'])
    return dict(old=n['vertex_camera_mm'],joint=.5*(n['full_mask_median_mm']/bn['full_mask_median_mm']+s['full_mask_median_mm']/bs['full_mask_median_mm']),joint_eligible=eligible)


def run(seed,arm_name):
    torch.set_num_threads(2);torch.manual_seed(seed);np.random.seed(seed)
    torch.backends.cuda.matmul.allow_tf32=False
    faces=torch.from_numpy(np.load(G/'assets/faces.npy')).cuda();renderer=MeshRenderer(faces)
    parent=load_parent(seed,renderer);model=FineOnly(parent).cuda();rows=selected_rows(seed)
    arm=CFG['arms'][arm_name];lam=json.loads((WORK/'L2_CALIBRATION.json').read_text())['lambda'] if arm['l2'] else 0.
    out=WORK/'runs'/('%s_s%d'%(arm_name,seed));out.mkdir(parents=True,exist_ok=True)
    assert not (out/'RESULTS.json').exists(),'Already completed; do not restart'
    baseline=json.loads((WORK/('BASELINE_s%d.json'%seed)).read_text())
    opt=torch.optim.AdamW(model.parameters(),lr=CFG['learning_rate'],weight_decay=CFG['weight_decay'])
    indices={d:[r for r in rows if r['domain']==d and r['role']=='TRAIN'] for d in ['native','scan']}
    validation={d:[r for r in rows if r['domain']==d and r['role']=='VAL'] for d in ['native','scan']}
    assert (len(indices['native']),len(indices['scan']))==(512,768)
    initial={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    initial_sha=hashlib.sha256(b''.join(v.numpy().tobytes() for v in initial.values())).hexdigest()
    curves=[];best_old=selection(baseline,baseline)['old'];best_joint=1.;old_epoch=joint_epoch=0
    torch.save(dict(model=initial,epoch=0,seed=seed,arm=arm_name),out/'epoch_00.pt')
    gradient_records=[dict(epoch=0,**gradient_ledger(model,renderer,rows,seed,arm,lam))]
    first=1
    if (out/'CURVES.json').exists():
        curves=json.loads((out/'CURVES.json').read_text());gradient_records=json.loads((out/'GRADIENT_LEDGER.json').read_text())
        last=curves[-1]['epoch'];saved=torch.load(out/('epoch_%02d.pt'%last),map_location='cpu',weights_only=False)
        assert saved['config_sha256']==sha(WORK/'EXPERIMENT.json') and saved['initial_fine_sha256']==initial_sha
        model.load_state_dict(saved['model']);opt.load_state_dict(saved['optimizer']);first=last+1
        for entry in curves:
            if 'validation' not in entry:continue
            score=entry['validation']['selection'];ep=entry['epoch']
            if score['old']<best_old:best_old=score['old'];old_epoch=ep
            if score['joint_eligible'] and score['joint']<best_joint:best_joint=score['joint'];joint_epoch=ep
    for epoch in range(first,CFG['epochs']+1):
        started=time.monotonic();model.train();rng=np.random.default_rng(seed*1000+epoch)
        orders={d:rng.permutation(len(v)) for d,v in indices.items()};losses=[]
        for step in range(32):
            opt.zero_grad(set_to_none=True);total=0.
            for domain,length in [('native',16),('scan',24)]:
                order=orders[domain][step*length:(step+1)*length]
                for start in range(0,length,4):
                    rr=[indices[domain][i] for i in order[start:start+4]];x=batch(rr,seed)
                    value,*_=objective(model,renderer,x,domain,arm,lam)
                    assert torch.isfinite(value),'NONFINITE_OBJECTIVE'
                    (value*len(rr)/length).backward();total+=float(value.detach())*len(rr)/length
            torch.nn.utils.clip_grad_norm_(model.parameters(),CFG['gradient_clip']);opt.step();losses.append(total)
        checkpoint=out/('epoch_%02d.pt'%epoch)
        torch.save(dict(model=model.state_dict(),optimizer=opt.state_dict(),epoch=epoch,seed=seed,arm=arm_name,config_sha256=sha(WORK/'EXPERIMENT.json'),initial_fine_sha256=initial_sha),checkpoint)
        row=dict(epoch=epoch,train_loss=float(np.mean(losses)),training_seconds=time.monotonic()-started,
            data_order_sha256={d:hashlib.sha256(v.tobytes()).hexdigest() for d,v in orders.items()})
        if epoch in CFG['evaluation_epochs']:
            value={d:evaluate(model,renderer,rr,seed) for d,rr in validation.items()}
            (out/('VAL_%02d.json'%epoch)).write_text(json.dumps(value,indent=2))
            score=selection(value,baseline);row['validation']=dict(selection=score,**{d:v['aggregate'] for d,v in value.items()})
            if score['old']<best_old:best_old=score['old'];old_epoch=epoch
            if score['joint_eligible'] and score['joint']<best_joint:best_joint=score['joint'];joint_epoch=epoch
            gradient_records.append(dict(epoch=epoch,**gradient_ledger(model,renderer,rows,seed,arm,lam)))
        (out/'GRADIENT_LEDGER.json').write_text(json.dumps(gradient_records,indent=2))
        curves.append(row);(out/'CURVES.json').write_text(json.dumps(curves,indent=2))
        print('EPOCH',arm_name,seed,epoch,'train',round(row['train_loss'],6),'seconds',round(time.monotonic()-started,1),flush=True)
    result=dict(status='TRAIN_VAL_COMPLETE',seed=seed,arm=arm_name,epochs=CFG['epochs'],old_best_epoch=old_epoch,joint_best_epoch=joint_epoch,last_epoch=CFG['epochs'],l2_lambda=lam,initial_fine_sha256=initial_sha,config_sha256=sha(WORK/'EXPERIMENT.json'),sealed_TEST_read=False,real_evaluation_read=False,coarse_trainable=False,body_trainable=False,interpretation='Matched Fine continuation with frozen corresponding parent Coarse; not original R5 training reproduction')
    (out/'RESULTS.json').write_text(json.dumps(result,indent=2));print('UNIT_COMPLETE',arm_name,seed,old_epoch,joint_epoch,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--arm',choices=list(CFG['arms']),required=True);a=p.parse_args();run(a.seed,a.arm)
