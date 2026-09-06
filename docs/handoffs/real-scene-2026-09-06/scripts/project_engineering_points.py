"""Numerical correspondence prototype, NOT anatomically validated labels."""
import hashlib,json,pathlib
import numpy as np

import trimesh

root=pathlib.Path(__file__).resolve().parent
workspace=root.parents[3]
atlas_path=workspace/'AI感知模块/outputs/交付文件/2026-08-28_20-21-54/engineering_atlas_back20_v1.json'
map_path=workspace/'AI感知模块/模型资源/SMPL-X_SKEL_v2.2_internal/alignment/mapping_female.npz'
canonical_path=map_path.parent/'canonical_female.npz'
mhr_map_path=workspace/'AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/MHR/tools/mhr_smpl_conversion/assets/mhr2smplx_mapping.npz'
smplx_path=workspace/'AI感知模块/模型资源/SMPL-X/模型/models_lockedhead/smplx/SMPLX_FEMALE.npz'
atlas=json.loads(atlas_path.read_text('utf-8'))
skel_map=np.load(map_path); mhr_map=np.load(mhr_map_path)
canonical=np.load(canonical_path); smplx=np.load(smplx_path)
assert np.array_equal(canonical['faces'],smplx['f'])
assert np.allclose(mhr_map['baryc_coords'].sum(-1),1)
pred=np.load(root/'server_snapshot/result/S01/prediction.npz')
verts=pred['pred_vertices']; faces=pred['faces']; cam=pred['pred_cam_t']
assert len(verts)==18439 and len(faces)==36874
w,h=1920,1080
focal=float(pred['focal_length'])
def project(xyz):
    c=xyz+cam
    return c[...,:2]/c[...,2:3]*focal+np.array([w/2,h/2])
reprojection=np.linalg.norm(project(pred['pred_keypoints_3d'])-pred['pred_keypoints_2d'],axis=-1)
assert reprojection.max()<.1, 'Camera convention must agree with upstream predictions'
mapped_smplx=(verts[faces[mhr_map['triangle_ids']]]*mhr_map['baryc_coords'][:,:,None]).sum(1)
points=[]; xyzs=[]
for a in atlas['anchors']:
    ids=np.array(a['vertex_indices']); weights=np.array(a['barycentric'])
    assert np.array_equal(skel_map['skel_skin_faces'][a['face_index']],ids)
    assert skel_map['valid_mask'][ids].all()
    target_ids=skel_map['target_indices'][ids]
    xyz=(mapped_smplx[target_ids]*weights[:,None]).sum(0); xyzs.append(xyz)
    uv=project(xyz)
    points.append(dict(point_id=a['point_id'],side=a['side'],region=a['region'],xy_original=uv.tolist(),xyz_model=xyz.tolist(),inside_image=bool(0<=uv[0]<w and 0<=uv[1]<h),medical_annotation=False,training_eligible=False,visibility='UNASSESSED',source_skel_vertices=ids.tolist(),smplx_vertices=target_ids.tolist(),source_barycentric=weights.tolist(),mhr_faces=mhr_map['triangle_ids'][target_ids].tolist(),mhr_barycentric=mhr_map['baryc_coords'][target_ids].tolist(),canonical_bridge_max_distance_model_m=float(skel_map['canonical_distances_m'][ids].max())))
mesh=trimesh.Trimesh(verts,faces,process=False)
_,distances,_=trimesh.proximity.closest_point_naive(mesh,np.array(xyzs))

for p,distance in zip(points,distances):
    p['interpolated_point_to_mhr_surface_model_m']=float(distance)
out=root/'engineering_projection';out.mkdir(exist_ok=True)

report=dict(stage='PROJECTION_PROTOTYPE_NOT_LABEL_VALIDATED',method='Frozen project SKEL->SMPLX nearest canonical vertex map composed with official MHR->SMPLX barycentric surface map; no individualized SKEL fitting',medical_validation=False,training_eligible=False,cross_gender_transfer_validated=False,source_atlas_gender='female',mhr_identity='predicted',external_occlusion_modeled=False,camera='upstream default FOV; no metric calibration',camera_reprojection_max_px=float(reprojection.max()),camera_reprojection_mean_px=float(reprojection.mean()),smplx_topology_exact_match=True,skel_atlas_face_indices_match=True,sources={str(p.relative_to(workspace)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [atlas_path,map_path,canonical_path,mhr_map_path]},points=points)
(out/'projection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(dict(points=len(points),inside_image=sum(p['inside_image'] for p in points),camera_check_max_px=float(reprojection.max()),max_surface_gap_model_m=float(distances.max())),indent=2))
