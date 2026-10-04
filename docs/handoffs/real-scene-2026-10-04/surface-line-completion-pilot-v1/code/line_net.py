import torch
from torch import nn
from torch.nn import functional as F


def block(cin,cout):
    return nn.Sequential(nn.Conv2d(cin,cout,3,padding=1),nn.GroupNorm(4,cout),nn.SiLU(),
                         nn.Conv2d(cout,cout,3,padding=1),nn.GroupNorm(4,cout),nn.SiLU())


class LineNet(nn.Module):
    def __init__(self):
        super().__init__();self.e1=block(4,16);self.e2=block(16,32);self.e3=block(32,64)
        self.d2=block(96,32);self.d1=block(48,16);self.output=nn.Conv2d(16,1,1)

    def forward(self,x):
        e1=self.e1(x);e2=self.e2(F.avg_pool2d(e1,2));e3=self.e3(F.avg_pool2d(e2,2))
        d2=self.d2(torch.cat([F.interpolate(e3,size=e2.shape[-2:],mode='bilinear',align_corners=False),e2],1))
        d1=self.d1(torch.cat([F.interpolate(d2,size=e1.shape[-2:],mode='bilinear',align_corners=False),e1],1))
        return self.output(d1)[:,0]
