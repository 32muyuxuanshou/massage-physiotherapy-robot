
import json,cv2,numpy as np
from pathlib import Path
root=Path('/raid5/xuhd'); out=root/'back_local_feasibility_v1/visual_v3'; out.mkdir(parents=True,exist_ok=True); seqroot=root/'behave_rgbd_mesh_v1/data/sequences'; calroot=root/'behave_rgbd_mesh_v1/data/calibration/calibs'; raw=root/'back_local_feasibility_v1/formal_eval_v3_complete'
def cam(seq,k):
 date=seq.split('_',1)[0]; c=json.loads((calroot/'intrinsics'/str(k)/'calibration.json').read_text())['color']; e=json.loads((calroot/date/'config'/str(k)/'config.json').read_text()); K=np.array([[c['fx'],0,c['cx']],[0,c['fy'],c['cy']],[0,0,1]],np.float32); return K,np.asarray(c['opencv'][4:],np.float32),np.asarray(e['rotation'],float).reshape(3,3),np.asarray(e['translation'],float)
def xform(v,src,dst):
 K,d,R,t=cam(src[0],src[1]); _,_,R2,t2=cam(dst[0],dst[1]); w=v@R.T+t; return (w-t2)@R2
def render(rgb,v,faces,K,dist,color):
 uv=cv2.projectPoints(v.astype(np.float32),np.zeros(3),np.zeros(3),K,dist)[0].reshape(-1,2); tri=v[faces]; order=np.argsort(tri[:,:,2].mean(1))[::-1]; layer=rgb.copy();h,w=rgb.shape[:2]
 for i in order:
  q=np.rint(uv[faces[i]]).astype(np.int32)
  if np.any((q[:,0]>=0)&(q[:,0]<w)&(q[:,1]>=0)&(q[:,1]<h)):cv2.fillConvexPoly(layer,q,color,cv2.LINE_AA)
 m=np.any(layer!=rgb,2); out=rgb.copy();out[m]=(rgb[m]*.25+layer[m]*.75).astype(np.uint8);return out
for jp in sorted(raw.glob('Sub*/raw/*/*/*/FULL.json')):
 row=json.loads(jp.read_text()); spec=row['spec']; seq=spec['sequence']; fr=spec['frame']; sid=f"{spec['subject']}__{seq}__{fr}"; base=jp.parent; panels=[]
 for k in range(4):
  src=seqroot/seq/fr; rgb=cv2.cvtColor(cv2.imread(str(src/f'k{k}.color.jpg')),cv2.COLOR_BGR2RGB); K,d,_,_=cam(seq,k); imgs=[rgb]
  for name,col in [('Official',(230,70,50)),('Txyz',(40,120,230)),('T_pose',(40,180,80))]:
   z=np.load(base/'FULL_vertices.npz');v=z[name] if k==0 else xform(z[name],(seq,0),(seq,k)); imgs.append(render(rgb,v,z['faces'],K,d,col))
  imgs=[cv2.resize(x,(384,288)) for x in imgs]; panels.append(np.hstack(imgs))
 montage=np.vstack(panels); cv2.imwrite(str(out/f'{sid}_FULL_K0K1K2K3.png'),cv2.cvtColor(montage,cv2.COLOR_RGB2BGR))
 # all conditions as a compact three-row sheet using K1 only
 rowsheet=[]
 for cond in ['FULL','UPPER','LOCAL_TORSO']:
  j=base/f'{cond}.json'; r2=json.loads(j.read_text()); z=np.load(base/f'{cond}_vertices.npz'); k=1; src=seqroot/seq/fr; rgb=cv2.cvtColor(cv2.imread(str(src/'k1.color.jpg')),cv2.COLOR_BGR2RGB); K,d,_,_=cam(seq,1); ims=[cv2.resize(rgb,(384,288))]
  for name,col in [('Official',(230,70,50)),('Txyz',(40,120,230)),('T_pose',(40,180,80))]: ims.append(cv2.resize(render(rgb,xform(z[name],(seq,0),(seq,1)),z['faces'],K,d,col),(384,288)))
  rowsheet.append(np.hstack(ims))
 cv2.imwrite(str(out/f'{sid}_K1_conditions.png'),cv2.cvtColor(np.vstack(rowsheet),cv2.COLOR_RGB2BGR))
print('done',len(list(out.glob('*.png'))))
