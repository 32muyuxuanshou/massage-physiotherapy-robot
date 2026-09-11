import json
from pathlib import Path
import cv2,numpy as np
ROOT=Path('/raid5/xuhd/cheap_txyz_inference_visualization_v1_full')
CASES=['p000838_a000084_f000023','p000891_a001199_f000040','p000893_a001415_f000014']
def obj(path):
 v=[];f=[]
 for line in path.read_text().splitlines():
  if line.startswith('v '):v.append([float(x) for x in line.split()[1:4]])
  elif line.startswith('f '):f.append([int(x.split('/')[0])-1 for x in line.split()[1:4]])
 return np.asarray(v),np.asarray(f)
def render(rgb,v,f,K,alpha=.88):
 uv=np.c_[K[0,0]*v[:,0]/v[:,2]+K[0,2],K[1,1]*v[:,1]/v[:,2]+K[1,2]]
 tri=v[f];order=np.argsort(tri[:,:,2].mean(1))[::-1]
 normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normals/=np.linalg.norm(normals,axis=1,keepdims=True).clip(1e-8)
 shade=.62+.34*np.abs(normals@np.array([-.25,-.45,-.86]));mesh=rgb.copy();H,W=rgb.shape[:2]
 for i in order:
  pts=np.rint(uv[f[i]]).astype(np.int32)
  if np.all((pts[:,0]<0)|(pts[:,0]>=W)|(pts[:,1]<0)|(pts[:,1]>=H)):continue
  q=int(np.clip(245*shade[i],150,245));cv2.fillConvexPoly(mesh,pts,(q,q,q),cv2.LINE_AA);cv2.polylines(mesh,[pts],True,(125,135,145),1,cv2.LINE_AA)
 mask=np.any(mesh!=rgb,axis=2);out=rgb.copy();out[mask]=(rgb[mask]*(1-alpha)+mesh[mask]*alpha).astype(np.uint8);return out
def card(case,kind):
 d=ROOT/'visualizations'/('case_'+case);rgb=cv2.cvtColor(cv2.imread(str(d/'input_rgb.png')),cv2.COLOR_BGR2RGB);m=json.loads((d/'metrics.json').read_text());K=np.load(m['source_path'])['K_a'].copy()
 # HuMMan cache keeps calibration at 1920x1080 while the exported RGB is 960x540.
 K[0]*=rgb.shape[1]/1920.;K[1]*=rgb.shape[0]/1080.
 v,f=obj(d/(kind+'_mesh.obj'));im=cv2.resize(render(rgb,v,f,K),(640,360));bar=np.full((52,640,3),248,np.uint8);cv2.putText(bar,f'{case}  {kind.upper()}',(18,23),0,.52,(25,30,38),1,cv2.LINE_AA);cv2.putText(bar,f"held-out Camera-B: {m['official_B']['median_mm']:.1f} -> {m['corrected_B']['median_mm']:.1f} mm",(18,44),0,.48,(30,90,160),1,cv2.LINE_AA);return np.vstack([im,bar])
cv2.imwrite(str(ROOT/'FINAL_CORRECTED_MESH_SHOWCASE.png'),cv2.cvtColor(np.hstack([card(c,'corrected') for c in CASES]),cv2.COLOR_RGB2BGR))
cv2.imwrite(str(ROOT/'FINAL_OFFICIAL_VS_CORRECTED_SHOWCASE.png'),cv2.cvtColor(np.vstack([np.hstack([card(c,'official'),card(c,'corrected')]) for c in CASES]),cv2.COLOR_RGB2BGR))
