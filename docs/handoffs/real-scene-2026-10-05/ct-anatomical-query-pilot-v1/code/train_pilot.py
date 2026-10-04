"""Fixed-budget seed runs; choose checkpoint by development cases only."""
import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
import torch

from model import AnatomicalQuery
from prepare_pilot import OUT, sha, write


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--method',required=True);parser.add_argument('--seed',type=int,required=True)
    args=parser.parse_args();torch.set_num_threads(2)
    torch.manual_seed(args.seed);np.random.seed(args.seed);random.seed(args.seed)
    torch.cuda.manual_seed_all(args.seed);torch.backends.cudnn.benchmark=False
    config=json.loads((OUT/'PROTOCOL.json').read_text());rows=json.loads((OUT/'CASE_MANIFEST.json').read_text())
    data={}
    for role in ['train','dev']:
        cohort=[r for r in rows if r['eligible'] and r['role']==role]
        values=[dict(np.load(r['path'])) for r in cohort]
        data[role]={k:torch.tensor(np.stack([v[k] for v in values]),device='cuda') for k in ['input','target_uv','target_valid']}
        data[role]['scale']=torch.tensor(np.array([r['field_size_xz_mm'] for r in cohort]),device='cuda',dtype=torch.float32)
    model=AnatomicalQuery(args.method).cuda();optimizer=torch.optim.AdamW(model.parameters(),lr=config['lr'],weight_decay=.0001)
    path=OUT/'models'/(args.method+'_seed'+str(args.seed));path.mkdir(parents=True,exist_ok=True)
    best=float('inf');log=[];start=time.monotonic()
    for epoch in range(1,config['epochs']+1):
        model.train();order=torch.randperm(len(data['train']['input']),device='cuda');losses=[]
        for batch in order.split(config['batch_size']):
            x=data['train'];pred=model(x['input'][batch]);valid=x['target_valid'][batch]
            loss=((pred-x['target_uv'][batch]).square().sum(-1)*valid).sum()/valid.sum()
            optimizer.zero_grad();loss.backward();optimizer.step();losses.append(float(loss.detach()))
        if epoch%10==0:
            model.eval()
            with torch.no_grad():
                x=data['dev'];pred=model(x['input']);error=torch.linalg.norm((pred-x['target_uv'])*x['scale'][:,None,:],dim=-1)
                score=float((error*x['target_valid']).sum()/x['target_valid'].sum())
            row=dict(epoch=epoch,train_loss=float(np.mean(losses)),dev_target_mean_xz_mm=score,seconds=time.monotonic()-start);log.append(row)
            if score<best:
                best=score;torch.save(dict(state_dict=model.state_dict(),method=args.method,seed=args.seed,epoch=epoch,dev_score=score,config_sha256=sha(OUT/'PROTOCOL.json')),path/'best.pt')
            print(args.method,args.seed,epoch,round(score,3),flush=True)
    write(path/'TRAINING.json',dict(method=args.method,seed=args.seed,history=log,seconds=time.monotonic()-start,
          checkpoint_sha256=sha(path/'best.pt'),config_sha256=sha(OUT/'PROTOCOL.json'),manifest_sha256=sha(OUT/'CASE_MANIFEST.json'),
          parameter_count=sum(p.numel() for p in model.parameters()),test_data_loaded=False))


if __name__=='__main__':main()
