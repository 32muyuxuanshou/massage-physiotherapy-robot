"""Supplied camera-space observations + actual mesh -> continuous surface slots.

Current caller uses mesh-sampled observations as an interface fixture. Real depth
observations can be passed without changing this API, but are not certified here.
Ray correction is returned separately, never silently replaces the patient mesh.
"""
import sys
from pathlib import Path
import numpy as np
import torch

from reference_frame import make_frame, to_local, direction_to_local, serializable

FROZEN = Path(__file__).resolve().parents[2]/'prone-reference-rule-workbench-v2/code'
sys.path.insert(0,str(FROZEN))
from rule_pipeline import module, generate


def frame_and_references(mesh, references, camera_origin_m):
    vertices=np.asarray(mesh['vertices_m']);faces=np.asarray(mesh['faces'])
    global_to_local={g:i for i,g in enumerate(mesh['global_face_ids'])}
    xyz=[];normals=[]
    for key in ['T3','L2']:
        ref=references[key];triangle=vertices[faces[global_to_local[ref['face_id']]]]
        xyz.append(np.asarray(ref['barycentric'])@triangle)
        normal=np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0])
        normal/=np.linalg.norm(normal)
        if np.dot(normal,np.asarray(camera_origin_m)-triangle.mean(0))<0:normal=-normal
        normals.append(normal)
    frame=make_frame(xyz,np.mean(normals,axis=0),1000.)
    return frame,np.asarray(xyz)


def decode_field(mesh, field, frame, targets=None):
    if targets is None:targets={'C7_T1':-3/11,'T5':2/11,'T9':6/11}
    vertices=np.asarray(mesh['vertices_m']);faces=np.asarray(mesh['faces']);result={}
    # Both chart coordinates are scaled into physical distances before nearest
    # triangle decoding. All candidate faces are retained; no best-case filtering.
    embedded=np.column_stack([field[:,0]*frame['reference_length_mm'],field[:,1]*500.,np.zeros(len(field))])
    for key,grade in targets.items():
        target=np.array([grade*frame['reference_length_mm'],0.,0.])
        candidates=[module._closest_point_triangle(target,embedded[face]) for face in faces]
        residual=np.array([np.linalg.norm(point-target) for point,_ in candidates])
        index=int(residual.argmin());_,bary=candidates[index];triangle=vertices[faces[index]]
        normal=np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0]);normal/=np.linalg.norm(normal)
        result[key]=dict(face_id=mesh['global_face_ids'][index],barycentric=bary.tolist(),
                        xyz_m=(bary@triangle).tolist(),normal=normal.tolist(),
                        coordinate_residual_mm=float(residual[index]),
                        exact_chart_candidate_faces=int((residual<1e-5).sum()),
                        origin='STRUCTURE_ONLY_LEARNED_CT_PROXY_NOT_ANATOMY',
                        medical_validated=False,semantic_review_required=True)
    return result


def infer_patient(mesh, observed_camera_m, references, camera_origin_m, model):
    vertices=np.asarray(mesh['vertices_m']);frame,ref_xyz=frame_and_references(mesh,references,camera_origin_m)
    local=to_local(vertices,frame)
    rays=vertices-np.asarray(camera_origin_m);rays/=np.linalg.norm(rays,axis=1,keepdims=True)
    observed=torch.from_numpy(to_local(observed_camera_m,frame).astype(np.float32))[None]
    query=torch.from_numpy(local.astype(np.float32))[None]
    refs=torch.from_numpy(to_local(ref_xyz,frame).astype(np.float32))[None]
    unit_rays=torch.from_numpy(direction_to_local(rays,frame).astype(np.float32))[None]
    with torch.no_grad():
        out=model(observed,query,refs,torch.ones(1,2,dtype=torch.bool),unit_rays,hard=True)
    field=out['anatomical_coordinates'][0].numpy();delta_mm=out['ray_delta'][0].numpy()*500.
    slots=decode_field(mesh,field,frame)
    supplied=dict(references);supplied.update(slots)
    rules=generate(mesh,supplied,25.,'FIXTURE_25_MM_NOT_MEDICAL')
    return dict(frame=serializable(frame),supplied_references=references,suggestions=slots,rules=rules,
                learned_field=field,ray_delta_mm=delta_mm,
                geometry_correction_applied=False,medical_validated=False,robot_release=False)
