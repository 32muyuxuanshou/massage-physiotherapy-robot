"""Actual source-point membership and barycentric reconstruction of all saved outputs."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np


def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    root=parser.parse_args().root;start=time.monotonic()
    base=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2')
    curves=read(root/'CURVE_MANIFEST.json');bindings=read(root/'BINDING_MANIFEST.json')
    raw={};splits={};meshes={};maximum=0.;normal_error=0.;point_checks=0
    for row in curves:
        assert sha(row['path'])==row['sha256']
        subject=row['subject'];key=subject,row['split_seed']
        if subject not in raw:
            with np.load(base/'inputs'/subject/'input.npz') as z:raw[subject]=(z['points_m'],z['posterior_point_mask'])
        if key not in splits:
            with np.load(base/'inputs'/subject/f"split_{row['split_seed']}.npz") as z:splits[key]=(z['train_idx'],z['heldout_idx'])
        with np.load(row['path']) as z:
            used=z['extraction_point_idx'];selected=z['source_global_point_idx']
            assert np.array_equal(used,splits[key][0][raw[subject][1][splits[key][0]]])
            assert np.intersect1d(used,splits[key][1]).size==0 and np.isin(selected,used).all()
            assert np.array_equal(z['curve_m'],raw[subject][0][selected]);point_checks+=len(selected)
    for row in bindings:
        assert sha(row['path'])==row['sha256']
        path=row['mesh_path']
        if path not in meshes:
            assert sha(path)==row['mesh_sha256']
            with np.load(path) as z:meshes[path]=(z['vertices_m'],z['faces'])
        V,F=meshes[path]
        with np.load(row['path']) as z:
            triangles=V[F[z['face_id']]];b=z['barycentric']
            rebuilt=np.sum(triangles*b[:,:,None],axis=1)
            maximum=max(maximum,float(np.linalg.norm(rebuilt-z['xyz_m'],axis=1).max()))
            n=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]);n/=np.linalg.norm(n,axis=1)[:,None]
            normal_error=max(normal_error,float(np.linalg.norm(n-z['normals'],axis=1).max()))
            assert np.allclose(b.sum(1),1) and np.all(b>=0)
    assert maximum<1e-10 and normal_error<1e-10
    for r in read(root/'SOURCE_FREEZE.json'):assert sha(r['path'])==r['sha256']
    report=dict(status='PASS',curves=len(curves),bindings=len(bindings),source_point_membership_checks=point_checks,
        actual_mesh_files=len(meshes),max_bary_reconstruction_error_m=maximum,max_normal_reconstruction_error=normal_error,
        heldout_input_intersection=0,source_unchanged=True,seconds=time.monotonic()-start,
        clinical_validation=False,analysis_script_sha256=sha(root/'code/analyze_transfer.py'),verification_script_sha256=sha(__file__))
    (root/'CACHE_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
