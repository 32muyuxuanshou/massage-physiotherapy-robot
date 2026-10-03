"""Cache-only closeout: actual splits, original metric agreement and recomputation."""
import sys,itertools
import numpy as np
from common import ROOT,BASE,OLD,METHODS,read,write,sha,token
sys.path[:0]=[str(BASE/'delivery/code'),str(OLD/'code')]
from surface_metrics import point_to_triangle_distances
from metrics_v2 import ray_depth_residual
from run_cached_point_diagnostics import interpolate

OUT=ROOT/'c_pressure_normal'

def main():
    cfg=read(OUT/'EXECUTION_CONTRACT.json');atlas=read(ROOT/'a_atlas/ENGINEERING_BACK_ATLAS_V2.json')
    fit_rows=[];splits=[];old_agreement=[];recomputed=[];stability=[]
    points=read(OUT/'ENG_POINTS_1920.json')
    for subject in cfg['subjects']:
        inp=np.load(OUT/'inputs'/subject/'input.npz');cloud=inp['points_m'];K=inp['K']
        ledger=read(OUT/'ledger'/(subject+'.json'));assert ledger['status']=='COMPLETE'
        fit_rows.extend(ledger['rows'])
        for seed in cfg['seeds']:
            split=np.load(OUT/'inputs'/subject/f'split_{seed}.npz')
            assert np.intersect1d(split['train_idx'],split['heldout_idx']).size==0
            assert np.isin(split['posterior_eval_idx'],split['heldout_idx']).all()
            splits.append(dict(subject=subject,seed=seed,train_count=len(split['train_idx']),heldout_count=len(split['heldout_idx']),
                posterior_count=len(split['posterior_eval_idx']),train_heldout_intersection=0,
                input_sha256=sha(OUT/'inputs'/subject/'input.npz'),split_sha256=sha(OUT/'inputs'/subject/f'split_{seed}.npz')))
            for method in METHODS:
                path=OUT/'meshes'/subject/f'seed_{seed}'/(token(method)+'.npz')
                mesh=np.load(path);idx=mesh['optimization_point_idx']
                assert np.isin(idx,split['train_idx']).all() and np.intersect1d(idx,split['heldout_idx']).size==0
                p,n,_=interpolate(mesh['vertices_m'],mesh['faces'],atlas['records'])
                saved=[r for r in points if r['subject']==subject and r['seed']==seed and r['method']==method]
                assert np.allclose(p,[r['xyz_m'] for r in saved],atol=1e-14,rtol=0)
                metric_path=OUT/'evaluation'/subject/f'seed_{seed}'/(token(method)+'_metrics.npz')
                metric=np.load(metric_path)
                if method in METHODS[:3]:
                    orig=np.load(BASE/'run_v2/evaluation'/subject/f'seed_{seed}'/(token(method)+'_metrics.npz'))
                    for region in ['posterior','torso']:
                        assert np.array_equal(metric[region+'_point_idx'],orig[region+'_point_idx'])
                        for field in ['d3d_m','ray_signed_m','hit']:
                            assert np.array_equal(metric[region+'_'+field],orig[region+'_'+field],equal_nan=True)
                    old_agreement.append(dict(subject=subject,seed=seed,method=method,point_distances_and_individual_rays='EXACT',
                        common_hit_not_compared='method intersection intentionally changed from five to four'))
                if subject in cfg['dev'] and seed==0 and method==METHODS[-1]:
                    query=cloud[split['posterior_eval_idx']]
                    faces=np.asarray(read(BASE/'delivery/POSTERIOR_FACE_MASK.json')['face_ids'],int)
                    d=point_to_triangle_distances(query,mesh['vertices_m'],mesh['faces'][faces])
                    r,hit=ray_depth_residual(query,mesh['vertices_m'],mesh['faces'],K)
                    assert np.array_equal(d,metric['posterior_d3d_m'])
                    assert np.array_equal(r,metric['posterior_ray_signed_m'],equal_nan=True)
                    assert np.array_equal(hit,metric['posterior_hit'])
                    recomputed.append(dict(subject=subject,seed=seed,method=method,cache_only='PASS',max_distance_difference_mm=0.,
                        mesh_sha256=sha(path),metric_sha256=sha(metric_path)))
        for method in METHODS:
            for rec in atlas['records']:
                ps=np.asarray([next(r['xyz_m'] for r in points if r['subject']==subject and r['seed']==seed and r['method']==method and r['id']==rec['id']) for seed in cfg['seeds']])
                spread=max(float(np.linalg.norm(ps[a]-ps[b])*1000) for a,b in itertools.combinations(range(3),2))
                stability.append(dict(subject=subject,split='dev' if subject in cfg['dev'] else 'test',method=method,id=rec['id'],
                    max_seed_pair_distance_mm=spread,medical_accuracy=False))
    assert len(fit_rows)==60 and len(splits)==60 and len(old_agreement)==180 and len(recomputed)==4
    write(OUT/'SPLIT_INDEX_MANIFEST.json',splits)
    write(OUT/'OLD_CACHE_METRIC_AGREEMENT.json',dict(status='PASS',rows=old_agreement))
    write(OUT/'INDEPENDENT_CACHE_RECOMPUTATION.json',dict(status='PASS',new_fits=0,rows=recomputed))
    write(OUT/'ENG_SEED_SPREAD_640.json',dict(status='DESCRIPTIVE_ONLY',definition='max pairwise Euclidean displacement across three seed fits per subject/probe',rows=stability))
    write(ROOT/'EXECUTION_LEDGER.json',dict(status='COMPLETE_WITH_BEHAVE_QUALIFICATION_NO_GO',start_date_local='2026-10-03',completion_date_local='2026-10-04',
        atlas=dict(old_cached_meshes_read=300,new_engineering_points=2400,medical_truth=False),
        behave=dict(candidate_timestamps=300,camera_views=1200,new_inferences=0,new_fits=0,
            qualification_file=str(ROOT/'b_qualification/COMMON_SUPPORT_COHORT_LIMITS.json')),
        pressurepose=dict(final_subjects=20,seeds=cfg['seeds'],new_fit_logical_branches=60,reused_meshes=180,final_meshes=240,
            final_metrics=240,new_engineering_points=1920,point_movement_records=960,public_comparison_pages=60,
            new_official_inferences=0,training_runs=0,fit_rows=fit_rows),
        retained_attempt1=dict(successful_cached_fits=57,failed_fit_calls=1,all_solver_calls=58,
            path=str(ROOT/'c_pressure_normal_attempt1'),reason='diagnostic assertion assumed exactly unit length frozen normals'),
        total_physical_normal_solver_calls=118,total_successful_saved_normal_meshes_all_attempts=117,
        final_fit_results_are_attempt2_only=True,optimizer_or_weights_tuned_to_test=False,
        aggregation='seed arithmetic mean -> subject -> role subject median',
        integrity=read(OUT/'POST_EXECUTION_INTEGRITY.json')))
    print('COMPLETION_QA_PASS',len(old_agreement),len(recomputed),len(splits),len(stability),flush=True)

if __name__=='__main__':main()
