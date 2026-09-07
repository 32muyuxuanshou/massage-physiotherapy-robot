"""Read-only bridge and camera audit; outputs are engineering candidates."""
import hashlib,json,pathlib,sys
import numpy as np
import trimesh
root=pathlib.Path(__file__).resolve().parent
workspace=pathlib.Path.cwd()
handoff=root.parent
resources=workspace/'AI感知模块/模型资源'
upstream=workspace/'AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/MHR/tools/mhr_smpl_conversion/assets'
atlas_path=workspace/'AI感知模块/outputs/交付文件/2026-08-28_20-21-54/engineering_atlas_back20_v1.json'
atlas=json.loads(atlas_path.read_text('utf-8'))
bridge=np.load(resources/'SMPL-X_SKEL_v2.2_internal/alignment/mapping_female.npz')
canonical=np.load(resources/'SMPL-X_SKEL_v2.2_internal/alignment/canonical_female.npz')
smplx=np.load(resources/'SMPL-X/模型/models_lockedhead/smplx/SMPLX_FEMALE.npz')
mapping=np.load(upstream/'mhr2smplx_mapping.npz')
official=trimesh.load(upstream/'mhr_face_mask.ply',process=False)
assert np.array_equal(canonical['faces'],smplx['f'])
assert len(mapping['triangle_ids'])==10475
assert np.allclose(mapping['baryc_coords'].sum(1),1)
loader=resources/'SKEL/loader';sys.path.insert(0,str(loader))
import torch
from skel.skel_model import SKEL
model=SKEL('female',model_path=str(loader/'data/skel'))
with torch.no_grad():
    skin=model(torch.zeros(1,46),torch.zeros(1,10),torch.zeros(1,3),skelmesh=False).skin_verts[0].numpy()
checks=[]
for point in atlas['anchors']:
    ids=np.array(point['vertex_indices']);bw=np.array(point['barycentric'])
    assert np.array_equal(bridge['skel_skin_faces'][point['face_index']],ids)
    assert np.array_equal(model.skin_f.numpy()[point['face_index']],ids)
    xyz=(skin[ids]*bw[:,None]).sum(0)
    side=point['side'];side_ok=(bool(xyz[0]>0) if side=='SUBJECT_LEFT' else bool(xyz[0]<0) if side=='SUBJECT_RIGHT' else None)
    checks.append(dict(id=point['point_id'],side=side,canonical_x=float(xyz[0]),side_sign_ok=side_ok,anchor_position_difference_model_m=float(np.linalg.norm(xyz-point['xyz_local_m'])),bridge_vertices_valid=bool(bridge['valid_mask'][ids].all()),bridge_max_distance_model_m=float(bridge['canonical_distances_m'][ids].max())))
assert max(p['anchor_position_difference_model_m'] for p in checks)<1e-5
assert all(p['side_sign_ok'] is not False for p in checks)
records=[]
for sid in ['S01','S03','S05']:
    pred=np.load(handoff/f'results/{sid}/prediction.npz');v=pred['pred_vertices'];f=pred['faces'];t=pred['pred_cam_t'];fl=float(pred['focal_length'])
    assert np.array_equal(official.faces,f)
    def project(xyz):
        c=xyz+t
        return c[...,:2]/c[...,2:3]*fl+np.array([960,540])
    residual=np.linalg.norm(project(pred['pred_keypoints_3d'])-pred['pred_keypoints_2d'],axis=-1)
    assert residual.max()<.1
    smplx_surface=(v[f[mapping['triangle_ids']]]*mapping['baryc_coords'][:,:,None]).sum(1)
    points=[]
    for a in atlas['anchors']:
        ids=np.array(a['vertex_indices']);bw=np.array(a['barycentric']);xyz=(smplx_surface[bridge['target_indices'][ids]]*bw[:,None]).sum(0)
        points.append(dict(point_id=a['point_id'],side=a['side'],xy=project(xyz).tolist(),xyz_model=xyz.tolist(),medical_label=False,training_eligible=False,target_reference=None,target_error_px=None))
    records.append(dict(id=sid,faces_exact_official_ply=True,camera_reprojection_max_px=float(residual.max()),points=points))
payload=dict(status='NUMERICAL_CHECKS_PASSED_SEMANTICS_UNVALIDATED',mhr_commit='e412e12c9d7287a598f00edf19242b476b440211',official_faces_source='MHR/tools/mhr_smpl_conversion/assets/mhr_face_mask.ply',official_faces_sha256_i64le=hashlib.sha256(np.asarray(official.faces,dtype='<i8').tobytes()).hexdigest(),atlas_sha256=hashlib.sha256(atlas_path.read_bytes()).hexdigest(),unit_note='SAM mhr_head divides MHR vertices by 100 before pred_vertices; no second /100 applied. Model scale is not measured real-world scale.',canonical_checks=checks,frames=records,unverified=['cross-person anatomical correspondence','target point ground truth','real metric scale','dense vertex semantic correspondence beyond topology'])
(root/'geometry_audit.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n','utf-8')
print('PASS: official MHR faces, SKEL anchors, SMPLX faces, barycentric weights, camera convention')
for r in records:print(r['id'],[(p['point_id'],[round(x) for x in p['xy']]) for p in r['points']])
