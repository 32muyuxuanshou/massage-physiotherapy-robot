"""Reopen source indices and fixed Mesh caches; no extraction or fitting."""
import argparse
from pathlib import Path
import numpy as np
from run_interface import BASE,read,write,sha


def main(root):
    curves=read(root/'CURVE_MANIFEST.json');bindings=read(root/'BINDING_MANIFEST.json');count=0;largest=0.
    assert len(curves)==180
    for r in curves:
        if r['status']!='COMPLETE':continue
        path=Path(r['path']);assert sha(path)==r['sha256'];cache=np.load(path)
        source=np.load(BASE/'inputs'/r['subject']/'input.npz')
        split=np.load(BASE/'inputs'/r['subject']/f"split_{r['seed']}.npz")
        idx=cache['extraction_point_idx'];assert len(np.intersect1d(idx,split['heldout_idx']))==0
        assert np.isin(idx,split['train_idx']).all();assert source['posterior_point_mask'][idx].all()
        np.testing.assert_array_equal(cache['curve_m'],source['points_m'][cache['source_global_point_idx']])
        count+=1
    for r in bindings:
        assert sha(r['path'])==r['sha256'];bound=np.load(r['path']);meshpath=str(bound['mesh_path'])
        assert sha(meshpath)==r['mesh_sha256'];mesh=np.load(meshpath)
        tri=mesh['vertices_m'][mesh['faces'][bound['face_id']]];bary=bound['barycentric']
        xyz=np.sum(tri*bary[:,:,None],axis=1)
        error=float(np.linalg.norm(xyz-bound['xyz_m'],axis=1).max());largest=max(largest,error)
        assert error<1e-10;assert (bary>=-1e-12).all();np.testing.assert_allclose(bary.sum(axis=1),1,atol=1e-12)
        normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normal/=np.linalg.norm(normal,axis=1)[:,None]
        np.testing.assert_allclose(normal,bound['normals'],atol=1e-12)
        distance=np.linalg.norm(xyz-bound['query_m'],axis=1)
        np.testing.assert_allclose(distance,bound['projection_distance_m'],atol=1e-12)
        curve=next(x for x in curves if x['subject']==r['subject'] and x['seed']==r['seed'] and x['method']==r['curve_method'])
        z=np.load(curve['path']);q=np.column_stack([np.interp(bound['common_y_m'],z['query_y_m'],z['curve_m'][:,j]) for j in range(3)])
        np.testing.assert_allclose(q,bound['query_m'],rtol=0,atol=1e-12)
    for r in read(root/'SOURCE_FREEZE.json'):assert sha(r['path'])==r['sha256']
    result=dict(status='PASS',curve_records=180,successful_curves_reopened=count,binding_packages_reopened=len(bindings),
        engineering_points=len(bindings)*9,bary_reconstruction_max_m=largest,normal_recomputed=True,
        actual_source_point_identity=True,heldout_extraction_intersection=0,source_freeze_unchanged=True)
    write(root/'CACHE_VERIFICATION.json',result);print(result)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
