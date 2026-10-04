"""Concrete surface coordinate decoders: global, template-conditioned, local conditioned."""
import torch
from torch import nn


class CoordinateField(nn.Module):
    def __init__(self,mode):
        super().__init__();self.mode=mode
        channels=6 if mode=='POINT_GLOBAL' else 12
        self.encode=nn.Sequential(nn.Conv1d(channels,64,1),nn.ReLU(),nn.Conv1d(64,128,1),nn.ReLU())
        extra=0
        if mode=='PRIOR_LOCAL':
            self.edge=nn.Sequential(nn.Conv2d(256,64,1),nn.ReLU(),nn.Conv2d(64,64,1),nn.ReLU());extra=64
        self.decode=nn.Sequential(nn.Conv1d(256+channels+extra,128,1),nn.ReLU(),nn.Conv1d(128,64,1),nn.ReLU(),nn.Conv1d(64,3,1))

    def forward(self,x):
        features=x[:,:,:6] if self.mode=='POINT_GLOBAL' else x
        encoded=self.encode(features.transpose(1,2));global_feature=encoded.max(2,keepdim=True)[0].expand_as(encoded)
        joined=[features.transpose(1,2),encoded,global_feature]
        if self.mode=='PRIOR_LOCAL':
            indices=torch.cdist(x[:,:,:3],x[:,:,:3]).topk(13,largest=False).indices[:,:,1:]
            batch=torch.arange(len(x),device=x.device)[:,None,None]
            local=encoded.transpose(1,2)[batch,indices].permute(0,3,1,2)
            center=encoded[:,:,:,None].expand_as(local)
            joined.append(self.edge(torch.cat([center,local-center],1)).max(3)[0])
        q=self.decode(torch.cat(joined,1)).transpose(1,2)
        return q if self.mode=='POINT_GLOBAL' else q+x[:,:,6:9]
