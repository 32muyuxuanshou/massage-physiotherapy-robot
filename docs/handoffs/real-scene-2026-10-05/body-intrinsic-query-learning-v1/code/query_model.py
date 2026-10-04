"""Concrete body-coordinate / intrinsic-geometry template query model."""
import sys
from pathlib import Path
import torch
from torch import nn
BASE=Path('/raid5/xuhd/datasets/registered_human_correspondence_20261005')
sys.path[:0]=[str(BASE/'author_deps'),str(BASE/'author_diffusion_net/src'),str(BASE/'author_diffusion_net/experiments/functional_correspondence')]
from fmaps_model import FunctionalMapCorrespondenceWithDiffusionNetFeatures


class BodyIntrinsicQuery(nn.Module):
    def __init__(self,mode):
        super().__init__();self.mode=mode
        if mode!='BODY_QUERY':
            author=FunctionalMapCorrespondenceWithDiffusionNetFeatures(input_features='hks')
            author.load_state_dict(torch.load(BASE/'author_diffusion_net/experiments/functional_correspondence/pretrained_models/faust_hks.pth',weights_only=True))
            self.geometry=author.feature_extractor
        if mode!='INTRINSIC_QUERY':
            self.body=nn.Sequential(nn.Linear(6,64),nn.ReLU(),nn.Linear(64,64),nn.ReLU())
            self.context=nn.Sequential(nn.Linear(128,64),nn.ReLU())
        width={'BODY_QUERY':64,'INTRINSIC_QUERY':128,'DUAL_QUERY':192}[mode]
        self.project=nn.Sequential(nn.Linear(width,128),nn.ReLU(),nn.Linear(128,64))
        self.score=nn.Sequential(nn.Linear(131,64),nn.ReLU(),nn.Linear(64,1))

    def descriptors(self,shape,body):
        streams=[]
        if self.mode!='BODY_QUERY':
            streams.append(self.geometry(shape[9],shape[3],L=shape[4],evals=shape[5],evecs=shape[6],gradX=shape[7],gradY=shape[8],faces=shape[1]))
        if self.mode!='INTRINSIC_QUERY':
            h=self.body(body);streams.append(self.context(torch.cat([h,h.max(0).values[None].expand(len(h),-1)],-1)))
        return self.project(torch.cat(streams,-1))

    def match(self,source_desc,target_desc,source_body,target_body,query_idx):
        q=source_desc[query_idx];n=len(target_desc);k=len(q)
        dot=nn.functional.normalize(q,dim=-1)@nn.functional.normalize(target_desc,dim=-1).T
        delta=source_body[query_idx,None,:3]-target_body[None,:,:3]
        if self.mode=='INTRINSIC_QUERY':delta=torch.zeros_like(delta)
        pair=torch.cat([q[:,None,:].expand(-1,n,-1),target_desc[None,:,:].expand(k,-1,-1),delta],-1)
        return dot*20+self.score(pair).squeeze(-1)
