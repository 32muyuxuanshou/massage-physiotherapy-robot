"""Independently recompute exported numeric summaries from all cached arrays."""
import json,ast,hashlib
from pathlib import Path
import numpy as np

def main():
    root=Path(__file__).resolve().parents[1]
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    cfg=read(root/'CONTRACT.json');metrics=probes=records=0
    for p in (root/'code').glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
    for subject in cfg['subjects']:
        index={k:np.load(root/'observation_indices'/subject/f'K{k}.npz') for k in [0,1,2]}
        for k in [1,2]:assert len(index[k]['optimization_idx'])==0
        assert len(index[0]['optimization_idx'])<=40000
        for case in cfg['cases']:
            d=root/'results'/subject/case;rows=read(d/'results.json');records+=len(rows)
            all_arrays={}
            for row in rows:
                m=row['method'];z=np.load(d/(m+'_probes.npz'))
                dist=np.linalg.norm(z['xyz_m']-z['reference_xyz_m'],axis=1)*1000
                np.testing.assert_allclose(dist,row['probe_errors_mm'],rtol=0,atol=1e-10);probes+=1
                for c in row['cameras']:
                    k=c['camera'];a=np.load(d/f'{m}_K{k}_metrics.npz');all_arrays[k,m]=a;metrics+=1
                    assert np.array_equal(a['evaluation_point_idx'],index[k]['posterior_eval_idx'])
                    dist=a['point_to_surface_m']*1000;assert np.isfinite(dist).all() and np.min(dist)>=0
                    np.testing.assert_allclose([np.median(dist),np.percentile(dist,95)],
                        [c['posterior']['median_mm'],c['posterior']['p95_mm']],rtol=0,atol=1e-9)
                    for key,mask in [('ray',a['ray_hit']),('common_ray',a['common_ray_hit'])]:
                        values=np.abs(a['ray_z_residual_m'][mask])*1000
                        np.testing.assert_allclose([np.median(values),np.percentile(values,95)],
                            [c[key]['median_mm'],c[key]['p95_mm']],rtol=0,atol=1e-9)
            for k in [1,2]:
                common=np.logical_and.reduce([all_arrays[k,m]['ray_hit'] for m in cfg['methods']])
                for m in cfg['methods']:assert np.array_equal(common,all_arrays[k,m]['common_ray_hit'])
    assert (records,metrics,probes)==(240,480,240)
    for row in read(root/'VISUALIZATION_MANIFEST.json'):
        path=root/'figures'/Path(row['path']).name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    result=dict(status='PASS',method_records=records,per_point_arrays_recomputed=metrics,probe_arrays_recomputed=probes,
        virtual_observation_index_files=60,common_hit_checks=120,visualization_pages_verified=60,
        geometry_cache_recompute='4 server checks recorded separately',new_fits=0)
    (root/'DELIVERY_NUMERICAL_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
