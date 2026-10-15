"""Dataset-separated aggregation of cached Full and A-only rigid diagnostics."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from analyze_cached import rigid_align,vertex_error


def groups_mean(rows,key,value):
    groups=defaultdict(list)
    for row in rows:groups[row[key]].append(value(row))
    return {key:float(np.mean(v)) for key,v in groups.items()}


def hierarchical(rows,value):
    result={}
    for identity in sorted({r['identity'] for r in rows}):
        rr=[r for r in rows if r['identity']==identity]
        seq=groups_mean(rr,'sequence',value) if 'sequence' in rr[0] else {'all_images':float(np.mean([value(r) for r in rr]))}
        result[identity]=dict(mean=float(np.mean(list(seq.values()))),sequences=seq)
    return dict(identity_equal_mean=float(np.mean([v['mean'] for v in result.values()])),
                frame_equal_mean=float(np.mean([value(r) for r in rows])),per_identity=result)


def paired_counts(rows,key):
    d=np.array([r['stages']['final'][key]-r['stages']['coarse'][key] for r in rows])
    lower=not key.endswith('coverage_50mm')
    good=d<0 if lower else d>0
    return dict(frames=len(rows),improved=int(good.sum()),worse=int((~good & (d!=0)).sum()),
                tied=int((d==0).sum()),frame_delta_mean=float(d.mean()))


def native_root(root,manifest):
    directory=root/'native_root_substitution'
    source=json.loads((directory/'MANIFEST.json').read_text())
    records=[];checks=[]
    tasks=[r for r in manifest['tasks'] if r['dataset']=='native' and r['seed']==11]
    assert len(tasks)==len(source['records'])==400
    S=np.diag([1.,-1.,-1.])
    for t in tasks:
        with np.load(root/'geometry'/t['prediction']) as z:
            body=z['body_m'].astype(np.float64);cam=z['original_camera'].reshape(3).astype(np.float64)
            pred_rot=z['global_rot'].reshape(3)
        with np.load(root/'geometry'/t['truth']) as z:
            truth=z['pred_vertices'].reshape(-1,3).astype(np.float64);gtcam=z['pred_cam_t'].reshape(3).astype(np.float64)
            gtrot=z['global_rot'].reshape(3);Rcv=z['R_world_to_camera']
        path=directory/(t['key']+'.npz')
        old=next(r for r in source['records'] if r['key']==t['key'])
        assert hashlib.sha256(path.read_bytes()).hexdigest()==old['output_sha256']
        with np.load(path) as z:rotated=z['vertices_true_root_m'].astype(np.float64)
        target=truth+gtcam
        values=dict(official=vertex_error(body+cam,target),true_t_only=vertex_error(body+gtcam,target),
                    true_R_only=vertex_error(rotated+cam,target),true_R_true_t=vertex_error(rotated+gtcam,target),
                    centered_official=vertex_error(body-body.mean(0),truth-truth.mean(0)),
                    centered_true_R=vertex_error(rotated-rotated.mean(0),truth-truth.mean(0)))
        aligned,rotation=rigid_align(body,rotated)
        Rp=Rotation.from_euler('xyz',pred_rot).as_matrix();Rg=Rotation.from_euler('xyz',gtrot).as_matrix()
        physical_error=float(np.max(np.abs(rotation.T-S@Rg@Rp.T@S)))
        truth_error=float(np.max(np.abs(Rg-S@Rcv@S)))
        rigid_error=float(np.max(np.abs(aligned-rotated)))
        assert physical_error<1e-5 and truth_error<1e-5 and rigid_error<1e-5
        checks.append(dict(key=t['key'],rotation_matrix_max_error=physical_error,
            GT_euler_vs_physical_camera_max_error=truth_error,rigid_vertex_max_abs_m=rigid_error))
        records.append(dict(key=t['key'],identity=t['identity'],role='VAL',metrics=values))
    return dict(status='PASS',frames=400,identities=50,
        aggregation={k:hierarchical(records,lambda r:r['metrics'][k]) for k in records[0]['metrics']},
        records=records,physical_checks=checks,cpu_source=source,
        interpretation='Controlled native-parameter substitution, not a surface-optimal oracle; wrong local pose/shape may compensate wrong global root. No inference of real rotation GT.')


def main(a):
    a.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((a.root/'geometry/MANIFEST.json').read_text())
    records=[json.loads(p.read_text()) for p in sorted((a.root/'q1/records').rglob('*.json'))]
    assert len(records)==2706
    cells=[]
    for dataset in ['native','real','behave']:
        dataset_rows=[r for r in records if r['dataset']==dataset]
        for role in sorted({r['role'] for r in dataset_rows}):
            for seed in [11,23,37]:
                rr=[r for r in dataset_rows if r['seed']==seed and r['role']==role]
                assert rr
                stages={}
                for stage in ['coarse','final']:
                    stages[stage]={k:hierarchical(rr,lambda r:r['stages'][stage][k]) for k in rr[0]['stages'][stage]}
                cell=dict(dataset=dataset,role=role,seed=seed,frames=len(rr),identities=len({r['identity'] for r in rr}),
                    stages=stages,paired={k:paired_counts(rr,k) for k in rr[0]['stages']['coarse']},
                    fine_norm_median_mm=float(np.median([r['fine_norm_mm'] for r in rr])),
                    fine_axis_median_mm=np.median([r['fine_delta_mm'] for r in rr],axis=0).tolist())
                if dataset=='native':
                    direction=[r['native_direction'] for r in rr]
                    cell['direction']=dict(toward_true_camera=sum(r['cosine_to_true_camera']>0 for r in direction),
                        opposite_true_camera=sum(r['cosine_to_true_camera']<0 for r in direction),
                        parallel_fraction_median=float(np.median([r['parallel_fraction'] for r in direction])),
                        orthogonal_mm_median=float(np.median([r['orthogonal_mm'] for r in direction])),
                        camera_improved_but_vertex_worse=sum(r['stages']['final']['camera_mm']<r['stages']['coarse']['camera_mm'] and r['stages']['final']['vertex_camera_mm']>r['stages']['coarse']['vertex_camera_mm'] for r in rr))
                    cell['centered_vs_rigid_reference']={k:hierarchical(rr,lambda r:r['reference_alignment'][k]) for k in ['centered_pve_mm','rigid_reference_pve_mm']}
                else:
                    cell['baseline']={k:hierarchical(rr,lambda r:r['official_txyz'][k]) for k in rr[0]['official_txyz']}
                    cell['final_minus_txyz_axis_median_mm']=np.median([r['final_minus_txyz_xyz_mm'] for r in rr],axis=0).tolist()
                    cell['baseline_fallback_frames']=sum(r['txyz_fallback'] for r in rr)
                cells.append(cell)
    rigid=[json.loads(p.read_text()) for p in sorted((a.root/'rigid/records').glob('*.json'))]
    assert len(rigid)==232 and all(r['historical_Txyz_reproduced'] for r in rigid)
    rigid_groups={}
    for role in ['TRAIN','VAL']:
        rr=[r for r in rigid if r['role']==role];result={}
        for method in ['official_txyz','matched_translation','matched_rigid']:
            get=lambda r: r['official_txyz'] if method=='official_txyz' else r['methods'][method]['metrics']
            result[method]={k:hierarchical(rr,lambda r:get(r)[k]) for k in ['median_mm','p95_mm','coverage_50mm']}
            if method!='official_txyz':
                result[method]['fallback_frames']=sum(r['methods'][method]['fallback'] for r in rr)
                result[method]['rotation_degrees_median']=float(np.median([r['methods'][method]['applied_rotation_deg'] for r in rr]))
        result['paired_rigid_minus_matched_translation']={k:dict(
            improved=sum(r['methods']['matched_rigid']['metrics'][k]<r['methods']['matched_translation']['metrics'][k] for r in rr),
            worse=sum(r['methods']['matched_rigid']['metrics'][k]>r['methods']['matched_translation']['metrics'][k] for r in rr)) for k in ['median_mm','p95_mm']}
        rigid_groups[role]=result
    root_result=native_root(a.root,manifest)
    result=dict(status='OFFLINE_DIAGNOSIS_COMPLETE_GPU_TIMING_DEFERRED',cells=cells,rigid=rigid_groups,
                native_root=root_result,
                q1_records=len(records),rigid_records=len(rigid),new_training=False,
                GPU_timing='NOT_MEASURED_USER_KEEPS_CPU_MODE',
                original_final_reproduction_max={d:max((v for r in records if r['dataset']==d for v in r['final_reproduction_error'].values()),default=None) for d in ['native','real','behave']},
                aggregation='Native image→identity; HuMMan frame→sequence→identity; BEHAVE PVE primary frame-equal, also hierarchical; surface camera→frame→sequence→identity. Mean of frame P95, not pooled P95.',
                scope='Previously consumed diagnostic cohorts; no sealed native/HuMMan TEST, no new B fit, no acupoint accuracy or M3 protocol claims')
    (a.out/'SUMMARY.json').write_text(json.dumps(result,indent=2))
    (a.out/'Q1_RECORDS.json').write_text(json.dumps(records,indent=2))
    (a.out/'RIGID_RECORDS.json').write_text(json.dumps(rigid,indent=2))
    flat=[]
    for r in records:
        base={k:r[k] for k in ['dataset','seed','key','identity','role']}
        base.update(fine_norm_mm=r['fine_norm_mm'],visible_queries=r['visible_queries'])
        for stage in ['coarse','final']:
            base.update({stage+'_'+k:v for k,v in r['stages'][stage].items()})
        base.update({'fine_'+axis+'_mm':r['fine_delta_mm'][i] for i,axis in enumerate(['x','y','z'])})
        flat.append(base)
    columns=list(dict.fromkeys(k for r in flat for k in r))
    with (a.out/'PER_FRAME.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(flat)
    print('SUMMARIZED',len(records),len(rigid),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    main(p.parse_args())
