"""Reuse fixed image-derived N1 references; projected silhouettes, not 3D truth."""
import json,sys,csv
from pathlib import Path
import numpy as np
O=Path(__file__).resolve().parent;D=O.parent/'2026-09-08_SAM_NLF_DEV40'
sys.path.insert(0,str(O.parent/'2026-09-08_NLF_ATLAS_QUERY'))
from analyze_query import read_image,save_image,project
import cv2
refs=json.loads((O.parent/'2026-09-08_INPUT_DIAGNOSTIC/N1_sparse_contours.json').read_text())[0]['samples']
# Drop historical prediction values; preserve only prior image observations.
refs=[{k:r[k] for k in ['y','side','reference_x','uncertainty_px']} for r in refs]
(O/'fixed_references.json').write_text(json.dumps(dict(source='../2026-09-08_INPUT_DIAGNOSTIC/N1_sparse_contours.json',status='PRIOR_AI_IMAGE_OBSERVATIONS_NOT_INDEPENDENT_GROUND_TRUTH',samples=refs),indent=2))

def section(uv,faces,y):
    tri=uv[faces].astype(float);xx=[]
    for a,b in [(0,1),(1,2),(2,0)]:
        aa,bb=tri[:,a],tri[:,b];ok=((aa[:,1]<=y)&(bb[:,1]>y))|((bb[:,1]<=y)&(aa[:,1]>y))
        x=np.full(len(faces),np.nan);x[ok]=aa[ok,0]+(y-aa[ok,1])/(bb[ok,1]-aa[ok,1])*(bb[ok,0]-aa[ok,0]);xx.append(x)
    xx=np.stack(xx,1);valid=np.isfinite(xx).sum(1)==2
    intervals=np.sort(np.where(np.isfinite(xx[valid]),xx[valid],np.inf),axis=1)[:,:2];merged=[]
    for lo,hi in sorted(intervals.tolist()):
        if merged and lo<=merged[-1][1]+1e-4:merged[-1][1]=max(merged[-1][1],hi)
        else:merged.append([lo,hi])
    return next((s for s in merged if s[0]<=2700<=s[1]),None)

rows=[];boards=[]
manifest={r['id']:r for r in json.loads((D/'manifest.json').read_text(encoding='utf-8-sig'))}
for name in ['B1','B2','B3','B4','B5','N1']:
    rgb=read_image(D/name/'original_display.jpg');h,w=rgb.shape[:2];r=manifest[name];scale=np.array([w/r['width'],h/r['height']]);panels=[]
    for model in ['sam','nlf']:
        out=np.load(D/name/(model+'.npz'));v=out['vertices_camera'] if model=='sam' else out['vertices3d'][0]/1000
        assert np.isfinite(v).all() and (v[:,2]>0).all()
        uv=project(v,np.array(r['K']));faces=np.load(D/('sam_faces.npy' if model=='sam' else 'nlf_smpl_faces.npy'))
        mask=np.zeros((h,w),np.uint8)
        for tri in np.round(uv[faces]*scale).astype(np.int32):cv2.fillConvexPoly(mask,tri,255)
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);im=rgb.copy();cv2.drawContours(im,contours,-1,(255,255,0),1)
        # Fixed fitted-mesh bindings for both columns, not NLF direct queries.
        points=np.load(O.parent/'2026-09-08_POINT_STABILITY'/name/'original'/(model+'.npz'))['original_uv'] if model=='sam' else None
        if model=='nlf':
            b=json.loads((O.parent/'2026-09-08_NLF_ATLAS_QUERY/binding.json').read_text())['points']
            idx=np.array([p['vertex_indices'] for p in b]);bc=np.array([p['barycentric'] for p in b]);points=project((v[idx]*bc[...,None]).sum(1),np.array(r['K']))
        for i,p in enumerate(points*scale):
            q=tuple(np.round(p).astype(int));cv2.circle(im,q,2,(0,255,255),-1)
            cv2.putText(im,str(i+1),tuple(np.array(q)+[3,-2]),cv2.FONT_HERSHEY_SIMPLEX,.27,(0,255,255),1)
        if name=='N1':
            for ref in refs:
                sec=section(uv,faces,ref['y']);assert sec is not None
                x=sec[ref['side']];err=float(x-ref['reference_x']);u=ref['uncertainty_px']
                rows.append(dict(model=model,**ref,predicted_x=x,signed_px=err,absolute_px=abs(err),outside_reference_band_px=max(0,abs(err)-u)))
                a=tuple(np.round(np.array([ref['reference_x'],ref['y']])*scale).astype(int));b=tuple(np.round(np.array([x,ref['y']])*scale).astype(int))
                cv2.line(im,a,b,(0,0,255),2);cv2.circle(im,a,4,(0,255,0),-1)
        im=cv2.copyMakeBorder(im,36,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25));cv2.putText(im,name+' '+model+' fitted surface',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1);panels.append(im)
    board=np.concatenate(panels,1);dest=O/name;dest.mkdir(exist_ok=True);save_image(dest/'comparison.jpg',board);boards.append(cv2.resize(board,(1400,round(board.shape[0]*1400/board.shape[1]))))
summary={m:dict(mean_abs_px=float(np.mean([r['absolute_px'] for r in rows if r['model']==m])),mean_outside_band_px=float(np.mean([r['outside_reference_band_px'] for r in rows if r['model']==m]))) for m in ['sam','nlf']}
(O/'summary.json').write_text(json.dumps(dict(status='SPARSE_2D_GEOMETRY_DIAGNOSTIC_NOT_POINT_ACCURACY',summary=summary,samples=rows),indent=2))
with (O/'metrics.csv').open('w',newline='') as f:
    wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
save_image(O/'overview.jpg',np.concatenate(boards,0));print(json.dumps(summary,indent=2))
