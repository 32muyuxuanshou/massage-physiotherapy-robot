"""Source-frozen two-reference prior to unverified patient-surface proposals.

This transfers a CT proxy ratio, never a clinically identified spinous depression.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from rule_pipeline import module

PRIOR_PATH = Path(__file__).with_name('frozen_reference_prior.json')


def propose(mesh, references):
    vertices = np.asarray(mesh['vertices_m']); faces = np.asarray(mesh['faces'])
    ids = {face: i for i, face in enumerate(mesh['global_face_ids'])}
    points = {name: np.asarray(ref['barycentric']) @ vertices[faces[ids[ref['face_id']]]]
              for name, ref in references.items()}
    first, last = points['T3'], points['L2']
    direction = last-first; length = np.linalg.norm(direction); axial = direction/length
    lateral = points['RIGHT_REF']-points['LEFT_REF']
    lateral -= np.dot(lateral, axial)*axial; lateral /= np.linalg.norm(lateral)
    prior = json.loads(PRIOR_PATH.read_text()); suggestions = {}
    for index, name in [(0, 'C7_T1'), (2, 'T5'), (3, 'T9')]:
        dx, fraction = prior['parameters'][index]
        target = first+fraction*direction+dx*length*lateral
        candidates = [module._closest_point_triangle(target, vertices[f]) for f in faces]
        distances = np.array([np.linalg.norm(p-target) for p, _ in candidates])
        i = int(distances.argmin()); xyz, bary = candidates[i]; tri = vertices[faces[i]]
        normal = np.cross(tri[1]-tri[0], tri[2]-tri[0]); normal /= np.linalg.norm(normal)
        suggestions[name] = dict(face_id=mesh['global_face_ids'][i], barycentric=bary.tolist(),
                                 xyz_m=xyz.tolist(), normal=normal.tolist(), raw_target_m=target.tolist(),
                                 projection_distance_mm=float(distances[i]*1000),
                                 prior_fraction=float(fraction), prior_lateral_ratio=float(dx),
                                 source_training_cases=prior['per_level_source_count'][index],
                                 origin='CT_PROXY_TWO_REFERENCE_PRIOR_SUGGESTION',
                                 semantic_review_required=True, medical_validated=False,
                                 semantic_note='CT surface proxy ratio transferred to candidate slot; not the named spinous-process depression.')
    return dict(schema='TWO_REFERENCE_PATIENT_PROPOSALS_V1', subject=mesh['subject'], mesh_sha256=mesh['mesh_sha256'],
                input_references=references, axial_reference_length_mm=float(length*1000),
                local_axial_direction=axial.tolist(), local_lateral_direction=lateral.tolist(),
                prior_sha256=hashlib.sha256(PRIOR_PATH.read_bytes()).hexdigest(), suggestions=suggestions,
                frame_transfer='3D chord T3-to-L2 plus orthogonalized supplied lateral axis; different from CT X/Z frame',
                calibration_validated=False, medical_validated=False, robot_release=False)
