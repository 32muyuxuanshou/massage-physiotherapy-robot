"""Mandatory source-TRAIN two-reference prior, with no test-driven fitting."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from acquire_full_v3 import ROOT


def fit(rows):
    examples=[[] for _ in range(18)]
    used=[];global_used=[];global_examples=[[] for _ in range(18)]
    for row in rows:
        if not row['eligible'] or row['role'] not in ['TRAIN','TRAIN_STRUCTURE_CHECK']:
            continue
        with np.load(row['pack']) as data:
            flags=data['level_valid'];xyz=data['level_xyz_mm']
            origin=np.median(data['points_ras_mm'],axis=0)
        for i in np.flatnonzero(flags):
            global_examples[i].append(((xyz[i]-origin)/500.).tolist())
        global_used.append(row['case'])
        if not flags[3] or not flags[14]:
            continue
        a,b=xyz[[3,14]][:,[0,2]];vector=b-a;length=float(np.linalg.norm(vector))
        down=vector/length;right=np.array([-down[1],down[0]])
        if right[0]<0:
            right=-right
        for i in np.flatnonzero(flags):
            delta=xyz[i,[0,2]]-a
            examples[i].append([float(delta@down/length),float(delta@right/length)])
        used.append(row['case'])
    coefficients=[np.median(v,axis=0).tolist() if v else None for v in examples]
    return dict(source='TRAIN only CT skin proxies',source_cases=used,
                global_source_cases=global_used,
                per_level_training_counts=[len(v) for v in examples],coefficients=coefficients,
                global_prior_normalized_xyz=[np.median(v,axis=0).tolist() if v else None for v in global_examples],
                global_prior_training_counts=[len(v) for v in global_examples],
                coefficient_order=['along_T3_to_L2','orthogonal_RAS_right'],
                references=['T3','L2'],scored_reference_levels_excluded=True,
                source_is_clinical_acupoint_GT=False)


def predict(prior,points,references):
    a,b=references[:,[0,2]];vector=b-a;length=np.linalg.norm(vector)
    down=vector/length;right=np.array([-down[1],down[0]])
    if right[0]<0:
        right=-right
    predicted=[];raw_xz=[]
    for coefficient in prior['coefficients']:
        if coefficient is None:
            predicted.append([np.nan]*3);raw_xz.append([np.nan]*2);continue
        along,lateral=coefficient;xz=a+length*(along*down+lateral*right)
        index=np.argmin(np.sum((points[:,[0,2]]-xz)**2,axis=1))
        raw_xz.append(xz.tolist());predicted.append(points[index].tolist())
    return np.asarray(predicted),np.asarray(raw_xz)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=ROOT/'v3_dataset');args=parser.parse_args()
    path=args.source/'CASE_MANIFEST.json';rows=json.loads(path.read_text())
    prior=fit(rows);prior['manifest_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    (args.source/'TWO_REFERENCE_PRIOR.json').write_text(json.dumps(prior,indent=2)+'\n')
    print(json.dumps({k:v for k,v in prior.items() if k!='source_cases'},indent=2))


if __name__=='__main__':
    main()
