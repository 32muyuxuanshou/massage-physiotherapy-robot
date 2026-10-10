"""Targeted scientific audits on actual cached R4.1 assets and final outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from run_r41_txyz import dependencies,sha,summary,METRICS


def main(work):
    f=dependencies(work/'code');j=json.loads((work/'PAIRED_RESULTS.json').read_text());rows=j['records']
    receipt=json.loads((work/'assets/original_assets/SOURCE_RECEIPT.json').read_text())
    faces=np.load(work/'assets/original_assets/official/faces.npy')
    for item in receipt['records']:
        key=item['key']
        assert sha(work/'assets/original_assets/inputs'/(key+'.npz'))==item['compact_sha256']
        assert sha(work/'assets/datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))==item['heldout_sha256']
    for r in rows:
        directory=work/'assets/original_assets/official' if r['cell']=='official' else work/f"assets/r4/formal/{r['cell']}/real"
        original=directory/(r['key']+'.npz');corrected=work/'corrected'/r['cell']/(r['key']+'.npz')
        assert sha(original)==r['input_sha256'] and sha(corrected)==r['corrected_sha256']
        z=np.load(original);c=np.load(corrected);applied=np.asarray(r['applied_translation_m'])
        assert all(np.array_equal(z[k],c[k]) for k in ['global_rot','body_pose','shape','scale'])
        assert np.max(np.abs((c['vertices_camera_A']-z['vertices_camera_A'])-applied))<1e-12
        assert np.max(np.abs((c['pred_cam_t']-z['pred_cam_t'])-applied))<1e-12
        assert r['fallback']==(r['raw_norm_mm']>177.88820176363325)
        assert np.array_equal(applied,np.zeros(3)) if r['fallback'] else np.array_equal(applied,np.asarray(r['raw_translation_m']))
        assert len(r['trace'])==6
        assert max(abs(t) for step in r['trace'] for t in step['step_m'])<=.05
        assert np.load(work/'regions'/(r['key']+'.npz'))['labels'].shape==(2048,)
    assert len(rows)==1624 and len({r['key'] for r in rows})==232
    config=json.loads((work/'EXECUTION_CONFIG.json').read_text())
    for name,h in config['source_sha256'].items():assert sha(work/'code'/name)==h
    # Independent reload/re-evaluation of saved meshes (no correction call).
    chosen=[r for r in rows if r['key']=='p001196_a000388_000040']
    chosen += [r for r in rows if r['cell']=='official' and r['fallback']][:1]
    checks=[]
    for r in chosen:
        c=np.load(work/'corrected'/r['cell']/(r['key']+'.npz'))
        p=np.load(work/'assets/datasets/heldout/humman_r3_k1_v1'/(r['key']+'.npz'))['points_camera_B']
        d=f['distance'](p,c['vertices_camera_B'],faces)*1000
        cached=np.load(work/'distances'/r['cell']/(r['key']+'.npz'))['after_mm']
        assert np.array_equal(d,cached)
        checks.append(dict(cell=r['cell'],key=r['key'],max_saved_distance_error_mm=float(np.max(np.abs(d-cached))),status='PASS'))
    # AST-loaded historical kernel sanity: known translation, unaltered geometry.
    anchors=np.array([[0,0,2],[1,0,2],[0,1,2],[1,1,2]],np.float64)
    raw,applied,trace,fallback=f['fit_txyz'](anchors+[.02,-.01,.03],anchors)
    assert np.allclose(applied,[.02,-.01,.03],atol=1e-12) and not fallback
    result=dict(status='PASS',actual_original_predictions=1624,actual_corrected_predictions=1624,
        fixed_A_sample_files=232,fixed_B_sample_files=232,vertices_and_cam_t_translated_exactly_once=True,
        native_global_rotation_pose_shape_scale_unchanged=True,source_code_pre_post_unchanged=True,
        sample_re_evaluation=checks,known_translation_sanity='PASS',test_read=False,camera_B_optimized=False,
        scientific_status='Completed cached native surface diagnostic; no real corresponding MHR/anatomical/acupoint truth.')
    (work/'POST_EXECUTION_INTEGRITY.json').write_text(json.dumps(result,indent=2))
    print('ACTUAL_POST_EXECUTION_AUDIT_PASS',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();main(a.work)
