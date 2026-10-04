"""Small positive-path checks before the controlled reference batch."""
import sys
import numpy as np
from common import ROOT,BASE,PREV,write
sys.path[:0]=[str(BASE/'delivery/code'),str(PREV/'code')]
from geometry import raster_samples,camera,local,world,K
from metrics_v2 import ray_depth_residual
from surface_metrics import point_to_triangle_distances
from l1_fit import fit_displacement
from normal_d import fit_normal

def main():
    V=np.array([[-.5,-.4,1.8],[.6,-.4,2.7],[0.,.6,2.1]])
    F=np.array([[0,2,1]])
    obs=raster_samples(V,F);sample=np.arange(0,len(obs['points_m']),max(1,len(obs['points_m'])//100))
    r,h=ray_depth_residual(obs['points_m'][sample],V,F)
    assert h.all() and np.max(np.abs(r))<1e-10
    triangle_error=float(np.max(np.abs(r)))
    camera_errors=[]
    for center in [[0,0,0],[.45,0,0],[-.45,0,0]]:
        R,C=camera(center);error=float(np.max(np.abs(world(local(V,R,C),R,C)-V)))
        assert error<1e-12;camera_errors.append(error)
    axis=np.linspace(-.3,.3,61);xx,yy=np.meshgrid(axis,axis)
    pv=np.c_[xx.ravel(),yy.ravel(),np.full(xx.size,2.4)]
    fs=[]
    for y in range(60):
        for x in range(60):
            a=y*61+x;fs.extend([[a,a+61,a+1],[a+1,a+61,a+62]])
    pf=np.asarray(fs);initial=pv+np.array([.020,0,0])
    ax=np.linspace(-.12,.12,61);xx,yy=np.meshgrid(ax,ax)
    cloud=np.c_[xx.ravel(),yy.ravel(),np.full(xx.size,2.4)]
    pars=dict(lam=.15,mu=.0001,tau=.05,n0=6.,irls=4,sigma=.012,use_conf=True,use_robust=True)
    vector,_,_=fit_displacement(initial,pf,cloud,K,**pars)
    normal,_,_,_,_=fit_normal(initial,pf,cloud,K,**pars)
    rows=[];face=pf[len(pf)//2];b=np.full(3,1/3);target=np.sum(pv[face]*b[:,None],axis=0)
    for method,W in [('INITIAL',initial),('D_VECTOR',vector),('D_NORMAL',normal)]:
        d=point_to_triangle_distances(cloud[::50],W,pf);r,hit=ray_depth_residual(cloud[::50],W,pf)
        error=float(np.linalg.norm(np.sum(W[face]*b[:,None],axis=0)-target)*1000)
        assert d.max()<1e-10 and hit.all() and np.max(np.abs(r))<1e-10
        assert abs(error-20)<1e-8
        rows.append(dict(method=method,surface_max_mm=float(d.max()*1000),ray_max_mm=float(np.max(np.abs(r))*1000),known_binding_error_mm=error))
    write(ROOT/'GEOMETRY_CHECK.json',dict(status='PASS',perspective_triangle_ray_max_m=triangle_error,
        virtual_camera_roundtrip_max_m=max(camera_errors),planar_binding_witness=rows,
        interpretation='in a central planar observed patch, surface/depth can be exact while a topology-bound point is displaced 20mm',
        limitations='analytical observation ambiguity, not evidence of 20mm real-patient acupoint error'))
    np.savez_compressed(ROOT/'planar_witness.npz',reference_vertices_m=pv,initial_vertices_m=initial,
        vector_vertices_m=vector,normal_vertices_m=normal,faces=pf,observed_points_m=cloud,
        probe_face=face,probe_barycentric=b,target_probe_m=target)
    print('GEOMETRY_CHECK_PASS',rows,flush=True)

if __name__=='__main__':main()
