"""Template-conditioned query matching; no fixed canonical XYZ labels as model input."""
import torch
from torch import nn


class PairedQuery(nn.Module):
    def __init__(self,mode):
        super().__init__();self.mode=mode
        self.encode=nn.Sequential(nn.Conv1d(6,64,1),nn.ReLU(),nn.Conv1d(64,128,1),nn.ReLU())
        extra=0
        if mode=='PAIR_LOCAL':
            self.edge=nn.Sequential(nn.Conv2d(256,64,1),nn.ReLU(),nn.Conv2d(64,64,1),nn.ReLU());extra=64
        self.point=nn.Sequential(nn.Conv1d(262+extra,128,1),nn.ReLU(),nn.Conv1d(128,64,1))
        self.score=nn.Sequential(nn.Linear(131,32),nn.ReLU(),nn.Linear(32,1))

    def descriptors(self,x):
        h=self.encode(x.transpose(1,2));joined=[x.transpose(1,2),h,h.max(2,keepdim=True)[0].expand_as(h)]
        if self.mode=='PAIR_LOCAL':
            idx=torch.cdist(x[:,:,:3],x[:,:,:3]).topk(13,largest=False).indices[:,:,1:]
            nb=h.transpose(1,2)[torch.arange(len(x),device=x.device)[:,None,None],idx].permute(0,3,1,2)
            center=h[:,:,:,None].expand_as(nb);joined.append(self.edge(torch.cat([center,nb-center],1)).max(3)[0])
        return self.point(torch.cat(joined,1)).transpose(1,2)

    def forward(self,source,target,query_idx):
        hs,ht=self.descriptors(source),self.descriptors(target)
        batch=torch.arange(len(source),device=source.device)[:,None]
        hq=hs[batch,query_idx];xq=source[batch,query_idx,:3]
        dot=torch.nn.functional.normalize(hq,dim=-1)@torch.nn.functional.normalize(ht,dim=-1).transpose(1,2)
        k,n=hq.shape[1],ht.shape[1]
        q=hq[:,:,None,:].expand(-1,-1,n,-1);p=ht[:,None,:,:].expand(-1,k,-1,-1)
        delta=xq[:,:,None,:]-target[:,None,:,:3]
        return dot*20+self.score(torch.cat([q,p,delta],dim=-1)).squeeze(-1)
