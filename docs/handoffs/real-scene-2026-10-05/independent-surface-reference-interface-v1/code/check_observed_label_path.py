"""Synthetic geometric workflow check. No patient or clinician labels exist here."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    output=ROOT/'checks';u,v=np.meshgrid(np.arange(96),np.arange(64))
    depth_native=1200.+.1*u+.2*v
    K=np.array([[240.,0.,48.],[0.,250.,32.],[0.,0.,1.]])
    sensor=output/'SIMULATED_SENSOR_NOT_PATIENT.npz';np.savez_compressed(sensor,depth_native=depth_native,K=K)
    ids=['GV14','BL13_L','BL13_R','BL15_L','BL15_R','BL18_L','BL18_R','GV4']
    labels=[]
    for i,key in enumerate(ids):
        for rater,offset in [('SIMULATED_RATER_A',0.),('SIMULATED_RATER_B',1.)]:
            labels.append(dict(point_id=key,rater_id=rater,repeat_id=0,uv=[10.25+i*8+offset,15.5+i*3],
                               target_semantics='STANDARD_ACUPOINT_LOCATION',
                               reference_method='SYNTHETIC_STANDARD_SLOT_GEOMETRY_NOT_PALPATION'))
    transform=np.eye(4);transform[:3,3]=[.03,-.02,.01]
    annotation=dict(capture_id='SIMULATED_REF_CAPTURE',model_input_capture_id='SIMULATED_INPUT_CAPTURE',
                    camera_domain='RECTIFIED_COLOR_ALIGNED_PINHOLE_AXIAL_Z',depth_native_to_m=.001,
                    reference_camera_to_input_camera_4x4=transform.tolist(),
                    calibration_evidence='ANALYTIC_FIXTURE_ONLY',registration_evidence='KNOWN_SYNTHETIC_RIGID_TRANSFORM',
                    model_input_contains_reference_marks=False,evidence_type='SIMULATED_GEOMETRY_NOT_CLINICAL',labels=labels)
    annotations=output/'SIMULATED_ANNOTATIONS.json';annotations.write_text(json.dumps(annotation,indent=2)+'\n')
    reference=output/'SIMULATED_OBSERVED_REFERENCES.json'
    subprocess.run([sys.executable,str(ROOT/'code/export_observed_reference.py'),'--sensor',str(sensor),
                    '--annotations',str(annotations),'--output',str(reference)],check=True)
    document=json.loads(reference.read_text());expected=[]
    for label in labels:
        uu,vv=label['uv'];zz=(1200.+.1*uu+.2*vv)*.001
        xyz=np.array([(uu-48)/240*zz,(vv-32)/250*zz,zz])+transform[:3,3]
        expected.append(xyz)
    error=float(np.max(abs(np.asarray(expected)-[r['input_camera_xyz_m'] for r in document['records']])))
    assert error<1e-12
    prediction=dict(capture_id='SIMULATED_INPUT_CAPTURE',coordinate_frame='input_camera_m',points=[])
    for label in document['records']:
        if label['rater_id']=='SIMULATED_RATER_A':
            xyz=np.asarray(label['input_camera_xyz_m'])+[.003,.004,.012]
            prediction['points'].append(dict(point_id=label['point_id'],xyz_m=xyz.tolist()))
    pred=output/'SIMULATED_PREDICTIONS.json';pred.write_text(json.dumps(prediction,indent=2)+'\n')
    comparison=output/'SIMULATED_COMPARISON.json'
    subprocess.run([sys.executable,str(ROOT/'code/compare_observed_reference.py'),'--prediction',str(pred),
                    '--reference',str(reference),'--output',str(comparison)],check=True)
    result=json.loads(comparison.read_text())
    first=[r['distance_3d_mm'] for r in result['model_to_each_rater'] if r['rater_id']=='SIMULATED_RATER_A']
    assert len(first)==8 and np.allclose(first,13.,rtol=0,atol=1e-10)
    assert len(result['model_to_each_rater'])==16 and len(result['reference_pair_agreement'])==8
    receipt=dict(status='INDEPENDENT_DEPTH_LABEL_EXPORT_AND_COMPARISON_NORMAL_PATH_PASS',
                 inputs='synthetic depth/K/labels; no human data',labels=16,model_to_rater_comparisons=16,
                 inter_rater_pairs=8,analytic_unprojection_max_error_m=error,known_model_offset_mm=[3,4,12],
                 expected_distance_mm=13.,actual_distance_first_rater_mm=first,
                 predicted_mesh_loaded=False,clinical_accuracy_validated=False,
                 sensor_sha256=hashlib.sha256(sensor.read_bytes()).hexdigest(),
                 observed_labels_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
    (output/'NORMAL_PATH_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
