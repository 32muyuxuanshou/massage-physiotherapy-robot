"""Two focused checks: exact reduced energy and an observed planar surface."""
import sys
import numpy as np,scipy.sparse as sp
from common import BASE,write,ROOT
sys.path.insert(0,str(BASE/'delivery/code'))
from normal_d import restricted_system,fit_normal
from l1_fit import graph_laplacian,edges

def main():
    rng=np.random.default_rng(17);n=rng.normal(size=(7,3));n/=np.linalg.norm(n,axis=1)[:,None]
    L=graph_laplacian(7,np.array([[i,i+1] for i in range(6)]))
    X=rng.normal(size=(7,3,3));Bk=np.einsum('nji,njk->nik',X,X)+np.eye(3)[None]*.1
    rk=rng.normal(size=(7,3));A,b=restricted_system(L,n,Bk,rk,.15)
    N=sp.coo_matrix((n.ravel(),(np.arange(21),np.repeat(np.arange(7),3))),shape=(21,7)).tocsr()
    full=sp.block_diag(list(Bk))+.15*sp.kron(L,sp.eye(3))
    matrix_error=float(np.max(np.abs((A-N.T@full@N).toarray())))
    rhs_error=float(np.max(np.abs(b-N.T@rk.ravel())))
    assert matrix_error<1e-12 and rhs_error<1e-12
    x,y=np.meshgrid(np.linspace(-.08,.08,11),np.linspace(-.08,.08,11))
    V=np.c_[x.ravel(),y.ravel(),np.ones(x.size)]
    F=[]
    for j in range(10):
        for i in range(10):
            a=j*11+i;F.extend([[a,a+12,a+1],[a,a+11,a+12]])
    F=np.array(F);cloud=V+np.array([0,0,.01]);K=np.array([[100,0,50],[0,100,50],[0,0,1]])
    # Dense sensor samples provide >=3 points within the frozen pixel neighbourhood.
    cloud=np.concatenate([cloud+np.array([dx,dy,0]) for dx in [-.002,0,.002] for dy in [-.002,0,.002]])
    final,d,u,n,info=fit_normal(V,F,cloud,K,lam=.15,mu=.0001,tau=.05,n0=6,irls=4,sigma=.012,use_conf=True,use_robust=True)
    assert np.allclose(final[:,:2],V[:,:2],atol=1e-12)
    assert np.median(final[:,2]-V[:,2])>.005
    write(ROOT/'C_NORMAL_SOLVER_CHECK.json',dict(status='PASS',restricted_matrix_error=matrix_error,
        restricted_rhs_error=rhs_error,planar_z_shift_mm=float(np.median(final[:,2]-V[:,2])*1000),info=info))
    print('NORMAL_SOLVER_PASS',matrix_error,rhs_error,flush=True)

if __name__=='__main__':main()
