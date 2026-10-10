"""Analytic perspective-depth check, including a triangle larger than the image."""
import json
import numpy as np
from raster import render_z, exact_ray_qa


def main():
    K=np.array([[100.,0,31.5],[0,100.,31.5],[0,0,1.]])
    v=np.array([[-2.,-2.,2.], [2.,-2.,3.], [0.,2.,4.]])
    faces=np.array([[0,1,2]],np.int32)
    depth,ids=render_z(v,faces,K,64,64)
    report=exact_ray_qa(v,faces,K,depth,ids)
    assert (depth>0).sum()>3000, 'Large triangle was missed'
    assert report['max_z_error_mm']<.001
    # An exactly planar, nearer triangle must occlude the original.
    near=np.array([[-2.,-2.,1.],[2.,-2.,1.],[0.,2.,1.]])
    d,_=render_z(np.concatenate([v,near]),np.array([[0,1,2],[3,4,5]],np.int32),K,64,64)
    assert np.max(np.abs(d-1))<1e-7
    print(json.dumps(dict(status='PASS',large_triangle_hits=int((depth>0).sum()),slanted_triangle=report,occlusion='PASS')))


if __name__=='__main__':
    main()
