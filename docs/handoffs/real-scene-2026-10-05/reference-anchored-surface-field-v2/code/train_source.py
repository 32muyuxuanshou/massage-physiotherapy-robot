"""Adult source training only; uses frozen V3 image roles and explicit ref pair."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import Dataset, DataLoader

from anchored_field import AnchoredField
from source_batch import sample_pack

SERVER=Path('/raid5/xuhd/datasets/anatomical_surface_method_foundation_20261005')


class SourceDataset(Dataset):
    def __init__(self,rows,seed,augment):
        self.rows=rows;self.seed=seed;self.augment=augment;self.epoch=0

    def __len__(self):return len(self.rows)

    def __getitem__(self,index):
        seed=self.seed+index+self.epoch*100000
        item,_=sample_pack(self.rows[index]['pack'],seed,1024,256)
        if self.augment:
            rng=np.random.default_rng(seed+777)
            if rng.random()<.4:
                # Same query geometry and references. Only observed visual context
                # is reduced; both supplied references remain explicitly available.
                observed=item['observed'];fraction=rng.uniform(.6,.9);start=rng.uniform(0,1-fraction)
                lo,hi=np.quantile(observed[:,2],[start,start+fraction])
                kept=observed[(observed[:,2]>=lo)&(observed[:,2]<=hi)]
                item['observed']=kept[rng.choice(len(kept),1024,replace=True)]
        return item


def loss(pred,batch,joint):
    anatomy=F.smooth_l1_loss(pred['anatomical_coordinates'],batch['anatomical_coordinates'],beta=.05)
    ray=F.smooth_l1_loss(pred['ray_delta'],batch['ray_target'],beta=.02)
    return anatomy+.25*ray if joint else anatomy,anatomy,ray


def paired(row):
    return row['eligible'] and row['valid_levels'][3] and row['valid_levels'][14]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=SERVER/'v3_dataset')
    parser.add_argument('--output',type=Path,default=SERVER.parent/'reference_anchored_surface_field_v2_20261005')
    parser.add_argument('--model',choices=['SOFT_ANATOMY','HARD_ANATOMY','HARD_JOINT'],default='HARD_JOINT')
    parser.add_argument('--seed',type=int,choices=[0,1,2],default=0)
    args=parser.parse_args();torch.set_num_threads(4);torch.manual_seed(args.seed)
    rows=json.loads((args.source/'CASE_MANIFEST.json').read_text())
    roles=json.loads((SERVER/'SOURCE_ROLE_FREEZE.json').read_text())
    expected={r['case'] for r in roles['rows'] if r['age_years'] is not None and r['age_years']>=18}
    assert {r['case'] for r in rows}==expected, 'FULL_ADULT_SOURCE_PREPARATION_REQUIRED'
    train=[r for r in rows if paired(r) and r['role']=='TRAIN']
    dev=[r for r in rows if paired(r) and r['role']=='DEVELOPMENT']
    assert len(train)>=200 and len(dev)>=20, 'QUALIFIED_PAIR_COHORT_TOO_SMALL'
    data=SourceDataset(train,args.seed,True);dl=DataLoader(data,batch_size=8,shuffle=True,num_workers=0,generator=torch.Generator().manual_seed(args.seed))
    validation=DataLoader(SourceDataset(dev,args.seed+9000000,False),batch_size=8,num_workers=0)
    model=AnchoredField().cuda();opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    output=args.output/(args.model+'_seed'+str(args.seed));output.mkdir(parents=True,exist_ok=True)
    trace=[];best=float('inf');started=time.time()
    for epoch in range(60):
        data.epoch=epoch;model.train();train_loss=[]
        for batch in dl:
            batch={k:v.cuda() for k,v in batch.items()}
            pred=model(batch['observed'],batch['query'],batch['references'],batch['reference_present'],batch['query_rays'],hard=args.model!='SOFT_ANATOMY')
            total,anatomy,ray=loss(pred,batch,args.model=='HARD_JOINT');assert torch.isfinite(total)
            opt.zero_grad();total.backward();opt.step();train_loss.append([float(total.detach()),float(anatomy.detach()),float(ray.detach())])
        model.eval();dev_sum=0.;dev_n=0
        with torch.no_grad():
            for batch in validation:
                batch={k:v.cuda() for k,v in batch.items()}
                pred=model(batch['observed'],batch['query'],batch['references'],batch['reference_present'],batch['query_rays'],hard=args.model!='SOFT_ANATOMY')
                _,anatomy,_=loss(pred,batch,args.model=='HARD_JOINT')
                count=len(batch['query']);dev_sum+=float(anatomy)*count;dev_n+=count
        score=dev_sum/dev_n
        if score<best:best=score;torch.save(model.state_dict(),output/'best.pt')
        record=dict(epoch=epoch,train_loss=np.mean(train_loss,axis=0).tolist(),dev_anatomy_loss=score)
        trace.append(record);(output/'trace.json').write_text(json.dumps(trace,indent=2)+'\n');print(json.dumps(record),flush=True)
    result=dict(status='SOURCE_TRAINING_COMPLETE_NO_TEST_READ',train_images=len(train),development_images=len(dev),
                model=args.model,seed=args.seed,epochs=60,seconds=time.time()-started,
                source_manifest_sha256=hashlib.sha256((args.source/'CASE_MANIFEST.json').read_bytes()).hexdigest(),
                role_freeze_sha256=hashlib.sha256((SERVER/'SOURCE_ROLE_FREEZE.json').read_bytes()).hexdigest(),
                checkpoint_sha256=hashlib.sha256((output/'best.pt').read_bytes()).hexdigest(),
                clinical_validated=False)
    (output/'TRAINING_RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
