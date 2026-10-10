"""Final inventory, source transform and cached-sample verification."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    a=p.parse_args();plan=json.loads(a.plan.read_text());manifest=json.loads((a.root/'MANIFEST.json').read_text())
    expected={f"{s['asset_id']}_c{c['camera_id']:02d}_l{l['lighting_id']}" for s in plan['assets'] for c in plan['cameras'] for l in plan['lighting']}
    rows=manifest['samples'];assert {r['sample_id'] for r in rows}==expected and len(rows)==len(expected)
    actual_roles=Counter(r['role'] for r in rows);counts=Counter(r['identity'] for r in rows)
    assert set(counts)=={i['identity'] for i in plan['identities']}
    expected_counts=Counter(a['identity'] for a in plan['assets'])
    expected_counts={k:v*len(plan['cameras'])*len(plan['lighting']) for k,v in expected_counts.items()}
    assert dict(counts)==expected_counts
    assert not ({i['identity'] for i in plan['identities']}&set(plan['excluded_official_test_ids']))
    geometry=[]
    for asset in plan['assets']:
        raw=np.array([list(map(float,s.split()[1:4])) for s in (a.source/asset['obj']).open() if s.startswith('v ')])
        g=np.load(a.root/'geometry'/(asset['asset_id']+'.npz'))
        mapped=raw@g['source_to_scene_R'].T+g['source_to_scene_t_m']
        error=float(np.abs(mapped-g['vertices_scene_m']).max());assert error<1e-6
        geometry.append({'asset_id':asset['asset_id'],'raw_vertices':len(raw),'triangles':len(g['faces']),
                         'source_to_scene_max_error_m':error})
    pixel_qa=[]
    for i,row in enumerate(rows):
        f=a.root/row['file'];assert hashlib.sha256(f.read_bytes()).hexdigest()==row['sha256']
        x=np.load(f);R=x['R_world_to_camera'];assert np.allclose(R@R.T,np.eye(3),atol=1e-6)
        mask=x['mask'];valid=mask&(x['depth_m']>0)
        assert np.all(x['depth_m'][~mask]==0)
        H,W=plan['render_config']['height'],plan['render_config']['width']
        assert x['rgb'].shape==(H,W,3) and x['depth_m'].shape==(H,W)
        if 'normals_camera' in x:
            assert np.allclose(np.linalg.norm(x['normals_camera'][mask],axis=1),1,atol=1e-5)
        if 'reference_point_camera_m' in x:
            reference=x['reference_point_camera_m']
            view=row['view']
            if 'distance_m' in view:
                assert abs(reference[2]-view['distance_m'])<1e-5
                projected=x['K']@reference;projected=projected[:2]/projected[2]
                expected_pixel=np.array([(W-1)/2+view['offset_x_fraction']*W,
                                         (H-1)/2+view['offset_y_fraction']*H])
                assert np.allclose(projected,expected_pixel,atol=1e-3)
        err=(x['depth_m']-x['depth_clean_m'])[valid]*1000
        pixel_qa.append({'sample_id':row['sample_id'],'valid_depth_fraction':float(valid.sum()/mask.sum()),
                         'noise_abs_p95_mm':float(np.quantile(abs(err),.95))})
        if (i+1)%192==0:print('VERIFIED',i+1,len(rows),flush=True)
    qa=json.loads((a.root/'GEOMETRY_QA.json').read_text());assert qa['samples']==len(rows)
    report={'status':'FINAL_DATASET_QA_PASS','samples':len(rows),'roles':dict(actual_roles),'identities':dict(counts),
            'source_transform_max_error_m':max(r['source_to_scene_max_error_m'] for r in geometry),
            'all_cached_sample_sha256_verified':True,'native_mhr_parameter_supervision_available':False,
            'TEST_read':False,'source_geometry':geometry,'depth_noise':pixel_qa}
    report['camera_groups']=dict(Counter(r['view'].get('group','legacy') for r in rows))
    report['truncated_samples']=sum(r.get('image_truncated',False) for r in rows)
    (a.root/'FINAL_DATASET_QA.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_geometry','depth_noise']}))


if __name__=='__main__':
    main()
