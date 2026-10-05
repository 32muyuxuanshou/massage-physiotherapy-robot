"""Explicit anatomical-reference candidates to actual patient mesh bindings.

References are supplied by an operator/prompt producer. This module never
renames CT bone-centroid proxies as spinous-process depressions.
"""
import importlib.util
from pathlib import Path

import numpy as np

RULE_ENGINE = Path(__file__).with_name('frozen_rule_engine.py')
spec = importlib.util.spec_from_file_location('existing_rule_engine', RULE_ENGINE)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

LEVELS = ['C7_T1', 'T3', 'T5', 'T9', 'L2']
REQUIRED = LEVELS + ['LEFT_REF', 'RIGHT_REF']
RULES = [dict(id='GV14', name='Dazhui', reference_level='C7_T1', lateral_b_cun=0., laterality='midline'),
         *[dict(id=point+'_'+side[0].upper(), name=name, reference_level=level, lateral_b_cun=1.5, laterality=side)
           for point, name, level in [('BL13','Feishu','T3'),('BL15','Xinshu','T5'),('BL18','Ganshu','T9')]
           for side in ['left','right']],
         dict(id='GV4', name='Mingmen', reference_level='L2', lateral_b_cun=0., laterality='midline')]


def reference_xyz(mesh, references):
    ids = {face: i for i, face in enumerate(mesh['global_face_ids'])}
    vertices = np.asarray(mesh['vertices_m'], dtype=np.float64)
    faces = np.asarray(mesh['faces'], dtype=np.int64)
    points = {}
    for name in REQUIRED:
        ref = references[name]
        bary = np.asarray(ref['barycentric'], dtype=np.float64)
        assert np.isclose(bary.sum(), 1.) and np.all(bary >= -1e-8)
        tri = vertices[faces[ids[ref['face_id']]]]
        points[name] = bary @ tri
    return vertices, faces, points


def generate(mesh, references, b_cun_mm, scale_source):
    """No anatomical estimate, b-cun estimate or robot release is hidden here."""
    assert float(b_cun_mm) > 0 and scale_source.strip()
    vertices, faces, points = reference_xyz(mesh, references)
    lateral = points['RIGHT_REF'] - points['LEFT_REF']
    lateral /= np.linalg.norm(lateral)
    frame = dict(status='SUPPLIED_UNVERIFIED_ANATOMICAL_REFERENCE', coordinate_frame='historical reconstructed camera_m',
                 levels={level: dict(point=points[level].tolist(), lateral_axis=lateral.tolist(),
                                     native_per_b_cun=float(b_cun_mm)/1000) for level in LEVELS})
    output = module.project_rules(vertices, faces, list(range(len(faces))), RULES, frame)
    for point in output['rules']:
        local_face = point['face_index']
        point['face_index'] = mesh['global_face_ids'][local_face]
        point['xyz_m'] = point['surface_xyz']
        point['projection_distance_mm'] = point['projection_distance_native']*1000
    output.update(schema='PATIENT_REFERENCE_RULE_BINDING_V1', subject=mesh['subject'], mesh_sha256=mesh['mesh_sha256'],
                  native_unit='m', display_unit='mm', reference_points_m={k: v.tolist() for k,v in points.items()},
                  supplied_references=references, b_cun_mm=float(b_cun_mm), scale_source=scale_source,
                  lateral_axis=lateral.tolist(), reference_medical_validated=False,
                  calibration_validated=False, robot_release=False,
                  semantic_note='Named references are candidates; no clinician/anatomical accuracy is implied by a successful mesh binding.')
    return output
