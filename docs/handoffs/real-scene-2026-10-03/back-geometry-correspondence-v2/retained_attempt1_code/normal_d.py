"""The frozen vector D energy restricted to delta_i = u_i * fixed normal_i.

The reduced smoothness is N.T @ kron(L,I3) @ N, not L on scalar u.
This preserves the old vector displacement energy exactly on the new subspace.
No post-hoc projection, new loss weights, shape/scale or pose fitting.
"""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve
from l1_fit import vertex_normals,edges,graph_laplacian,visible_mask,ray_targets


def restricted_system(L,n,Bk,rk,lam):
    smooth=sum(sp.diags(n[:,a])@L@sp.diags(n[:,a]) for a in range(3))
    diag=np.einsum('ni,nij,nj->n',n,Bk,n)
    return sp.diags(diag)+lam*smooth,np.einsum('ni,ni->n',n,rk)


def fit_normal(V,F,cloud,K,*,lam,mu,tau,n0,irls,sigma,use_conf,use_robust):
    L=graph_laplacian(len(V),edges(F));n=vertex_normals(V,F)
    vis=visible_mask(V,n,K)
    rays=V/np.linalg.norm(V,axis=1,keepdims=True)
    agree=np.clip(-np.sum(n*rays,axis=1),0,1)
    u=np.zeros(len(V));info={'parameterization':'scalar displacement on fixed Rigid vertex normals',
        'smoothness':'N.T @ kron(L,I3) @ N; exact restricted frozen vector energy',
        'iterations':[]}
    for it in range(irls):
        delta=u[:,None]*n
        inc,cnt=ray_targets(V+delta,n,vis,cloud,K)
        has=cnt>0;tgt=np.sum(delta*n,axis=1)+inc
        w=cnt/(cnt+n0)*agree**2 if use_conf else has.astype(float)
        if use_robust and it>0:w*=(sigma*sigma/(sigma*sigma+inc*inc))**2
        w=np.where(has,w,0)
        nn=n[:,:,None]*n[:,None,:]
        Bk=w[:,None,None]*nn+tau*(np.eye(3)[None]-nn)+mu*np.eye(3)[None]
        rk=(w*tgt)[:,None]*n
        A,b=restricted_system(L,n,Bk,rk,lam)
        u=spsolve(A,b)
        info['iterations'].append(dict(iteration=it,data_vertices=int(has.sum()),
            solve_relative_residual=float(np.linalg.norm(A@u-b)/(np.linalg.norm(b)+1e-15))))
    delta=u[:,None]*n
    tangent=delta-(delta*n).sum(1)[:,None]*n
    info.update(vertex_tangent_max_mm=float(np.linalg.norm(tangent,axis=1).max()*1000),
        fixed_normal_norm_max_error=float(np.max(np.abs(np.linalg.norm(n,axis=1)-1))),
        scalar_abs_p95_mm=float(np.percentile(np.abs(u),95)*1000))
    assert np.isfinite(delta).all() and info['vertex_tangent_max_mm']<1e-5
    return V+delta,delta,u,n,info
