"""Actual twenty-patient normal-path check using explicitly nonmedical fixtures."""
import hashlib
import json
from pathlib import Path

import numpy as np

from rule_pipeline import LEVELS, generate

ROOT = Path(__file__).resolve().parents[1]


def fixture(mesh):
    vertices = np.array(mesh['vertices_m']); faces = np.array(mesh['faces'])
    centers = vertices[faces].mean(1); xmin, ymin = np.min(centers[:, :2], axis=0)
    xmax, ymax = np.max(centers[:, :2], axis=0); xmid = np.median(centers[:, 0])
    refs = {}
    for name, fraction in zip(LEVELS, [.12, .28, .40, .60, .78]):
        y = ymin + fraction*(ymax-ymin)
        i = int(np.argmin(abs(centers[:, 0]-xmid)+abs(centers[:, 1]-y)))
        refs[name] = dict(face_id=mesh['global_face_ids'][i], barycentric=[1/3]*3,
                          origin='GEOMETRY_FIXTURE_NOT_ANATOMY')
    band = np.flatnonzero(abs(centers[:, 1]-(ymin+.48*(ymax-ymin))) < .1*(ymax-ymin))
    for name, i in [('LEFT_REF', band[np.argmin(centers[band, 0])]), ('RIGHT_REF', band[np.argmax(centers[band, 0])])]:
        refs[name] = dict(face_id=mesh['global_face_ids'][i], barycentric=[1/3]*3,
                          origin='GEOMETRY_FIXTURE_NOT_ANATOMY')
    return refs


def verify(mesh, output):
    vertices = np.array(mesh['vertices_m']); faces = np.array(mesh['faces'])
    ids = {g:i for i,g in enumerate(mesh['global_face_ids'])}
    errors = []
    for point in output['rules']:
        tri = vertices[faces[ids[point['face_index']]]]
        xyz = np.array(point['barycentric']) @ tri
        normal = np.cross(tri[1]-tri[0], tri[2]-tri[0]); normal /= np.linalg.norm(normal)
        error = np.linalg.norm(xyz-point['xyz_m']); assert error < 1e-10
        assert np.allclose(normal, point['surface_normal'], rtol=0, atol=1e-10)
        assert abs(np.linalg.norm(xyz-point['rule_target'])*1000-point['projection_distance_mm']) < 1e-8
        errors.append(error)
    assert len(output['rules']) == 8 and output['robot_release'] is False and output['native_unit'] == 'm'
    return max(errors)


def main():
    index = json.loads((ROOT/'site/CASE_INDEX.json').read_text()); rows = []
    for subject in index['subjects']:
        path = ROOT/'site/cases'/(subject+'.json'); mesh = json.loads(path.read_text())
        output = generate(mesh, fixture(mesh), 25., 'FIXTURE_25_MM_NOT_MEDICAL')
        error = verify(mesh, output)
        rows.append(dict(subject=subject, mesh_sha256=mesh['mesh_sha256'],
                         public_payload_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         max_barycentric_reconstruction_error_m=error, output=output))
        print('actual_patient_rule_path', subject, flush=True)
    result = dict(status='PASS', actual_cached_patients=len(rows), rules=len(rows)*8,
                  scope='geometry-only reference fixtures, exact binding and units; not clinical localization',
                  algorithm='unchanged existing rule_engine.py / explicit operator reference and scale', records=rows)
    (ROOT/'ENGINEERING_FIXTURE_RESULTS.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__=='__main__':main()
