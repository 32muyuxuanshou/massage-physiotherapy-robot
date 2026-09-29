#!/usr/bin/env python3
import json,pickle,cv2
from pathlib import Path
import numpy as np
from surface_metrics import render_depth
root=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928')
out=root/'inference_3method_v1'/'alignment_diagnostic_v1'
out.mkdir(parents=True,exist_ok=True)
raw=root/'raw'; calib=json.loads((root/'calibration/pressurepose_k0_calibration_qa.json').read_text()); cs={r['subject']:r for r in calib['rows']}
results=json.loads((root/'inference_3method_v1/results.json').read_text()); methods=results['methods']; rows=[]
for r in results['rows']:
 s=r['subject']; d=pickle.load(open(raw/s/'p_select.p','rb'),encoding='latin1'); c=cs[s]; idx=r['pose_index']; rgb=np.asarray(d['RGB'][idx]); pts=(np.asarray(d['pc'][idx],float)-np.asarray(c['camera_center_m']))@np.asarray(c['R_world_to_camera']).T; K=np.asarray(c['K']);h,w=rgb.shape[:2]
 z=pts[:,2];u=np.rint(K[0,0]*pts[:,0]/z+K[0,2]).astype(int);v=np.rint(K[1,1]*pts[:,1]/z+K[1,2]).astype(int);valid=(z>0)&(u>=0)&(u<w)&(v>=0)&(v<h); u,v=u[valid],v[valid]
 pm=np.zeros((h,w),np.uint8);pm[v,u]=1
 dil=cv2.dilate(pm,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
 npz=np.load(root/'inference_3method_v1'/'subjects'/s/'mesh_parameters.npz')
 row={'subject':s,'projected_point_count':int(valid.sum()),'methods':{}}
 for method,key in zip(methods,['Official_vertices','Txyz_vertices','TxyzPose_vertices']):
  dep=render_depth(npz[key],npz['faces'],K,h,w); mm=(dep>0).astype(np.uint8)
  point_covered=float(mm[v,u].mean()); inter=int(((mm>0)&(dil>0)).sum()); union=int(((mm>0)|(dil>0)).sum()); iou=inter/max(union,1); mesh_support=float(((mm>0)&(dil>0)).sum()/max(int((mm>0).sum()),1))
  row['methods'][method]={'point_pixel_coverage':point_covered,'dilated_support_iou_r3':iou,'mesh_pixels_supported_r3':mesh_support,'mesh_pixel_count':int((mm>0).sum()),'point_support_pixel_count':int((pm>0).sum())}
 rows.append(row);print(s,[(m,round(row['methods'][m]['point_pixel_coverage'],3),round(row['methods'][m]['dilated_support_iou_r3'],3)) for m in methods],flush=True)
report={'status':'COMPLETE','metric_note':'2D diagnostic: projection of the official filtered K0 person point cloud versus rendered mesh silhouettes; point support dilated by 3px for IoU. This is not manual ground-truth segmentation.','rows':rows}
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
