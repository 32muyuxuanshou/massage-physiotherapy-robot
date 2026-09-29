import json,pickle,cv2
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from surface_metrics import render_depth
root=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928'); out=root/'inference_3method_v1'/'directional_error_audit_v1';out.mkdir(parents=True,exist_ok=True)
raw=root/'raw';cal=json.loads((root/'calibration/pressurepose_k0_calibration_qa.json').read_text());cs={r['subject']:r for r in cal['rows']};res=json.loads((root/'inference_3method_v1/results.json').read_text());az=np.load(root/'run_assets/anchors.npz');fi=az['face_index'].astype(int);bc=az['barycentric'].astype(float);rows=[]
for r in res['rows']:
 s=r['subject'];d=pickle.load(open(raw/s/'p_select.p','rb'),encoding='latin1');idx=r['pose_index'];rgb=np.asarray(d['RGB'][idx]);pworld=np.asarray(d['pc'][idx],float);c=cs[s];R=np.asarray(c['R_world_to_camera']);C=np.asarray(c['camera_center_m']);P=(pworld-C)@R.T;K=np.asarray(c['K']);h,w=rgb.shape[:2];z=P[:,2];u=np.rint(K[0,0]*P[:,0]/z+K[0,2]).astype(int);v=np.rint(K[1,1]*P[:,1]/z+K[1,2]).astype(int);valid=(z>0)&(u>=0)&(u<w)&(v>=0)&(v<h);u,v=u[valid],v[valid];cloudmask=np.zeros((h,w),np.uint8);cloudmask[v,u]=1;cloud3=cv2.dilate(cloudmask,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
 npz=np.load(root/'inference_3method_v1'/'subjects'/s/'mesh_parameters.npz');faces=npz['faces'];row={'subject':s,'txyz_fallback':bool(r['txyz_fallback']),'txyz_raw_m':r['txyz_raw_m'],'tpose_delta_from_txyz_m':r['tpose_translation_delta_from_txyz_m'],'methods':{}}
 for m,key in zip(res['methods'],['Official_vertices','Txyz_vertices','TxyzPose_vertices']):
  V=np.asarray(npz[key],float);A=(V[faces[fi]]*bc[:,:,None]).sum(1);tree=cKDTree(A);dist,nn=tree.query(P,workers=-1);keep=dist<=np.quantile(dist,.8);rv=P-A[nn]; medvec=np.median(rv[keep],axis=0)
  dep=render_depth(V,faces,K,h,w);mm=(dep>0).astype(np.uint8);inter=((mm>0)&(cloud3>0)).sum();union=((mm>0)|(cloud3>0)).sum(); ys,xs=np.nonzero(mm);cy,cx=ys.mean(),xs.mean();py,px=np.nonzero(cloudmask);pcy,pcx=py.mean(),px.mean();mby,mbx=ys.min(),xs.min();Mby,Mbx=ys.max(),xs.max();pby,pbx=py.min(),px.min();Pby,Pbx=py.max(),px.max()
  row['methods'][m]={'trimmed_nn_residual_median_xyz_mm':(medvec*1000).tolist(),'median_nearest_anchor_distance_mm':float(np.median(dist[keep])*1000),'projected_cloud_to_mesh_iou_r3':float(inter/max(union,1)),'point_coverage_by_mesh':float(mm[v,u].mean()),'mesh_centroid_minus_cloud_centroid_px_xy':[float(cx-pcx),float(cy-pcy)],'mesh_bbox_minus_cloud_bbox_px_xywh':[int(mbx-pbx),int(mby-pby),int((Mbx-mbx)-(Pbx-pbx)),int((Mby-mby)-(Pby-pby))]}
 rows.append(row);print(s,'TXYZ',np.round(np.array(row['txyz_raw_m'])*1000,1),'final3Dres',np.round(row['methods']['Official+Txyz+Pose']['trimmed_nn_residual_median_xyz_mm'],1),'imgΔ',np.round(row['methods']['Official+Txyz+Pose']['mesh_centroid_minus_cloud_centroid_px_xy'],1),flush=True)
report={'status':'COMPLETE','axis_convention':'camera coordinates: +X right, +Y down, +Z forward into scene; image offset +dx right, +dy down','directional_nn_note':'Per-point residuals to nearest of 16384 mesh anchors, trimmed to closest 80%, coordinate-wise median. No anatomical correspondence; directional diagnosis only.','image_note':'Mesh mask rendered with the same K0 calibration; cloud support is the filtered person pointcloud projected into RGB. This is a projection diagnostic, not manual silhouette GT.','rows':rows}
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')

