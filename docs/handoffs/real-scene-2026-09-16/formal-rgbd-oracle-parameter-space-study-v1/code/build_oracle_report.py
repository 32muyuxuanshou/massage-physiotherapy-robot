import argparse,csv,json,sys
from pathlib import Path
import cv2,numpy as np
def project(v,K,d):return cv2.projectPoints(v[:,None],np.zeros(3),np.zeros(3),K,d)[0].reshape(-1,2)
def render(rgb,v,f,K,d,color):
 uv=project(v,K,d);tri=v[f];order=np.argsort(tri[:,:,2].mean(1))[::-1];mesh=rgb.copy();h,w=rgb.shape[:2]
 for i in order:
  q=np.rint(uv[f[i]]).astype(np.int32)
  if np.all((q[:,0]<0)|(q[:,0]>=w)|(q[:,1]<0)|(q[:,1]>=h)):continue
  cv2.fillConvexPoly(mesh,q,color,cv2.LINE_AA)
 m=np.any(mesh!=rgb,2);out=rgb.copy();out[m]=(rgb[m]*.2+mesh[m]*.8).astype(np.uint8);return out
def save(path,img):path.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(path),cv2.cvtColor(img,cv2.COLOR_RGB2BGR))
def main():
 p=argparse.ArgumentParser()
 for n in ('config','stage-a','stage-b','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();cfg=json.loads(a.config.read_text());paths=cfg['paths'];sys.path.insert(0,str(Path(paths['v23_code'])));from behave_v2_io import read_camera,transform_between
 stage=json.loads(a.stage_a.read_text());by={x['frame_id']:x for x in stage['rows']};character=json.loads((a.stage_b/'FINAL_CHARACTERIZATION.json').read_text());cases=[]
 for name in ('top_improvements','top_degradations','k0_overfit_cases'):
  z=json.loads((a.stage_b/f'{name}.json').read_text())[:3]
  for x in z:x['category']=name
  cases+=z
 seen=set();cases=[x for x in cases if not ((x['frame_id'],x['method']) in seen or seen.add((x['frame_id'],x['method'])))]
 colors={'O0':(225,70,55),'O1':(55,100,230),'O2':(50,180,80),'O3':(180,80,190),'O4':(245,155,45)}
 for c in cases:
  fid=c['frame_id'];spec=by[fid];assets={g:np.load(spec['methods'][g]['asset']) for g in ('O2','O3','O4')};faces=assets['O2']['faces'];meshes={'O0':assets['O2']['official_vertices'],'O1':assets['O2']['o1_vertices'],**{g:assets[g]['vertices'] for g in ('O2','O3','O4')}};subject,sequence,frame=fid.split('/');root=a.out/'visualizations'/c['category']/f"{subject}__{sequence}__{frame}__{c['method']}";src=Path(paths['sequences'])/sequence/frame;cams=[read_camera(Path(paths['calibs']),sequence,k) for k in range(4)]
  for k in range(4):
   rgb=cv2.cvtColor(cv2.imread(str(src/f'k{k}.color.jpg')),cv2.COLOR_BGR2RGB);panels=[cv2.resize(rgb,(512,384))]
   for m in ('O0','O1','O2','O3','O4'):
    v=meshes[m] if k==0 else transform_between(meshes[m],cams[0],cams[k]);panels.append(cv2.resize(render(rgb,v,faces,cams[k]['K'],cams[k]['dist'],colors[m]),(512,384)))
   save(root/f'K{k}_rgb_O0_O1_O2_O3_O4.png',np.hstack(panels))
  allv=np.vstack(list(meshes.values()));lo,hi=np.percentile(allv,[1,99],axis=0)
  for view,(u,v) in {'front':(0,1),'side':(2,1),'top':(0,2)}.items():
   canvas=np.full((700,700,3),248,np.uint8)
   for m,xyz in meshes.items():
    q=((xyz[:,[u,v]]-lo[[u,v]])/np.maximum(hi[[u,v]]-lo[[u,v]],1e-6)*620+40).astype(int);q[:,1]=699-q[:,1]
    for x,y in q[::8]:
     if 0<=x<700 and 0<=y<700:cv2.circle(canvas,(x,y),1,colors[m],-1)
   save(root/f'{view}.png',canvas)
 param=[]
 for row in stage['rows']:
  for m,z in row['methods'].items():param.append({'frame_id':row['frame_id'],'method':m,**z['changes']})
 with (a.out/'parameter_changes.csv').open('w',newline='') as f:
  fields=['frame_id','method','translation_norm_mm','pose_l2','shape_l2'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:x[k] for k in fields} for x in param)
 comp=character['comparisons'];lines=['# FORMAL RGB-D ORACLE PARAMETER-SPACE STUDY V1','','## Decision',f"**STRUCTURED_PARAMETER_SPACE: {character['decision']}**",'','The study uses BEHAVE dataset person masks and K0 RGB-D for optimization. K1/K2/K3 are held out until Stage A outputs are frozen.','', '## O2/O3/O4 vs O1','', '| Method | Held-out improvement | Absolute delta | Aligned improvement | Subjects improved |','|---|---:|---:|---:|---:|']
 for m in ('O2','O3','O4'):
  x=comp[m];lines.append(f"| {m} | {x['vs_O1_absolute_relative_improvement_pct']:.2f}% | {x['vs_O1_absolute_delta_mm']:+.2f} mm | {x['vs_O1_aligned_relative_improvement_pct']:.2f}% | {x['subjects_improved']}/5 |")
 lines+=['','## Interpretation','','O2 tests translation + pose, O3 tests translation + identity shape and skeletal scale, and O4 tests all three parameter groups. The Oracle result establishes parameter-space utility only; it does not prove unique residual factorization.','','Regional anatomical metrics are NOT_YET_AVAILABLE because no frozen canonical MHR anatomical partition exists. Whole-body and translation-aligned held-out metrics remain the formal evidence.']
 (a.out/'FINAL_REPORT.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
