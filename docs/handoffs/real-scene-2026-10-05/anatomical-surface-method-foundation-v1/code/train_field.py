"""Shared training path for larger CT-source anatomy/geometry comparisons."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import Dataset, DataLoader

from acquire_full_v3 import ROOT
from joint_surface_field import JointSurfaceField


class GlobalField(JointSurfaceField):
    """Same observed encoder; query receives global, rather than KNN, conditioning.

    Registered parameters are equal but the query-KNN modules are unused in this
    baseline. Report active-gradient counts; do not claim exact effective capacity.
    """
    def forward(self, observed, query, references, reference_present):
        feature = self.stem(observed)
        for block in self.encoder:
            feature = block(observed, feature)
        local = self.stem(query)
        global_code = feature.max(dim=1).values[:, None].expand(-1, query.shape[1], -1)
        types = torch.arange(2, device=query.device)
        tokens = self.reference_xyz(references) + self.reference_type(types)[None]
        null = self.reference_null[None, None].expand(query.shape[0], 1, -1)
        tokens = torch.cat([tokens, null], dim=1)
        padding = torch.cat([~reference_present, torch.zeros(query.shape[0], 1, dtype=torch.bool, device=query.device)], dim=1)
        ref = self.reference_attn(local, tokens, tokens, key_padding_mask=padding)[0]
        fused = self.fusion(torch.cat([local, global_code, ref, query], dim=-1))
        return dict(surface_delta=self.surface_head(fused), anatomical_coordinates=self.coordinate_head(fused))


class FieldDataset(Dataset):
    def __init__(self, rows, seed, augment):
        self.rows = rows; self.seed = seed; self.augment = augment; self.epoch = 0

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        rng = np.random.default_rng(self.seed + index + self.epoch*100000)
        with np.load(self.rows[index]['pack']) as data:
            points=data['points_ras_mm'].copy(); coordinate=data['anatomical_coordinates'].copy()
            valid=data['anatomy_valid'].copy(); refs=data['references_ras_mm'].copy(); present=data['reference_present'].copy()
        available = np.arange(len(points))
        if self.augment and rng.random() < .4:
            fraction=rng.uniform(.6,.9); quantile_start=rng.uniform(0,1-fraction)
            bottom,top=np.quantile(points[:,2],[quantile_start,quantile_start+fraction])
            available=available[(points[:,2]>=bottom)&(points[:,2]<=top)]
            present &= (refs[:,2]>=bottom)&(refs[:,2]<=top)
        observed_index = rng.choice(available,1024,replace=False)
        remaining=np.setdiff1d(np.arange(len(points)),observed_index)
        supervised=remaining[valid[remaining]]
        supervised_query=rng.choice(supervised,min(128,len(supervised)),replace=False)
        extra=rng.choice(np.setdiff1d(remaining,supervised_query),256-len(supervised_query),replace=False)
        query_index=np.concatenate([supervised_query,extra]);rng.shuffle(query_index)
        origin=np.median(points[observed_index],axis=0)
        observed=(points[observed_index]-origin)/500.
        clean_query=(points[query_index]-origin)/500.
        # Geometry noise is explicitly simulated; no claim of native sensor noise.
        observed += rng.normal(0,.004,observed.shape)
        query=clean_query+rng.normal(0,.02,clean_query.shape)
        references=(refs-origin)/500.
        if self.augment and rng.random()<.5:
            present[:]=False
        return dict(observed=observed.astype(np.float32),query=query.astype(np.float32),
                    surface_delta=(clean_query-query).astype(np.float32),
                    anatomical_coordinates=coordinate[query_index].astype(np.float32),
                    anatomy_valid=valid[query_index],references=references.astype(np.float32),reference_present=present)


def compute_loss(pred,batch,joint):
    anatomy=F.smooth_l1_loss(pred['anatomical_coordinates'][batch['anatomy_valid']],batch['anatomical_coordinates'][batch['anatomy_valid']],beta=.05)
    surface=F.smooth_l1_loss(pred['surface_delta'],batch['surface_delta'],beta=.02)
    total=anatomy + .25*surface if joint else anatomy
    return total,anatomy,surface


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',choices=['GLOBAL_ANATOMY','LOCAL_ANATOMY','LOCAL_JOINT'],default='LOCAL_JOINT')
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--epochs',type=int,default=60)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args();torch.manual_seed(args.seed);torch.set_num_threads(4)
    source=ROOT/('v2_train_structure_check' if args.check_only else 'v3_dataset')
    summary=json.loads((source/'DATA_SUMMARY.json').read_text())
    rows=json.loads((source/'CASE_MANIFEST.json').read_text())
    if not args.check_only:
        expected=sum(r['age_years'] is not None and r['age_years']>=18 for r in json.loads((ROOT/'SOURCE_ROLE_FREEZE.json').read_text())['rows'])
        assert summary['cases']==len(rows)==expected, 'SOURCE_PREPARATION_NOT_COMPLETE'
    train=[r for r in rows if r['eligible'] and r['role'] in (['TRAIN_STRUCTURE_CHECK'] if args.check_only else ['TRAIN'])]
    dev=[r for r in rows if r['eligible'] and r['role']=='DEVELOPMENT']
    if not args.check_only:
        assert len(train)>=200 and len(dev)>=20, 'INSUFFICIENT_QUALIFIED_LARGE_COHORT'
    dataset=FieldDataset(train,args.seed,True)
    loader=DataLoader(dataset,batch_size=min(8,len(dataset)),shuffle=True,num_workers=0,
                      generator=torch.Generator().manual_seed(args.seed))
    dev_loader=DataLoader(FieldDataset(dev,args.seed+9000000,False),batch_size=8,num_workers=0) if dev else None
    model=(GlobalField() if args.model=='GLOBAL_ANATOMY' else JointSurfaceField()).cuda()
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    output=ROOT/('model_path_checks' if args.check_only else 'source_training')/(args.model+'_seed'+str(args.seed))
    output.mkdir(parents=True,exist_ok=True); start=time.time(); best=float('inf'); trace=[]
    active_parameters=None
    for epoch in range(1 if args.check_only else args.epochs):
        dataset.epoch=epoch;model.train();losses=[]
        for batch in loader:
            batch={k:v.cuda() for k,v in batch.items()}
            pred=model(batch['observed'],batch['query'],batch['references'],batch['reference_present'])
            total,anatomy,surface=compute_loss(pred,batch,args.model=='LOCAL_JOINT')
            assert torch.isfinite(total)
            optimizer.zero_grad();total.backward()
            if active_parameters is None:
                active_parameters=sum(p.numel() for p in model.parameters() if p.grad is not None)
            optimizer.step();losses.append([float(total.detach()),float(anatomy.detach()),float(surface.detach())])
        dev_loss=None
        if dev_loader is not None:
            model.eval(); values=[]
            with torch.no_grad():
                for batch in dev_loader:
                    batch={k:v.cuda() for k,v in batch.items()}
                    pred=model(batch['observed'],batch['query'],batch['references'],batch['reference_present'])
                    _,anatomy,_=compute_loss(pred,batch,args.model=='LOCAL_JOINT')
                    unprompted=model(batch['observed'],batch['query'],batch['references'],torch.zeros_like(batch['reference_present']))
                    _,unprompted_anatomy,_=compute_loss(unprompted,batch,args.model=='LOCAL_JOINT')
                    values.append(.5*(float(anatomy)+float(unprompted_anatomy)))
            dev_loss=float(np.mean(values))
            if dev_loss<best:
                best=dev_loss;torch.save(model.state_dict(),output/'best.pt')
        record=dict(epoch=epoch,train_total=float(np.mean(losses,axis=0)[0]),train_anatomy=float(np.mean(losses,axis=0)[1]),train_surface=float(np.mean(losses,axis=0)[2]),development_anatomy=dev_loss)
        trace.append(record);(output/'trace.json').write_text(json.dumps(trace,indent=2)+'\n')
        print(args.model,args.seed,json.dumps(record),flush=True)
    result=dict(status='NORMAL_DATA_MODEL_PATH_PASS' if args.check_only else 'SOURCE_TRAINING_COMPLETE_TEST_NOT_RUN',
                model=args.model,seed=args.seed,epochs=len(trace),train_images=len(train),development_images=len(dev),
                test_images_used=0,parameters_registered=sum(p.numel() for p in model.parameters()),
                parameters_receiving_gradient=active_parameters,seconds=time.time()-start,
                source_manifest_sha256=hashlib.sha256((source/'CASE_MANIFEST.json').read_bytes()).hexdigest(),
                clinical_precision_validated=False)
    (output/'TRAINING_RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
