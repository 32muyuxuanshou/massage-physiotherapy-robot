import json,csv,ast,sys
from pathlib import Path
import numpy as np
O=Path(__file__).resolve().parent;D=O.parent/'2026-09-08_SAM_NLF_DEV40'
sys.path.insert(0,str(O.parent/'2026-09-08_NLF_ATLAS_QUERY'))
from analyze_query import read_image,save_image,project
import cv2
meta=O.parents[3]/'AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/sam-3d-body/sam_3d_body/metadata/__init__.py'
values={}
for n in ast.parse(meta.read_text(encoding='utf-8')).body:
    if isinstance(n,ast.Assign):
        for t in n.targets:
            if isinstance(t,ast.Name) and t.id in ['MHR70_TO_OPENPOSE','OPENPOSE_TO_COCO']:values[t.id]=ast.literal_eval(n.value)
mapping=[values['MHR70_TO_OPENPOSE'][i] for i in values['OPENPOSE_TO_COCO']][5:17]
binding=json.loads((O.parent/'2026-09-07_MHR_NATIVE_ATLAS_PROPAGATION/native_binding.json').read_text())['points']
idx=np.array([p['vertex_indices'] for p in binding]);bc=np.array([p['barycentric'] for p in binding]);faces=np.load(D/'sam_faces.npy')
rows=[];boards=[];backs=[]
for r in json.loads((O/'manifest.json').read_text(encoding='utf-8-sig')):
    name=r['id'];b=np.load(D/name/'sam.npz');a=np.load(O/name/'adapted.npz');K=np.array(r['K'])
    xy=[]
    for p in [b,a]:xy.append(project((p['vertices_camera'][idx]*bc[...,None]).sum(1),K))
    row=dict(id=name,role=r['regression_role'],atlas_mean_displacement_px=float(np.linalg.norm(xy[1]-xy[0],axis=1).mean()),camera_delta_mm=float(np.linalg.norm(a['pred_cam_t']-b['pred_cam_t'])*1000),local_vertex_mean_delta_mm=float(np.linalg.norm(a['pred_vertices']-b['pred_vertices'],axis=-1).mean()*1000))
    ann=r['coco17_annotation']
    if ann is not None:
        ref=np.array(ann['keypoints']).reshape(17,3)[5:17];valid=ref[:,2]>0;s=float(np.sqrt(ann['bbox'][2]*ann['bbox'][3]));assert valid.any()
        row['joint_count']=int(valid.sum())
        for model,p in [('baseline',b),('adapted',a)]:
            dist=np.linalg.norm(p['pred_keypoints_2d'][mapping][valid]-ref[valid,:2],axis=1)
            row[model+'_mean_px']=float(dist.mean());row[model+'_nme']=float(dist.mean()/s);row[model+'_pck05']=float((dist/s<.05).mean())
        row['delta_nme']=row['adapted_nme']-row['baseline_nme']
    rows.append(row)
    im=read_image(D/name/'original_display.jpg');h,w=im.shape[:2];scale=np.array([w/r['width'],h/r['height']]);panels=[]
    for title,p,points in [('baseline',b,xy[0]),('adapted',a,xy[1])]:
        canvas=im.copy();mask=np.zeros((h,w),np.uint8);uv=project(p['vertices_camera'],K)
        for tri in np.round(uv[faces]*scale).astype(np.int32):cv2.fillConvexPoly(mask,tri,255)
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);cv2.drawContours(canvas,contours,-1,(255,255,0),1)
        if ann is None:
            for pt in points*scale:cv2.circle(canvas,tuple(np.round(pt).astype(int)),2,(0,255,255),-1)
        else:
            for pred,gt in zip(p['pred_keypoints_2d'][mapping][valid]*scale,ref[valid,:2]*scale):
                pxy=tuple(np.round(pred).astype(int));gxy=tuple(np.round(gt).astype(int));cv2.line(canvas,pxy,gxy,(0,0,255),1);cv2.circle(canvas,gxy,3,(0,255,0),-1);cv2.circle(canvas,pxy,2,(255,0,255),-1)
        canvas=cv2.copyMakeBorder(canvas,36,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25));label=name+' '+title
        if ann is not None:label+=f" NME={row[title+'_nme'] if title=='baseline' else row['adapted_nme']:.4f}"
        cv2.putText(canvas,label,(8,24),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1);panels.append(canvas)
    board=np.concatenate(panels,1);save_image(O/name/'comparison.jpg',board)
    thumb=cv2.resize(board,(960,round(board.shape[0]*960/board.shape[1])))
    boards.append(thumb)
    if name.startswith('B'):backs.append(thumb)
scored=[r for r in rows if r['role']=='unused_in_updates' and 'baseline_nme' in r]
summary=dict(status='DEVELOPMENT_REGRESSION_NOT_INDEPENDENT_TEST',unused_images=sum(r['role']=='unused_in_updates' for r in rows),scored_images=len(scored),joint_count=sum(r['joint_count'] for r in scored),improved_images=sum(r['delta_nme']<0 for r in scored))
for name in ['baseline','adapted']:
    summary[name]={k:float(np.mean([r[name+'_'+k] for r in scored])) for k in ['mean_px','nme','pck05']}
summary['relative_nme_change']=summary['adapted']['nme']/summary['baseline']['nme']-1
summary['worst_delta_cases']=sorted(scored,key=lambda r:r['delta_nme'],reverse=True)[:5]
(O/'summary.json').write_text(json.dumps(dict(aggregate=summary,images=rows),indent=2))
fields=list(dict.fromkeys(k for r in rows for k in r))
with (O/'metrics.csv').open('w',newline='') as f:
    wr=csv.DictWriter(f,fieldnames=fields);wr.writeheader();wr.writerows(rows)
for start in range(0,len(boards),8):save_image(O/f'overview_{start//8+1}.jpg',np.concatenate(boards[start:start+8],0))
save_image(O/'back5.jpg',np.concatenate(backs,0));print(json.dumps(summary,indent=2))
