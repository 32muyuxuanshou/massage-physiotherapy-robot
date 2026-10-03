"""Frozen seed -> subject aggregation, with all individual paired changes."""
import argparse,csv
from pathlib import Path
import numpy as np
from data_v2 import load_json,save_json


def flatten(row):
    r={k:row[k] for k in ['subject','split','seed','method']}
    for reg in ['posterior','torso']:
        for kind in ['d3d','ray_absolute','ray_common_hit_absolute']:
            for metric in ['median_mm','p95_mm']:r[f'{reg}_{kind}_{metric}']=row[reg][kind][metric]
        for metric in ['ray_hit_fraction','ray_common_hit_fraction']:r[f'{reg}_{metric}']=row[reg][metric]
    for k in ['face_flip_frac','edge_strain_p50','edge_strain_p99']:r[k]=row['mesh_quality'][k]
    r['silhouette_iou']=row['silhouette'].get('iou');r['silhouette_boundary_median_px']=row['silhouette'].get('boundary_median_px')
    r['txyz_fallback']=row['optimization'].get('fallback',row['optimization'].get('txyz_fallback'))
    return r


def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def aggregate(out,contract,subjects,methods=None,seeds=None):
    names=methods or contract['methods'];seeds=contract['seeds'] if seeds is None else seeds
    rows=[]
    for s in subjects:rows+=load_json(out/'evaluation'/s/'results.json')
    keys=[(r['subject'],r['seed'],r['method']) for r in rows]
    expected={(s,k,m) for s in subjects for k in seeds for m in names}
    assert len(keys)==len(set(keys)) and set(keys)==expected
    flat=[flatten(r) for r in rows];numeric=[k for k in flat[0] if k not in ['subject','split','seed','method','txyz_fallback']]
    per_subject=[]
    for s in subjects:
        for name in names:
            selection=[r for r in flat if r['subject']==s and r['method']==name]
            r=dict(subject=s,split=selection[0]['split'],method=name)
            for k in numeric:
                values=[x[k] for x in selection if x[k] is not None]
                # Do not quietly average only seeds with valid ray hits.
                r[k]=float(np.mean(values)) if len(values)==len(seeds) else None
            r['txyz_fallback_seeds']=sum(x['txyz_fallback'] is True for x in selection)
            per_subject.append(r)
    paired=[]
    for s in subjects:
        baseline=next(r for r in per_subject if r['subject']==s and r['method']==names[0])
        for r in [x for x in per_subject if x['subject']==s]:
            paired.append(dict(subject=s,split=r['split'],method=r['method'],
                posterior_median_delta_mm=r['posterior_d3d_median_mm']-baseline['posterior_d3d_median_mm'],
                posterior_p95_delta_mm=r['posterior_d3d_p95_mm']-baseline['posterior_d3d_p95_mm'],
                ray_hit_delta=r['posterior_ray_hit_fraction']-baseline['posterior_ray_hit_fraction']))
    summary={}
    for group in ['dev','test','all']:
        summary[group]={}
        for name in names:
            selection=[r for r in per_subject if r['method']==name and (group=='all' or r['split']==group)]
            summary[group][name]=dict(subject_count=len(selection),metrics={})
            for k in numeric:
                values=[r[k] for r in selection if r[k] is not None]
                summary[group][name]['metrics'][k]=dict(n_valid_subjects=len(values),
                    median=float(np.median(values)) if len(values)==len(selection) and values else None)
    formal=(len(subjects)==20 and names==contract['methods'] and seeds==contract['seeds']
            and all(r['source_status'].startswith('FRESH_OFFICIAL') for r in rows))
    result=dict(status='FORMAL_COMPLETE' if formal else 'PARTIAL_OR_OFFLINE_SANITY',row_count=len(rows),
        fresh_official_inference_count=len(subjects) if all(r['source_status'].startswith('FRESH_OFFICIAL') for r in rows) else 0,
        aggregation='seed arithmetic mean -> subject -> split subject median; no seed treated as a new subject',
        subjects=subjects,seeds=seeds,methods=names,summary=summary,per_subject=per_subject,paired_changes=paired,
        interpretation='reconstructed-camera same-source spatial holdout diagnostic; not independent sensor or medical accuracy')
    save_json(out/'AGGREGATED_RESULTS.json',result);write_csv(out/'per_method_subject_seed.csv',flat)
    write_csv(out/'subject_seed_mean.csv',per_subject);write_csv(out/'paired_subject_changes.csv',paired)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--subjects',nargs='+',required=True)
    p.add_argument('--methods',nargs='+');p.add_argument('--seeds',nargs='+',type=int);a=p.parse_args()
    aggregate(a.out,load_json(Path(__file__).resolve().parents[1]/'EXPERIMENT_CONTRACT.json'),a.subjects,a.methods,a.seeds)
