"""Exact camera-error decomposition; real surfaces remain descriptive, not GT."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import numpy as np


def describe(values):
    a=np.asarray(values)
    return dict(count=len(a),median=float(np.median(a)),q25=float(np.quantile(a,.25)),q75=float(np.quantile(a,.75)))


def main(a):
    rows=json.loads(a.records.read_text());output=[];groups=[]
    for r in rows:
        dataset=r['dataset'];metric='camera_mm' if dataset=='native' else 'median_mm' if dataset=='real' else 'pve_mm'
        coarse=r['stages']['coarse'][metric];final=r['stages']['final'][metric]
        item={k:r[k] for k in ['dataset','seed','key','identity','role']}
        item.update(metric=metric,coarse=coarse,final=final,worse=final>coarse,delta=final-coarse,
                    fine_norm_mm=r['fine_norm_mm'],visible_queries=r['visible_queries'])
        if dataset=='native':
            need=np.array(r['native_direction']['target_camera_m'])-np.array(r['coarse_camera_m'])
            delta=np.array(r['final_camera_m'])-np.array(r['coarse_camera_m'])
            dot=float(np.dot(delta,need));r2=float(np.dot(need,need));d2=float(np.dot(delta,delta))
            parallel2=dot**2/r2 if r2 else 0.;perpendicular2=max(0.,d2-parallel2)
            exact_difference=(d2-2*dot)*1e6
            assert abs((final**2-coarse**2)-exact_difference)<1e-6
            if final<=coarse:kind='improved_or_tied'
            elif r2==0:kind='nonzero_update_at_true_camera'
            elif dot<=0:kind='opposite_direction'
            elif parallel2>2*dot:kind='parallel_overshoot_alone_worsens'
            else:kind='orthogonal_component_erases_parallel_gain'
            item.update(kind=kind,parallel_fraction=dot/r2 if r2 else None,
                perpendicular_mm=float(np.sqrt(perpendicular2)*1000),
                parallel_squared_error_change_mm2=(parallel2-2*dot)*1e6,
                perpendicular_squared_error_change_mm2=perpendicular2*1e6,
                exact_squared_error_change_mm2=exact_difference,
                half_step_camera_mm=float(np.linalg.norm(need-.5*delta)*1000),
                oracle_stop_camera_mm=min(coarse,final))
        else:item['kind']='no_true_camera_available_surface_change_only'
        output.append(item)
    for dataset in ['native','real','behave']:
        for role in sorted({r['role'] for r in output if r['dataset']==dataset}):
            for seed in [11,23,37]:
                rr=[r for r in output if r['dataset']==dataset and r['role']==role and r['seed']==seed]
                group=dict(dataset=dataset,role=role,seed=seed,total=len(rr),kinds=dict(Counter(r['kind'] for r in rr)))
                for name,worse in [('worse',True),('not_worse',False)]:
                    selected=[r for r in rr if r['worse']==worse]
                    group[name]={k:describe([r[k] for r in selected]) for k in ['coarse','fine_norm_mm','visible_queries']}
                if dataset=='native':
                    group['native_counterfactual']={k:float(np.mean([r[k] for r in rr])) for k in ['coarse','final','half_step_camera_mm','oracle_stop_camera_mm']}
                groups.append(group)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'UPDATE_CLASSIFICATION.json').write_text(json.dumps(dict(
        status='DESCRIPTIVE_DIAGNOSIS_COMPLETE',groups=groups,records=output,
        formula='E_final^2-E_coarse^2=norm(delta)^2-2*delta.dot(t_GT-t_coarse)',
        interpretation='Direction and overstep labels apply only to Native camera error. Grouping by outcome is exploratory and mathematically coupled to starting error, not causal proof of an observable gate.',
        camera_B_fitting=False,new_training=False),indent=2))
    keys=list(dict.fromkeys(k for r in output for k in r))
    with (a.out/'UPDATE_CLASSIFICATION.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(output)
    for r in groups:
        if r['dataset']=='native':print(r['seed'],r['kinds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--records',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
