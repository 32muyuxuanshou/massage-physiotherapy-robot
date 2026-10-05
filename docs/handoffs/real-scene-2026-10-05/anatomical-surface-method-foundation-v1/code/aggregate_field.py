"""Freeze image-equal summaries and retain the common oracle-reference cohort."""
import json
from pathlib import Path

import numpy as np

from acquire_full_v3 import ROOT


def aggregate(rows):
    cohorts={}
    for scope in ['ALL_ELIGIBLE_SOURCE_IMAGES','TWO_REFERENCE_COMMON_IMAGES']:
        selected=[r for r in rows if scope=='ALL_ELIGIBLE_SOURCE_IMAGES' or all(r['oracle_reference_present'])]
        groups={}
        for row in selected:
            groups.setdefault((row['method'],row['case']),[]).append(row)
        per_case=[]
        for (method,case),values in groups.items():
            assert {r['seed'] for r in values}=={0,1,2}, 'THREE_PRESET_SEEDS_REQUIRED'
            per_case.append(dict(method=method,case=case,
                                 anatomy_mean_over_levels_then_median_seeds_mm=float(np.median([r['anatomy_case_mean_mm'] for r in values])),
                                 geometry_mean_then_median_seeds_mm=float(np.median([r['geometry_after_mean_mm'] for r in values]))))
        summaries={}
        for method in sorted({r['method'] for r in per_case}):
            values=[r['anatomy_mean_over_levels_then_median_seeds_mm'] for r in per_case if r['method']==method]
            summaries[method]=dict(CT_images=len(values),median_of_image_means_mm=float(np.median(values)),
                                   mean_of_image_means_mm=float(np.mean(values)),p95_of_image_means_mm=float(np.quantile(values,.95)))
        cohorts[scope]=dict(per_image=per_case,summaries=summaries)
    return cohorts


def main():
    result={}
    for noise in [0.,5.]:
        rows=[]
        for seed in [0,1,2]:
            path=ROOT/'source_evaluation'/('seed'+str(seed)+'_refnoise'+str(noise))/'PER_CASE.json'
            rows.extend(json.loads(path.read_text()))
        result[str(noise)]=aggregate(rows)
    no_reference_rows=[]
    for seed in [0,1,2]:
        path=ROOT/'source_evaluation'/('seed'+str(seed)+'_noreferences')/'PER_CASE.json'
        no_reference_rows.extend(json.loads(path.read_text()))
    result['NONE']=aggregate(no_reference_rows)
    report=dict(status='SOURCE_PROXY_CHARACTERIZATION_NOT_CLINICAL',results=result,
                formula='valid non-prompt levels mean -> median over 3 seeds for each CT image -> image-equal median/mean',
                primary_cohort='TWO_REFERENCE_COMMON_IMAGES',primary_reference_noise_mm=0.,
                supporting_cohort='all eligible source images; prior only available when both references exist',
                patient_disjointness_certified=False,CT_pose_not_certified_prone=True)
    (ROOT/'SOURCE_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:{s:v['summaries'] for s,v in scopes.items()} for k,scopes in result.items()},indent=2))


if __name__=='__main__':
    main()
