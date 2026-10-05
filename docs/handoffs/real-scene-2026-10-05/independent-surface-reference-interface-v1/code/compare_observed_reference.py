"""Each rater is retained. Pairwise agreement is not turned into perfect truth."""
import argparse
import json
from itertools import combinations
from pathlib import Path
import numpy as np


def compare(prediction,reference):
    assert prediction['capture_id']==reference['model_input_capture_id']
    assert prediction['coordinate_frame']=='input_camera_m'
    targets={p['point_id']:np.asarray(p['xyz_m']) for p in prediction['points']}
    comparisons=[];groups={}
    for label in reference['records']:
        if label['target_semantics']!='STANDARD_ACUPOINT_LOCATION':continue
        key=label['point_id'];groups.setdefault(key,[]).append(label)
        if key not in targets:continue
        delta=(targets[key]-np.asarray(label['input_camera_xyz_m']))*1000.
        comparisons.append(dict(point_id=key,rater_id=label['rater_id'],repeat_id=label['repeat_id'],
                                delta_camera_xyz_mm=delta.tolist(),distance_3d_mm=float(np.linalg.norm(delta)),
                                evidence_type=label['evidence_type']))
    agreement=[]
    for key,labels in groups.items():
        for a,b in combinations(labels,2):
            distance=float(np.linalg.norm(np.asarray(a['input_camera_xyz_m'])-b['input_camera_xyz_m'])*1000)
            agreement.append(dict(point_id=key,raters=[a['rater_id'],b['rater_id']],
                                  repeat_ids=[a['repeat_id'],b['repeat_id']],distance_3d_mm=distance,
                                  agreement_type='inter_rater' if a['rater_id']!=b['rater_id'] else 'within_rater_repeat'))
    return dict(schema='MODEL_TO_INDEPENDENT_REFERENCE_COMPARISON_V1',capture_id=prediction['capture_id'],
                model_to_each_rater=comparisons,reference_pair_agreement=agreement,
                prediction_points_without_acupoint_reference=sorted(set(targets)-set(groups)),
                acupoint_reference_without_prediction=sorted(set(groups)-set(targets)),
                reference_depth_source=reference['label_depth_source'],evidence_type=reference['evidence_type'],
                calibration_evidence=reference['calibration_evidence'],registration_evidence=reference['registration_evidence'],
                clinical_accuracy_validated=False,robot_release=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--prediction',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=compare(json.loads(a.prediction.read_text()),json.loads(a.reference.read_text()))
    a.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
