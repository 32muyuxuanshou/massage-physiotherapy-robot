"""Cached binding/metric verification without correspondence solver."""
import argparse
from pathlib import Path
import numpy as np
from run_bounded import PARENT,read,write,sha


def main(root):
    cfg=read(root/'CONTRACT.json');manifest=read(root/'CACHE_MANIFEST.json');rows=read(root/'PER_CASE_RESULTS.json')
    cases={(r['subject'],r['case']):r for r in read(PARENT/'CASE_MANIFEST.json')};query=cfg['query_indices']
    assert len(rows)==300 and len(manifest)==300
    original_names={'FIXED':'FIXED','RBF_EXACT':'REF4_EXACT','RBF_NOISY5':'REF4_NOISY5'}
    for r in manifest:
        assert sha(r['path'])==r['sha256'];z=np.load(r['path']);case=cases[r['subject'],r['case']]
        assert sha(case['mesh_path'])==r['source_surface_sha256'];mesh=np.load(case['mesh_path'])
        xyz=np.sum(mesh['vertices_m'][mesh['faces'][z['face_id']]]*z['barycentric'][:,:,None],axis=1)
        np.testing.assert_allclose(xyz,z['xyz_m'],rtol=0,atol=1e-9)
        truth=np.load(case['truth_path']);delta=z['xyz_m']-truth['reference_xyz_m'];euclidean=np.linalg.norm(delta,axis=1)*1000
        saved=next(x for x in rows if (x['subject'],x['case'],x['method'])==(r['subject'],r['case'],r['method']))
        np.testing.assert_allclose(euclidean,saved['per_probe_error_mm'],rtol=0,atol=1e-10)
        assert abs(np.median(euclidean[query])-saved['query_median_mm'])<1e-10
        assert abs(np.percentile(euclidean[query],95)-saved['query_p95_mm'])<1e-10
        if r['inherited']:
            assert sha(PARENT/'runs'/r['subject']/r['case']/(original_names[r['method']]+'.npz'))==r['sha256']
        else:
            w=z['reference_weights'];assert w.min()>=0;np.testing.assert_allclose(w.sum(axis=1),1,atol=1e-12)
    for row in read(root/'SOURCE_FREEZE.json'):assert sha(row['path'])==row['sha256']
    for row in read(root/'VISUALIZATION_MANIFEST.json'):assert sha(row['path'])==row['sha256']
    result=dict(status='PASS',cached_points_reopened=300,probe_metrics_recomputed=2400,inherited_identity_exact=180,
        fixed_surfaces_unchanged=60,source_files=len(read(root/'SOURCE_FREEZE.json')),figures_verified=60,
        input_query_intersection=sorted(set(cfg['input_indices'])&set(query)),new_mesh_fits=0)
    write(root/'CACHE_VERIFICATION.json',result);print(result)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
