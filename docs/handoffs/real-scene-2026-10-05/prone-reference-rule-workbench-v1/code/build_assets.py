"""Reuse the twenty actual input0/RigidD surfaces; no inference or fitting."""
import base64
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

DATA = Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2')
OLD = Path('/raid5/xuhd/datasets/prone_body_query_workbench_v1_20261005')
OUT = Path('/raid5/xuhd/datasets/prone_reference_rule_workbench_v1_20261005')
ASSETS = Path('/raid5/xuhd/datasets/prone_back_point_validation_20261003/assets')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((OLD/'TARGET_MANIFEST.json').read_text())
    chosen = [r for r in manifest if r['split_seed']==0 and r['mesh_method']=='RigidD' and r['method']=='TOPOLOGY']
    mask = np.array(json.loads((ASSETS/'candidate_posterior_mask.json').read_text())['face_ids'])
    for site in ['site_public','site_private']:
        (OUT/site/'cases').mkdir(parents=True,exist_ok=True)
    receipts = []
    for row in chosen:
        mesh_path = Path(row['mesh_path']); assert sha(mesh_path)==row['mesh_sha256']
        data = dict(np.load(mesh_path)); f = data['faces'][mask]; used = np.unique(f)
        local = np.full(len(data['vertices_m']),-1,int); local[used] = np.arange(len(used))
        points = dict(np.load(row['path']))
        input_path = DATA/'inputs'/row['subject']/'input.npz'
        with np.load(input_path) as original:
            rgb = Image.fromarray(original['rgb']); K = original['K']; buf=io.BytesIO();rgb.save(buf,format='JPEG',quality=90)
        payload = dict(subject=row['subject'], vertices_m=data['vertices_m'][used].tolist(), faces=local[f].tolist(),
                       global_face_ids=mask.tolist(), K=K.tolist(), image_width=rgb.width,image_height=rgb.height,
                       mesh_sha256=row['mesh_sha256'], source_frame='historical reconstructed camera_m',
                       source_method='RigidD / input0 / frozen previous cache', rgb_data_url=None,
                       engineering_points=[dict(id='ENG_'+str(i+1),xyz_m=point.tolist()) for i,point in enumerate(points['xyz_m'])],
                       medical_validated=False,calibration_validated=False,robot_release=False)
        public=OUT/'site_public/cases'/(row['subject']+'.json');public.write_text(json.dumps(payload,separators=(',',':')))
        payload['rgb_data_url']='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()
        private=OUT/'site_private/cases'/(row['subject']+'.json');private.write_text(json.dumps(payload,separators=(',',':')))
        receipts.append(dict(subject=row['subject'],role=row['role'],source_mesh_path=str(mesh_path),source_mesh_sha256=sha(mesh_path),
                             original_input_path=str(input_path),original_input_sha256=sha(input_path),
                             public_sha256=sha(public),private_sha256=sha(private),faces=len(mask),vertices=len(used)))
    for site in ['site_public','site_private']:
        (OUT/site/'CASE_INDEX.json').write_text(json.dumps(dict(default='S104',subjects=[r['subject'] for r in receipts]),indent=2))
    (OUT/'ASSET_MANIFEST.json').write_text(json.dumps(receipts,indent=2))
    print('ACTUAL_CACHED_PATIENT_ASSETS',len(receipts),flush=True)


if __name__=='__main__':main()
