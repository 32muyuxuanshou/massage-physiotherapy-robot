"""Observed surface labels: independent depth/K, never a predicted-mesh query.

Input domain is rectified color-aligned pinhole depth, axial Z. Camera distortion
and cross-capture registration must be resolved upstream and stated explicitly.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def bilinear_depth(depth, uv):
    u,v=uv;x=int(np.floor(u));y=int(np.floor(v))
    assert 0<=x<depth.shape[1]-1 and 0<=y<depth.shape[0]-1
    neighborhood=depth[y:y+2,x:x+2]
    assert np.all(np.isfinite(neighborhood)) and np.all(neighborhood>0), 'REFERENCE_DEPTH_UNOBSERVED'
    du=u-x;dv=v-y
    return float(neighborhood[0,0]*(1-du)*(1-dv)+neighborhood[0,1]*du*(1-dv)+
                 neighborhood[1,0]*(1-du)*dv+neighborhood[1,1]*du*dv)


def export(depth_native,K,annotation):
    assert annotation['camera_domain']=='RECTIFIED_COLOR_ALIGNED_PINHOLE_AXIAL_Z'
    depth=depth_native*annotation['depth_native_to_m']
    transform=np.asarray(annotation['reference_camera_to_input_camera_4x4'],float)
    Kinv=np.linalg.inv(np.asarray(K,float));records=[]
    for label in annotation['labels']:
        z=bilinear_depth(depth,label['uv'])
        ray=Kinv@np.array([*label['uv'],1.]);xyz=ray*(z/ray[2])
        input_xyz=(transform@np.append(xyz,1.))[:3]
        records.append(dict(point_id=label['point_id'],rater_id=label['rater_id'],repeat_id=label['repeat_id'],
                            target_semantics=label['target_semantics'],reference_method=label['reference_method'],
                            uv=label['uv'],observed_axial_z_m=z,reference_camera_xyz_m=xyz.tolist(),
                            input_camera_xyz_m=input_xyz.tolist(),
                            evidence_type=annotation['evidence_type']))
    return dict(schema='INDEPENDENT_OBSERVED_SURFACE_REFERENCES_V1',capture_id=annotation['capture_id'],
                model_input_capture_id=annotation['model_input_capture_id'],native_unit='m',records=records,
                camera_domain=annotation['camera_domain'],depth_native_to_m=annotation['depth_native_to_m'],
                reference_camera_to_input_camera_4x4=annotation['reference_camera_to_input_camera_4x4'],
                calibration_evidence=annotation['calibration_evidence'],
                registration_evidence=annotation['registration_evidence'],
                label_depth_source='independent sensor; no predicted mesh projection',
                model_input_contains_reference_marks=annotation['model_input_contains_reference_marks'],
                evidence_type=annotation['evidence_type'],clinical_validated=False,robot_release=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--sensor',type=Path,required=True)
    p.add_argument('--annotations',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    annotation=json.loads(args.annotations.read_text())
    with np.load(args.sensor) as data:result=export(data['depth_native'],data['K'],annotation)
    result['sensor_file_sha256']=hashlib.sha256(args.sensor.read_bytes()).hexdigest()
    result['annotation_file_sha256']=hashlib.sha256(args.annotations.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
