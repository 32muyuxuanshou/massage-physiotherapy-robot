"""Check actual query retrieval caches against their scan face/vertex and same cases."""
import time
from pathlib import Path
import numpy as np
from experiment import ROOT,read,write,sha
from inspect_data import load_off


def main():
    start=time.monotonic();out=ROOT/'query_stage_v1';result=read(out/'RESULTS.json')
    cases={(r['name'],r['condition'],r['seed']):r for r in read(ROOT/'CASE_MANIFEST.json') if r['role']=='test'}
    faces={r['name']:load_off(Path(r['mesh_path']))[1] for r in read(ROOT/'DATA_INVENTORY.json')['meshes'] if r['dataset']=='faust'}
    differences=[];points=0
    for r in result['raw_evaluation']:
        assert sha(Path(r['prediction_path']))==r['prediction_sha256']
        case=cases[(r['name'],r['condition'],r['input_seed'])]
        with np.load(case['path']) as z:vertex=z['source_vertex_idx']
        with np.load(r['prediction_path']) as z:
            chosen=z['retrieved_observed_idx'];assert np.array_equal(vertex[chosen],z['source_vertex_idx'])
            decoded=np.sum(faces[r['name']][z['face_id']]*z['barycentric'],axis=1).astype(int)
            assert np.array_equal(decoded,vertex[chosen]);points+=len(chosen)
            qe=z['query_canonical_errors_percent'];se=z['query_surface_errors_percent']
            for k,v in [('visible_query_median_percent',np.median(qe)),('visible_query_p95_percent',np.quantile(qe,.95)),('visible_surface_query_median_percent',np.median(se))]:
                differences.append(abs(float(v)-r[k]))
    for r in read(out/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    assert max(differences)<1e-9
    write(out/'CACHE_VERIFICATION.json',dict(status='PASS',predictions=len(result['raw_evaluation']),bound_query_points=points,
        actual_scan_face_vertex_membership=True,source_unchanged=True,maximum_difference_percent=max(differences),seconds=time.monotonic()-start,
        predicted_mhr=False,clinical_validation=False))
    print('QUERY_CACHE_PASS',points,flush=True)


if __name__=='__main__':main()
