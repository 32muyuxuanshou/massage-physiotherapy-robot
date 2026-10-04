"""Continuous canonical query decoder over a visible observed surface candidate set."""
import torch
from torch import nn


class QuerySurface(nn.Module):
    def __init__(self,mode):
        super().__init__();self.mode=mode;c=6 if mode=='Q_GLOBAL' else 12
        self.encode=nn.Sequential(nn.Conv1d(c,64,1),nn.ReLU(),nn.Conv1d(64,128,1),nn.ReLU())
        extra=0
        if mode=='Q_PRIOR_LOCAL':
            self.edge=nn.Sequential(nn.Conv2d(256,64,1),nn.ReLU(),nn.Conv2d(64,64,1),nn.ReLU());extra=64
        self.point=nn.Sequential(nn.Conv1d(256+c+extra,128,1),nn.ReLU(),nn.Conv1d(128,64,1))
        self.query=nn.Sequential(nn.Linear(3,64),nn.ReLU(),nn.Linear(64,64))
        self.pair=nn.Sequential(nn.Linear(128,32),nn.ReLU(),nn.Linear(32,1))

    def forward(self,x,q):
        features=x[:,:,:6] if self.mode=='Q_GLOBAL' else x
        h=self.encode(features.transpose(1,2));joined=[features.transpose(1,2),h,h.max(2,keepdim=True)[0].expand_as(h)]
        if self.mode=='Q_PRIOR_LOCAL':
            idx=torch.cdist(x[:,:,:3],x[:,:,:3]).topk(13,largest=False).indices[:,:,1:]
            nb=h.transpose(1,2)[torch.arange(len(x),device=x.device)[:,None,None],idx].permute(0,3,1,2)
            center=h[:,:,:,None].expand_as(nb);joined.append(self.edge(torch.cat([center,nb-center],1)).max(3)[0])
        p=self.point(torch.cat(joined,1)).transpose(1,2);queries=self.query(q)
        dot=torch.nn.functional.normalize(queries,dim=-1)@torch.nn.functional.normalize(p,dim=-1).transpose(1,2)
        n,k=x.shape[1],q.shape[1]
        pair=torch.cat([queries[:,:,None,:].expand(-1,-1,n,-1),p[:,None,:,:].expand(-1,k,-1,-1)],-1)
        return dot*20+self.pair(pair).squeeze(-1)
