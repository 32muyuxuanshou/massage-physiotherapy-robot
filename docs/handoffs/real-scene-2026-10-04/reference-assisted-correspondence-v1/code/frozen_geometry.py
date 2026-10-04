"""Exact virtual cameras and first-layer raster samples with known face/bary."""
import sys
import numpy as np
from common import BASE
sys.path.insert(0,str(BASE/'delivery/code'))
from data_v2 import project

K=np.array([[900.,0,320],[0,900,480],[0,0,1]])
H,W=960,640

def camera(center):
    C=np.asarray(center,float);f=np.array([0.,0,2.4])-C;f/=np.linalg.norm(f)
    r=np.cross([0.,1,0],f);r/=np.linalg.norm(r);d=np.cross(f,r)
    return np.stack([r,d,f]),C

def local(V,R,C):return (V-C)@R.T
def world(V,R,C):return V@R+C

def raster_samples(V,F,K=K,height=H,width=W):
    tri=V[F];assert (tri[:,:,2]>0).all()
    uv=project(V,K)[F];depth=np.full((height,width),np.inf)
    ids=np.full((height,width),-1,np.int32);bary=np.zeros((height,width,3),np.float64)
    for i,(t,z) in enumerate(zip(uv,tri[:,:,2])):
        x0=max(0,int(np.ceil(t[:,0].min())));x1=min(width-1,int(np.floor(t[:,0].max())))
        y0=max(0,int(np.ceil(t[:,1].min())));y1=min(height-1,int(np.floor(t[:,1].max())))
        if x1<x0 or y1<y0:continue
        a,b,c=t;e1=b-a;e2=c-a;den=e1[0]*e2[1]-e1[1]*e2[0]
        if abs(den)<1e-12:continue
        xx,yy=np.meshgrid(np.arange(x0,x1+1),np.arange(y0,y1+1));dx=xx-a[0];dy=yy-a[1]
        w1=(dx*e2[1]-e2[0]*dy)/den;w2=(e1[0]*dy-dx*e1[1])/den
        inside=(w1>=-1e-9)&(w2>=-1e-9)&(w1+w2<=1+1e-9)
        weights=np.stack([1-w1-w2,w1,w2],axis=-1)/z
        inv=weights.sum(-1);candidate=np.full_like(inv,np.inf);candidate[inside]=1/inv[inside]
        view=depth[y0:y1+1,x0:x1+1];replace=inside&(candidate<view)
        view[replace]=candidate[replace]
        ids[y0:y1+1,x0:x1+1][replace]=i
        bary[y0:y1+1,x0:x1+1][replace]=weights[replace]/inv[replace,None]
    flat=np.flatnonzero(ids.ravel()>=0);ys,xs=np.unravel_index(flat,depth.shape)
    face=ids[ys,xs];b=bary[ys,xs];pts=np.sum(V[F[face]]*b[:,:,None],axis=1)
    assert np.max(np.abs(project(pts,K)-np.c_[xs,ys]))<1e-6
    depth[~np.isfinite(depth)]=0
    return dict(points_m=pts,face_id=face,barycentric=b,pixel_flat_index=flat,depth_m=depth,face_image=ids)

def probe(V,F,records):
    tri=V[F[[r['face_id'] for r in records]]];b=np.asarray([r['barycentric'] for r in records])
    p=(tri*b[:,:,None]).sum(1);n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.linalg.norm(n,axis=1,keepdims=True)
    return p,n
