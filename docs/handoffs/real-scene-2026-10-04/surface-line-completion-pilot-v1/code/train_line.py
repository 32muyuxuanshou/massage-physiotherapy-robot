"""Two fixed training strategies, then hand off to a separate evaluation entry."""
import argparse,hashlib,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from line_net import LineNet
from data_line import read,write,sha,features,drop_blocks


def fixed_drop_seed(candidate,seed):
    return 2026100400+int(candidate.rsplit('_',1)[-1])*10+seed


def model_identity(model):
    digest=hashlib.sha256()
    for name,value in model.state_dict().items():
        digest.update(name.encode());digest.update(value.cpu().numpy().tobytes())
    return digest.hexdigest()


def objective(logits,xs,target,valid):
    probability=logits.softmax(-1);expected=(probability*xs[:,None,:]).sum(-1)
    gaussian=torch.exp(-.5*((xs[:,None,:]-target[:,:,None])/.003)**2)
    gaussian=gaussian/gaussian.sum(-1,keepdim=True)
    ce=-(gaussian*logits.log_softmax(-1)).sum(-1)
    coordinate=F.smooth_l1_loss((expected-target)/.01,torch.zeros_like(target),reduction='none')
    continuity=((expected[:,2:]-2*expected[:,1:-1]+expected[:,:-2])/.01).square().mean()
    loss=((ce+.1*coordinate)*valid).sum()/valid.sum()+.01*continuity
    return loss,expected


def load_case(row):
    with np.load(row['path']) as z:
        return {k:z[k] for k in ['points_m','xs_m','features','target_x_m','target_row_valid','ys_m']}


def train(root):
    torch.set_num_threads(4);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    rows=read(root/'DATA_MANIFEST.json');config=read(root/'CONFIG.json')
    for asset in read(root/'SOURCE_FREEZE.json'):assert sha(asset['path'])==asset['sha256'],asset['path']
    training=[(r,load_case(r)) for r in rows if r['role']=='train']
    development=[]
    for r in rows:
        if r['role']!='dev':continue
        case=load_case(r)
        for seed in [0,1,2]:
            visible,_=drop_blocks(case['points_m'],fixed_drop_seed(r['candidate_id'],seed))
            tensor,_=features(visible,case['xs_m'],case['ys_m'])
            development.append((tensor,case))
    device=torch.device('cuda:0');ledger=[];(root/'checkpoints').mkdir(exist_ok=True)
    for seed in config['seeds']:
        for strategy in config['strategies']:
            start=time.monotonic();torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
            model=LineNet().to(device);initial=model_identity(model);optimizer=torch.optim.Adam(model.parameters(),lr=config['lr'])
            rng=np.random.default_rng(seed);best=float('inf');history=[]
            checkpoint=root/'checkpoints'/f'{strategy}_seed{seed}.pth'
            for epoch in range(config['epochs']):
                model.train();order=rng.permutation(len(training));losses=[]
                for offset in range(0,len(order),config['batch']):
                    tensors=[];cases=[]
                    for index in order[offset:offset+config['batch']]:
                        row,case=training[index];cases.append(case)
                        if strategy=='BLOCK_AUG':
                            aug_seed=seed*10000000+epoch*1000+int(index)
                            visible,_=drop_blocks(case['points_m'],aug_seed)
                            tensor,_=features(visible,case['xs_m'],case['ys_m'])
                        else:tensor=case['features']
                        tensors.append(tensor)
                    x=torch.as_tensor(np.stack(tensors),device=device)
                    xs=torch.as_tensor(np.stack([c['xs_m'] for c in cases]),dtype=torch.float32,device=device)
                    target=torch.as_tensor(np.stack([c['target_x_m'] for c in cases]),dtype=torch.float32,device=device)
                    valid=torch.as_tensor(np.stack([c['target_row_valid'] for c in cases]),device=device)
                    optimizer.zero_grad();loss,_=objective(model(x),xs,target,valid);loss.backward();optimizer.step()
                    losses.append(float(loss.detach()))
                model.eval();errors=[]
                with torch.no_grad():
                    for offset in range(0,len(development),4):
                        batch=development[offset:offset+4]
                        x=torch.as_tensor(np.stack([t for t,c in batch]),device=device)
                        xs=torch.as_tensor(np.stack([c['xs_m'] for t,c in batch]),dtype=torch.float32,device=device)
                        expectation=(model(x).softmax(-1)*xs[:,None,:]).sum(-1).cpu().numpy()
                        errors.extend(float(np.mean(np.abs(p[c['target_row_valid']]-c['target_x_m'][c['target_row_valid']]))*1000)
                                      for p,(_,c) in zip(expectation,batch))
                score=float(np.mean(errors));improved=score<best
                if improved:
                    best=score;torch.save(dict(state_dict=model.state_dict(),seed=seed,strategy=strategy,
                        epoch=epoch+1,dev_lateral_mean_mm=score,initial_state_sha256=initial),checkpoint)
                history.append(dict(epoch=epoch+1,training_loss=float(np.mean(losses)),dev_lateral_mean_mm=score,selected=improved))
                if epoch%10==0 or epoch==config['epochs']-1:
                    print(strategy,seed,'epoch',epoch+1,'loss',round(history[-1]['training_loss'],4),'dev_mm',round(score,3),flush=True)
            log=root/f'TRAIN_{strategy}_seed{seed}.json';write(log,history)
            selected=torch.load(checkpoint,map_location='cpu',weights_only=True)
            ledger.append(dict(strategy=strategy,seed=seed,epochs=len(history),selected_epoch=selected['epoch'],
                dev_lateral_mean_mm=best,parameter_count=sum(p.numel() for p in model.parameters()),
                initial_state_sha256=initial,checkpoint_path=str(checkpoint),checkpoint_sha256=sha(checkpoint),
                history_path=str(log),history_sha256=sha(log),seconds=time.monotonic()-start,
                evaluation_cases_loaded=False))
            write(root/'TRAINING_LEDGER.json',ledger)
            print('TRAIN_COMPLETE',strategy,seed,'best',best,'seconds',ledger[-1]['seconds'],flush=True)
    assert len(ledger)==6
    for seed in [0,1,2]:
        pair=[r for r in ledger if r['seed']==seed];assert pair[0]['initial_state_sha256']==pair[1]['initial_state_sha256']
    write(root/'TRAINING_COMPLETE.json',dict(status='COMPLETE',models=6,evaluation_labels_loaded=False,
        torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),ledger_sha256=sha(root/'TRAINING_LEDGER.json')))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args();train(args.root)
