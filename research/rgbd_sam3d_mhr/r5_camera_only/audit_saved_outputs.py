"""Check the completed main path: saved Body identity and a single translation."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def run(root):
    compact=root/'assets/compact_real'
    rows=json.loads((compact/'MANIFEST.json').read_text())['records']
    cells=sorted(p.stem for p in (root/'real_evaluation').glob('repaired__*.json'))
    assert len(cells)==15 and len(rows)==232
    names=['pred_vertices','global_rot','body_pose','shape','scale','hand','face',
           'pred_pose_raw','mhr_model_params','pred_joint_coords','joint_global_rots','pred_keypoints_3d']
    count=0;max_camera_error=0.;max_translation_error=0.
    for row in rows:
        key=Path(row['compact_file']).stem
        with np.load(compact/row['compact_file']) as source:
            body=source['official_pred_vertices'].reshape(-1,3)
            for cell in cells:
                with np.load(root/'real_predictions'/cell/(key+'.npz')) as raw:
                    assert all(np.array_equal(raw[k],source['official_'+k]) for k in names),(cell,key,'Body')
                    error=np.max(np.abs(raw['vertices_camera_A']-(body+raw['pred_cam_t'].reshape(3))))
                    assert error<1e-6,(cell,key,'camera-space vertices')
                    max_camera_error=max(max_camera_error,float(error))
                    with np.load(root/'real_corrected'/cell/(key+'.npz')) as corrected:
                        assert all(np.array_equal(corrected[k],raw[k]) for k in ['global_rot','body_pose','shape','scale'])
                        shift=corrected['applied_translation_m']
                        error=np.max(np.abs(corrected['vertices_camera_A']-raw['vertices_camera_A']-shift))
                        assert error<1e-6,(cell,key,'repeated translation')
                        assert np.max(np.abs(corrected['pred_cam_t']-raw['pred_cam_t']-shift))<1e-6
                        max_translation_error=max(max_translation_error,float(error))
                count+=1
    result=dict(status='PASS',actual_saved_prediction_pairs=count,models=len(cells),frames_per_model=len(rows),
        all_12_Body_fields_exact_equal=True,corrected_Body_exact_equal=True,
        max_camera_space_construction_error_m=max_camera_error,max_single_translation_error_m=max_translation_error,
        TEST_read=False,method='reopen actual prediction/compact/corrected NPZ; compare arrays, not manifest assertion strings')
    (root/'SAVED_OUTPUT_AUDIT.json').write_text(json.dumps(result,indent=2));print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);run(p.parse_args().root)
