"""Train-only XYZ curve extraction and binding to fixed existing MHR meshes."""
import argparse, csv, json, hashlib, sys, time
from pathlib import Path
import numpy as np

BASE=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2')
EXTRACTOR=Path('/raid5/xuhd/datasets/back_reference_extraction_v1_20261004')
PROJECTION=Path('/raid5/xuhd/datasets/back_reference_assisted_v1_20261004/code')
MASK=Path('/raid5/xuhd/datasets/prone_back_point_validation_20261003/assets/candidate_posterior_mask.json')
COHORT=Path('/raid5/xuhd/datasets/back_reference_assisted_v1_20261004/CONTRACT.json')
sys.path.insert(0,str(EXTRACTOR/'code'));from extract_geometry import extract
sys.path.insert(0,str(PROJECTION));from correspondence import surface_project

MESHES={'Official':'Official','Rigid':'Official_Rigid','RigidD':'Official_Rigid_D'}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,value):p.write_bytes((json.dumps(value,indent=2,allow_nan=False)+'\n').encode('utf-8'))
def csv_write(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main(root):
    start=time.time();cohort=read(COHORT);subjects=cohort['subjects'];config=read(EXTRACTOR/'CONFIG.json')
    mask=np.asarray(read(MASK)['face_ids'],int)
    files=[COHORT,MASK,EXTRACTOR/'CONFIG.json',EXTRACTOR/'code/extract_geometry.py',PROJECTION/'correspondence.py',root/'PROTOCOL.md',*(root/'code').glob('*.py')]
    for s in subjects:
        files.append(BASE/'inputs'/s/'input.npz')
        for seed in range(3):
            files.append(BASE/'inputs'/s/f'split_{seed}.npz')
            for name in MESHES.values():files.append(BASE/'meshes'/s/f'seed_{seed}'/(name+'.npz'))
    freeze=[dict(path=str(p),sha256=sha(p)) for p in files];write(root/'SOURCE_FREEZE.json',freeze)
    write(root/'CONFIG.json',dict(cohort=subjects,dev=cohort['dev'],seeds=[0,1,2],extraction=config,
        extractor_sha256=sha(EXTRACTOR/'code/extract_geometry.py'),posterior_mask_sha256=sha(MASK),
        posterior_faces=len(mask),meshes=MESHES,probe_fractions=np.arange(.1,1,.1).tolist(),clinical_accuracy=False))
    for d in ['curves','grids','bindings']: (root/d).mkdir(exist_ok=True)
    curve_rows=[];bindings=[];query_manifest=[]
    for s in subjects:
        z=np.load(BASE/'inputs'/s/'input.npz');points=z['points_m'];posterior=z['posterior_point_mask']
        available={}
        for seed in range(3):
            split=np.load(BASE/'inputs'/s/f'split_{seed}.npz');train=split['train_idx'];held=split['heldout_idx'];used=train[posterior[train]]
            assert len(np.intersect1d(used,held))==0
            pred,grid=extract(points[used],config)
            np.savez_compressed(root/'grids'/f'{s}_{seed}.npz',**grid)
            for method in config['methods']:
                result=pred[method]
                row=dict(subject=s,role='dev' if s in cohort['dev'] else 'consumed_test_role',seed=seed,method=method,
                    status=result['status'],extraction_points=len(used),heldout_intersection=0,
                    input_sha256=sha(BASE/'inputs'/s/'input.npz'),split_sha256=sha(BASE/'inputs'/s/f'split_{seed}.npz'))
                if result['status']=='COMPLETE':
                    path=root/'curves'/f'{s}_{seed}_{method}.npz'
                    np.savez_compressed(path,**{k:v for k,v in result.items() if k!='status'},
                        extraction_point_idx=used,source_global_point_idx=used[result['source_point_indices']])
                    row.update(path=str(path),sha256=sha(path),curve_points=len(result['curve_m']),
                        snap_median_mm=float(np.median(result['xy_snap_distance_m'])*1000),
                        snap_max_mm=float(result['xy_snap_distance_m'].max()*1000),
                        supported_fraction=float(np.mean(result['xy_snap_distance_m']<=config['support_radius_m'])))
                    available[seed,method]=result
                else: row.update(path=None,sha256=None,curve_points=0,snap_median_mm=None,snap_max_mm=None,supported_fraction=0.)
                curve_rows.append(row)
        ylo=max(c['query_y_m'].min() for c in available.values());yhi=min(c['query_y_m'].max() for c in available.values())
        ys=ylo+(yhi-ylo)*np.arange(.1,1,.1)
        query_manifest.append(dict(subject=s,common_y_m=ys.tolist(),anatomical_or_acupoint_labels=False))
        for (seed,method),curve in available.items():
            query=np.column_stack([np.interp(ys,curve['query_y_m'],curve['curve_m'][:,j]) for j in range(3)])
            for mesh_method,stem in MESHES.items():
                mesh_path=BASE/'meshes'/s/f'seed_{seed}'/(stem+'.npz');mesh=np.load(mesh_path)
                used=curve_rows[next(i for i,r in enumerate(curve_rows) if r['subject']==s and r['seed']==seed and r['method']==method)]
                split=np.load(BASE/'inputs'/s/f'split_{seed}.npz')
                assert np.isin(mesh['optimization_point_idx'],split['train_idx']).all()
                bound=surface_project(query,mesh['vertices_m'],mesh['faces'],mask)
                b=bound['barycentric'];face=bound['face_id'];vertices=mesh['vertices_m'][mesh['faces'][face]]
                reconstructed=np.sum(vertices*b[:,:,None],axis=1)
                assert np.allclose(reconstructed,bound['xyz_m'],rtol=0,atol=1e-10)
                p=root/'bindings'/f'{s}_{seed}_{method}_{mesh_method}.npz'
                np.savez_compressed(p,**bound,query_m=query,common_y_m=ys,probe_fraction=np.arange(.1,1,.1),mesh_path=np.asarray(str(mesh_path)),mesh_sha256=np.asarray(sha(mesh_path)))
                bindings.append(dict(subject=s,role=used['role'],seed=seed,curve_method=method,mesh_method=mesh_method,
                    path=str(p),sha256=sha(p),mesh_sha256=sha(mesh_path),curve_sha256=used['sha256'],points=len(query),
                    projection_median_mm=float(np.median(bound['projection_distance_m'])*1000),
                    projection_p95_mm=float(np.percentile(bound['projection_distance_m'],95)*1000),
                    bary_reconstruction_max_m=float(np.linalg.norm(reconstructed-bound['xyz_m'],axis=1).max()),
                    medical_labels=False,robot_coordinates=False))
        print('SUBJECT_COMPLETE',s,[r['status'] for r in curve_rows if r['subject']==s],flush=True)
    write(root/'CURVE_MANIFEST.json',curve_rows);csv_write(root/'CURVE_RESULTS.csv',curve_rows)
    write(root/'BINDING_MANIFEST.json',bindings);csv_write(root/'BINDING_RESULTS.csv',bindings)
    write(root/'QUERY_MANIFEST.json',query_manifest)
    for row in freeze:assert sha(row['path'])==row['sha256']
    write(root/'EXECUTION_LEDGER.json',dict(status='COMPLETE',subjects=20,curve_records=len(curve_rows),
        successful_curves=sum(r['status']=='COMPLETE' for r in curve_rows),binding_packages=len(bindings),
        engineering_points=sum(r['points'] for r in bindings),sam_inferences=0,mesh_fits=0,training=0,
        source_unchanged=True,seconds=time.time()-start,heldout_reference_input_intersection=0))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
