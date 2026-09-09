import json,sys
from pathlib import Path
import numpy as np
O=Path(__file__).resolve().parent;D=O.parent/'2026-09-08_SAM_NLF_DEV40'
sys.path.insert(0,str(O.parent/'2026-09-08_NLF_ATLAS_QUERY'))
from analyze_query import read_image,save_image,project
import cv2
report=json.loads((O/'report.json').read_text())
refs=json.loads((O/'fixed_references.json').read_text())['samples']
r=next(x for x in json.loads((O/'samples.json').read_text()) if x['id']=='N1')
im=read_image(D/'N1/original_display.jpg');h,w=im.shape[:2];scale=np.array([w/r['wh'][0],h/r['wh'][1]])
faces=np.load(D/'sam_faces.npy')
b=json.loads((O.parent/'2026-09-07_MHR_NATIVE_ATLAS_PROPAGATION/native_binding.json').read_text())['points'];idx=np.array([p['vertex_indices'] for p in b]);bc=np.array([p['barycentric'] for p in b]);panels=[]
for tag in ['before','after']:
    data=np.load(O/(tag+'_N1.npz'));v=data['vertices_camera'];uv=project(v,data['K']);mask=np.zeros((h,w),np.uint8)
    for tri in np.round(uv[faces]*scale).astype(np.int32):cv2.fillConvexPoly(mask,tri,255)
    cnt,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);canvas=im.copy();cv2.drawContours(canvas,cnt,-1,(255,255,0),1)
    pts=project((v[idx]*bc[...,None]).sum(1),data['K'])*scale
    for p in pts:cv2.circle(canvas,tuple(np.round(p).astype(int)),2,(0,255,255),-1)
    for rr,x in zip(refs,data['contour_x']):
        a=tuple(np.round(np.array([rr['reference_x'],rr['y']])*scale).astype(int));z=tuple(np.round(np.array([x,rr['y']])*scale).astype(int));cv2.line(canvas,a,z,(0,0,255),2);cv2.circle(canvas,a,4,(0,255,0),-1)
    metric=next(x for x in report[tag] if x['id']=='N1')['mean_contour_px']
    canvas=cv2.copyMakeBorder(canvas,40,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25));cv2.putText(canvas,f'{tag}: training-image contour {metric:.2f}px',(10,26),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1);panels.append(canvas)
save_image(O/'before_after.jpg',np.concatenate(panels,1))
summary={}
for tag in ['before','after']:
    summary[tag]=dict(mean_generic_joint_loss=float(np.mean([r['joint_loss'] for r in report[tag] if 'joint_loss' in r])),target=next(x for x in report[tag] if x['id']=='N1'))
(O/'analysis.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
