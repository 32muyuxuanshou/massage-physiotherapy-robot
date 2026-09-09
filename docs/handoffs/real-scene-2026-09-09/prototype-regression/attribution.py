"""N1 training-image counterfactual decomposition; not causal or accuracy proof."""
import json
from pathlib import Path
import numpy as np
O=Path(__file__).resolve().parent;D=O.parent/'2026-09-08_SAM_NLF_DEV40'
b=np.load(D/'N1/sam.npz');a=np.load(O/'N1/adapted.npz');faces=np.load(D/'sam_faces.npy')
refs=json.loads((O.parent/'2026-09-08_LOCAL_GEOMETRY/fixed_references.json').read_text())['samples']
def section(uv,y):
    tri=uv[faces];xx=[]
    for i,j in [(0,1),(1,2),(2,0)]:
        x,z=tri[:,i],tri[:,j];ok=((x[:,1]<=y)&(z[:,1]>y))|((z[:,1]<=y)&(x[:,1]>y));v=np.full(len(tri),np.nan)
        v[ok]=x[ok,0]+(y-x[ok,1])/(z[ok,1]-x[ok,1])*(z[ok,0]-x[ok,0]);xx.append(v)
    xx=np.stack(xx,1);xx=xx[np.isfinite(xx).sum(1)==2];intervals=np.sort(np.where(np.isfinite(xx),xx,np.inf),axis=1)[:,:2];merged=[]
    for lo,hi in sorted(intervals.tolist()):
        if merged and lo<=merged[-1][1]+1e-4:merged[-1][1]=max(hi,merged[-1][1])
        else:merged.append([lo,hi])
    return next(s for s in merged if s[0]<=2700<=s[1])
combos={'baseline':(b,b),'camera_only':(b,a),'geometry_only':(a,b),'both':(a,a)};out={}
for name,(geo,cam) in combos.items():
    v=geo['pred_vertices']+cam['pred_cam_t'];p=v@b['K'].T;uv=p[:,:2]/p[:,2:];err=[float(section(uv,r['y'])[r['side']]-r['reference_x']) for r in refs]
    out[name]=dict(signed_px=err,mean_absolute_px=float(np.abs(err).mean()))
result=dict(status='TRAINING_IMAGE_COUNTERFACTUAL_ONLY',camera_delta_mm=((a['pred_cam_t']-b['pred_cam_t'])*1000).tolist(),mean_local_vertex_change_mm=float(np.linalg.norm(a['pred_vertices']-b['pred_vertices'],axis=-1).mean()*1000),combinations=out,interpretation='Geometry includes global rotation, pose, shape and scale; not a shape-only change. Camera/geometry effects are coupled and non-additive. No independent 3D reference.')
(O/'attribution.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
