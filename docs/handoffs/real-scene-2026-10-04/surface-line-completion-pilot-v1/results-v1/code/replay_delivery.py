"""Independently recompute reported scores from downloaded immutable curve/input caches."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(root, remote_path):
    return root/'predictions'/Path(remote_path).name


def main(root):
    freeze=read(root/'PREDICTION_FREEZE.json')
    assert sha(root/'PREDICTION_MANIFEST.json')==freeze['manifest_sha256']
    assets={**freeze['input_sha256'],**freeze['prediction_sha256']}
    assert all(sha(local(root,path))==digest for path,digest in assets.items())
    rows=read(root/'RESULTS.json')['records']
    with np.load(root/'REFERENCE_EVALUATION_ONLY.npz') as z:
        references={str(candidate):(z['ys_m'][i].copy(),z['target_x_m'][i].copy(),z['target_row_valid'][i].copy())
                    for i,candidate in enumerate(z['candidate_id'])}
    maximum=0.;cache={};support_checks=0
    for row in rows:
        if row['status']!='COMPLETE':continue
        ys,target,valid=references[row['candidate_id']]
        with np.load(local(root,row['path'])) as z:
            xy=z['query_xy_m'];source=z['source_point_indices'];visible=z['visible_point_indices']
        with np.load(local(root,row['input_path'])) as z:
            assert np.array_equal(visible,z['visible_point_indices'])
            assert np.all(z['features'][0,~z['valid']]==0)
        assert np.isin(source,visible).all()
        support_checks+=len(source)
        keep=valid&(ys>=xy[:,1].min())&(ys<=xy[:,1].max())
        error=np.abs(np.interp(ys,xy[:,1],xy[:,0])-target)*1000
        recomputed={'lateral_median_mm':float(np.median(error[keep])),
                    'lateral_p95_mm':float(np.quantile(error[keep],.95)),
                    'label_coverage':float(keep.sum()/valid.sum())}
        for key,value in recomputed.items():
            delta=abs(value-row[key]);maximum=max(maximum,delta);assert delta<1e-10,(row['path'],key,delta)
        cache[(row['candidate_id'],row['condition'],row['method'],row['seed'])]=(error,keep)
    maximum_common=0.
    for candidate in references:
        for condition in ['FULL','MISSING_0','MISSING_1','MISSING_2']:
            entries={k:v for k,v in cache.items() if k[0]==candidate and k[1]==condition}
            common=references[candidate][2].copy()
            for error,keep in entries.values():common&=keep
            for reported in read(root/'RESULTS.json')['common_positions']:
                if reported['candidate_id']!=candidate or reported['condition']!=condition:continue
                key=(candidate,condition,reported['method'],reported['seed'])
                value=float(np.median(entries[key][0][common]))
                delta=abs(value-reported['common_lateral_median_mm'])
                maximum_common=max(maximum_common,delta);assert delta<1e-10
                assert int(common.sum())==reported['common_rows']
    report=dict(status='PASS',metric_records=len(rows),successful_records=len(cache),
                failed_records=len(rows)-len(cache),hashed_prediction_and_input_assets=len(assets),
                source_index_membership_checks=support_checks,
                max_metric_recalculation_difference=maximum,
                max_common_position_recalculation_difference=maximum_common,
                models_rerun=False,geometry_refit=False,scope='cache consistency, not independent clinical validation')
    (root/'CACHE_REPLAY_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    fields=['candidate_id','condition','method','seed','status','lateral_median_mm','lateral_p95_mm','label_coverage','supported_fraction_3mm','prediction_seconds']
    with (root/'PER_RECORD_RESULTS.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    print(json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args().root)
