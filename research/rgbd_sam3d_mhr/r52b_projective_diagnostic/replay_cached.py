"""Independent cache-only regeneration of a saved endpoint, no backbone or fitting to B."""
import argparse,json
import numpy as np
import torch
from common import W,load
from projection import Projector
from solvers import update,finish


def main(tag,method):
    torch.set_num_threads(1)
    a=load(W/'inputs'/(tag+'.npz'));z=load(W/'fits'/(tag+'.npz'))
    rec={k:torch.from_numpy(a[k]) for k in ['depth','valid','rays']}
    rec['batch']={k:torch.from_numpy(a[v]) for k,v in [('cam_int','K'),('ori_img_size','size'),('affine_trans','affine')]}
    p=Projector();p.bind(rec,z['body_m'],z['coarse_camera_m'])
    paths={
        'proj_vis_med1':(256,'median',True,False,1),
        **{'proj_med%d'%i:(256,'median',True,False,i) for i in [2,3,6]},
        **{'proj_plane%d'%i:(256,'plane',True,False,i) for i in [1,2,3,6]},
        'proj_gate3':(256,'plane',True,True,3),'proj_trim_huber3':(256,'huber',True,False,3),
        'proj_plain3':(256,'plane',False,False,3),'proj_huber3':(256,'huber',False,False,3),
        'proj_1024_plane3':(1024,'plane',True,False,3),'proj_4096_plane3':(4096,'plane',True,False,3)}
    count,kind,trim,gate,steps=paths[method];delta=np.zeros(3)
    for _ in range(steps):
        s=p.sample(delta,count);m=s['observed']
        step,_=update((s['measured'][m]-s['query'][m]).astype(np.float64),s['normal'][m],kind,trim,gate);delta+=step
    endpoint=json.loads((W/'fits'/(tag+'.json')).read_text())['methods'][method]
    applied,fb=finish(delta)
    difference=float(np.max(abs(applied-endpoint['applied_delta_m'])))
    np.testing.assert_allclose(delta,endpoint['raw_delta_m'],atol=2e-6,rtol=0)
    assert fb==endpoint['fallback']
    print(json.dumps(dict(status='PASS',tag=tag,method=method,max_camera_difference_m=difference,uses_backbone=False,uses_B=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--method',default='proj_plane3');a=p.parse_args();main(a.tag,a.method)
