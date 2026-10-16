"""Original R5 camera contract, re-rendered at every translation update."""
import sys
import numpy as np
import torch
from torch.nn import functional as F
from common import BASE,G,load
sys.path.insert(0,str(BASE/'r51_fine_supervision_ablation_v1/code'))
from frozen_render_losses import MeshRenderer


def nested_ids():
    ids=np.linspace(0,16383,256,dtype=np.int64);result={256:ids}
    for count in [1024,4096]:
        remaining=np.setdiff1d(np.arange(16384),ids)
        chosen=remaining[np.linspace(0,len(remaining)-1,count-len(ids),dtype=np.int64)]
        ids=np.sort(np.r_[ids,chosen]);result[count]=ids
    return result


class Projector:
    def __init__(self):
        self.faces=torch.from_numpy(np.load(G/'assets/faces.npy')).cuda().long()
        a=load(G/'assets/anchors.npz');self.fi=torch.from_numpy(a['face_index']).cuda().long()
        self.bc=torch.from_numpy(a['barycentric']).cuda().float()
        self.ids={n:torch.from_numpy(a).cuda() for n,a in nested_ids().items()}
        self.renderer=MeshRenderer(self.faces)

    def bind(self,rec,body,coarse):
        self.body=torch.from_numpy(body).cuda()[None];self.coarse=torch.from_numpy(coarse).cuda()[None]
        self.depth=rec['depth'].cuda().float();self.valid=rec['valid'].cuda().float()
        self.K=rec['batch']['cam_int'].cuda().float()
        self.size=rec['batch']['ori_img_size'].cuda().reshape(-1,2).float()
        self.affine=rec['batch']['affine_trans'].cuda().reshape(-1,2,3).float()
        self.render_K=self.K.clone();self.render_K[:,0,:]*=self.renderer.width/self.size[:,0,None]
        self.render_K[:,1,:]*=self.renderer.height/self.size[:,1,None]

    @torch.no_grad()
    def sample(self,delta,count):
        ids=self.ids[count];camera=self.coarse+torch.as_tensor(delta,device='cuda',dtype=torch.float32)[None]
        vertices=self.body+camera[:,None];tri=vertices[:,self.faces[self.fi[ids]]]
        q=(tri*self.bc[ids][None,:,:,None]).sum(2)
        normal=F.normalize(torch.cross(tri[:,:,1]-tri[:,:,0],tri[:,:,2]-tri[:,:,0],dim=-1),dim=-1)
        proj=torch.einsum('bij,bnj->bni',self.K,q);uv=proj[...,:2]/q[...,2:].clamp_min(.001)
        crop=torch.einsum('bij,bnj->bni',self.affine,torch.cat((uv,torch.ones_like(uv[...,:1])),2));crop[...,0]-=64
        h,w=self.depth.shape[-2:];grid=torch.stack((2*crop[...,0]/(w-1)-1,2*crop[...,1]/(h-1)-1),2)
        z=F.grid_sample(self.depth,grid[:,:,None],mode='nearest',align_corners=True)[:,0,:,0]
        valid=F.grid_sample(self.valid,grid[:,:,None],mode='nearest',align_corners=True)[:,0,:,0]>.5
        rendered,_=self.renderer(vertices,self.render_K)
        rg=torch.stack((2*(uv[...,0]+.5)/self.size[:,0,None]-1,2*(uv[...,1]+.5)/self.size[:,1,None]-1),2)
        sz=F.grid_sample(rendered[:,None],rg[:,:,None],mode='nearest',align_corners=False)[:,0,:,0]
        obs=valid&(grid.abs()<=1).all(2)&(q[...,2]>.05)&(sz>0)&((sz-q[...,2]).abs()<.02)
        ray=(uv-self.K[:,None,:2,2])/torch.stack((self.K[:,0,0],self.K[:,1,1]),1)[:,None]
        measured=torch.cat((ray*z[...,None],z[...,None]),2)
        return {k:v[0].cpu().numpy() for k,v in dict(query=q,normal=normal,measured=measured,observed=obs,grid=grid).items()}
