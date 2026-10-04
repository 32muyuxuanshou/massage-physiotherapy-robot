"""Targeted analytic checks: disjoint queries and exact constant shift."""
import numpy as np
from common import ROOT,INPUT,QUERY,write
from correspondence import binding,estimate

def main():
    assert not set(INPUT)&set(QUERY) and sorted(INPUT+QUERY)==list(range(8))
    x=np.linspace(-.3,.3,11);xx,yy=np.meshgrid(x,x);V=np.c_[xx.ravel(),yy.ravel(),np.full(xx.size,2.4)];F=[]
    for y in range(10):
        for x in range(10):
            a=y*11+x;F.extend([[a,a+11,a+1],[a+1,a+11,a+12]])
    F=np.asarray(F);records=[dict(face_id=i,barycentric=[1/3]*3) for i in [44,132,48,56,88,96,128,136]]
    target=binding(V,F,records);shifted=V+[.020,0,0];prediction=binding(shifted,F,records)
    fixed_error=np.linalg.norm(prediction-target,axis=1)*1000
    corrected,info=estimate(shifted,F,records,INPUT,target[INPUT],np.arange(len(F)))
    recovered_error=np.linalg.norm(corrected['xyz_m'][QUERY]-target[QUERY],axis=1)*1000
    unchanged,_=estimate(shifted,F,records,INPUT,prediction[INPUT],np.arange(len(F)))
    zero_error=np.max(np.linalg.norm(unchanged['xyz_m']-prediction,axis=1))
    assert np.max(abs(fixed_error-20))<1e-8 and recovered_error.max()<1e-8 and zero_error<1e-10
    write(ROOT/'ANALYTIC_CHECK.json',dict(status='PASS',input_indices=INPUT,query_indices=QUERY,
        fixed_binding_error_mm=fixed_error.tolist(),unprovided_query_error_mm=recovered_error.tolist(),
        zero_offset_identity_max_m=float(zero_error),point_projection='all faces, exact closest triangle and barycentric reconstruction',
        no_true_query_positions_in_estimator=True,medical_accuracy=False,rbf=info))
    print('ANALYTIC_CHECK_PASS',recovered_error.tolist(),flush=True)

if __name__=='__main__':main()
