"""NumPy-only replay of the delivered predicted MHR faces and target caches."""
import json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    rows=read(ROOT/'TARGET_MANIFEST.json');reviews={(r['subject'],r['split_seed'],r['mesh_method']):r for r in read(ROOT/'MESH_REVIEW_MANIFEST.json')}
    loaded={};checks=0
    for r in rows:
        p=ROOT/'targets'/Path(r['path']).name;assert sha(p)==r['sha256']
        key=(r['subject'],r['split_seed'],r['mesh_method']);mr=reviews[key];mp=ROOT/'mesh_reviews'/Path(mr['path']).name
        if key not in loaded:
            assert sha(mp)==mr['sha256'];loaded[key]=dict(np.load(mp))
        m=loaded[key]
        with np.load(p) as z:
            idx=np.searchsorted(m['global_face_id'],z['face_id']);assert np.array_equal(m['global_face_id'][idx],z['face_id'])
            tri=m['triangles_m'][idx];xyz=(tri*z['barycentric'][:,:,None]).sum(1)
            normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normal/=np.linalg.norm(normal,axis=1,keepdims=True)
            assert np.allclose(xyz,z['xyz_m'],atol=1e-10);assert np.allclose(normal,z['normals'],atol=1e-10)
            assert np.allclose(np.linalg.norm(z['query_m']-xyz,axis=1),z['projection_distance_m'],atol=1e-10)
            assert abs(float(np.median(np.linalg.norm(xyz-z['topology_xyz_m'],axis=1))*1000)-r['offset_from_topology_median_mm'])<1e-8
            checks+=5
    out=dict(status='PASS',delivered_targets=len(rows),delivered_mesh_face_caches=len(loaded),checks=checks,new_fit=0,medical_accuracy=False)
    (ROOT/'DELIVERY_REPLAY.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out))


if __name__=='__main__':main()
