"""Twenty actual cached patient surfaces, geometry fixtures only."""
import hashlib
import json
from pathlib import Path

import numpy as np
from check_pipeline import fixture, verify
from reference_completion import propose
from rule_pipeline import generate

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT.parent/'prone-reference-rule-workbench-v1/site'

rows = []
for path in sorted((ASSETS/'cases').glob('*.json')):
    mesh = json.loads(path.read_text()); all_refs = fixture(mesh)
    refs = {k: all_refs[k] for k in ['T3', 'L2', 'LEFT_REF', 'RIGHT_REF']}
    output = propose(mesh, refs); accepted = dict(refs)
    vertices = np.array(mesh['vertices_m']); faces = np.array(mesh['faces'])
    ids = {g: i for i, g in enumerate(mesh['global_face_ids'])}
    for name, proposal in output['suggestions'].items():
        xyz = np.array(proposal['barycentric']) @ vertices[faces[ids[proposal['face_id']]]]
        assert np.allclose(xyz, proposal['xyz_m'], rtol=0, atol=1e-12)
        assert abs(np.linalg.norm(xyz-proposal['raw_target_m'])*1000-proposal['projection_distance_mm']) < 1e-8
        assert proposal['semantic_review_required'] and not proposal['medical_validated']
        accepted[name] = dict(proposal, origin='ENGINEERING_ACCEPTED_CT_PROXY_SUGGESTION')
    rules = generate(mesh, accepted, 25., 'GEOMETRY_FIXTURE_NOT_MEDICAL')
    error = verify(mesh, rules)
    rows.append(dict(subject=mesh['subject'], actual_mesh_sha256=mesh['mesh_sha256'],
                     input_payload_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     max_rule_bary_error_m=error, proposals=output, rule_output=rules))
result = dict(status='PASS', actual_cached_patients=len(rows), suggestions=len(rows)*3, rules=len(rows)*8,
              source='unchanged actual RigidD/input0 mesh; geometric input fixtures, not anatomy', records=rows)
(ROOT/'ENGINEERING_COMPLETION_RESULTS.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k: v for k, v in result.items() if k != 'records'}))
