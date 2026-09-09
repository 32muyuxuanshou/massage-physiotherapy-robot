import os
os.environ['PYOPENGL_PLATFORM']='egl'
import json,sys,time,hashlib,math
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
O=Path(__file__).resolve().parent; D=O.parent/'scaleup_mhr'; P=Path('/raid5/xuhd/sam3d_s01_pilot_20260906')
sys.path.insert(0,str(P/'sam-3d-body'))
from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
from sam_3d_body.data.utils.prepare_batch import prepare_batch
from sam_3d_body.utils import recursive_to
from sam_3d_body.metadata import MHR70_TO_OPENPOSE,OPENPOSE_TO_COCO
mapping=[MHR70_TO_OPENPOSE[i] for i in OPENPOSE_TO_COCO][5:17]
protocol=json.loads((D/'protocol.json').read_text()); rows=json.loads((D/'samples.json').read_text())
train=[r for r in rows if r['split']=='train']; val=[r for r in rows if r['split']=='validation']
assert set(r['source_sha256'] for r in train).isdisjoint(r['source_sha256'] for r in val)
torch.manual_seed(protocol['seed']); np.random.seed(protocol['seed'])
model,cfg=load_sam_3d_body(str(P/'weights/model.ckpt'),device='cuda',mhr_path=str(P/'weights/assets/mhr_model.pt'))
model.eval(); model.requires_grad_(False)
heads={'pose':model.head_pose.proj,'camera':model.head_camera.proj}
for h in heads.values():h.requires_grad_(True)
params=[p for p in model.parameters() if p.requires_grad]
est=SAM3DBodyEstimator(model,cfg); pelvis=model.pelvis_idx
images=Path('/raid5/xuhd/datasets/coco2014_person_seed20260908/images/train2014')
verified=set()
def forward(r):
 src=images/r['image']
 if str(src) not in verified:
  assert hashlib.sha256(src.read_bytes()).hexdigest()==r['source_sha256'];verified.add(str(src))
 rgb=np.asarray(Image.open(src).convert('RGB')).copy()
 batch=prepare_batch(rgb,est.transform,np.asarray([r['bbox']],np.float32),None,None)
 batch=recursive_to(batch,'cuda');batch['cam_int']=torch.tensor([r['cam_int']],device='cuda').to(batch['img'])
 model._initialize_batch(batch)
 return model.forward_step(batch,decoder_type='body')['mhr']
def loss_for(out,r):
 p2=out['pred_keypoints_2d'];p3=out['pred_keypoints_3d']
 t2=p2.new_tensor(r['keypoints_2d'])[None,:,:2]
 t3=p3.new_tensor(r['keypoints_3d'])[None,:,:3]
 t3=(t3+p3.new_tensor(r['model_params'][:3])/10)*p3.new_tensor([1,-1,-1])
 size=p2.new_tensor(r['original_hw'][::-1])
 return F.smooth_l1_loss(p2/size,t2/size)+F.smooth_l1_loss(p3-p3[:,pelvis].mean(1,keepdim=True),t3-t3[:,pelvis].mean(1,keepdim=True))
def evaluate(tag):
 metrics=[]
 with torch.no_grad():
  for i,r in enumerate(val):
   out=forward(r); a=r['coco_annotation'];ref=np.array(a['keypoints']).reshape(17,3)[5:17];valid=ref[:,2]>0
   pred=out['pred_keypoints_2d'][0].float().cpu().numpy()[mapping]
   dist=np.linalg.norm(pred[valid]-ref[valid,:2],axis=1)/math.sqrt(a['bbox'][2]*a['bbox'][3])
   metrics.append(dict(id=r['id'],image=r['image'],fitted_loss=float(loss_for(out,r)),nme=float(dist.mean()),pck05=float((dist<.05).mean())))
   if (i+1)%20==0:print(tag,'validation',i+1,len(val),flush=True)
 groups={}
 for r in metrics:groups.setdefault(r['image'],[]).append(r)
 agg={k:float(np.mean([np.mean([r[k] for r in rr]) for rr in groups.values()])) for k in ['fitted_loss','nme','pck05']}
 result=dict(tag=tag,images=len(groups),people=len(metrics),image_macro=agg,rows=metrics)
 (O/(tag+'.json')).write_text(json.dumps(result,indent=2));print(tag,agg,flush=True);return agg

import cv2,trimesh,pyrender
faces=np.asarray(est.faces)
initial={k:{n:t.detach().cpu().clone() for n,t in h.state_dict().items()} for k,h in heads.items()}
metrics=[]
for tag,epoch in [('baseline',0),('epoch2',2),('epoch10',10)]:
 if epoch:
  ck=torch.load(D/f'heads_epoch{epoch}.pt',map_location='cpu',weights_only=False)
  assert ck['manifest_sha256']==hashlib.sha256((D/'samples.json').read_bytes()).hexdigest()
  for k,h in heads.items():h.load_state_dict(ck['heads'][k])
 for j,r in enumerate(val):
  with torch.no_grad():out=forward(r)
  v=(out['pred_vertices'][0]+out['pred_cam_t'][0]).cpu().numpy()
  kp=out['pred_keypoints_2d'][0].cpu().numpy()
  dest=O/r['id'];dest.mkdir(exist_ok=True)
  np.savez_compressed(dest/(tag+'.npz'),vertices_camera=v,keypoints_2d=kp)
  a=r['coco_annotation'];ref=np.array(a['keypoints']).reshape(17,3)[5:17];valid=ref[:,2]>0
  dd=np.linalg.norm(kp[mapping][valid]-ref[valid,:2],axis=1)/math.sqrt(a['bbox'][2]*a['bbox'][3])
  metrics.append(dict(id=r['id'],image=r['image'],tag=tag,nme=float(dd.mean()),pck05=float((dd<.05).mean()),tags=r['tags']))
  rgb=np.asarray(Image.open(images/r['image']).convert('RGB'));h,w=rgb.shape[:2];sc=min(640/w,520/h,1);ww,hh=round(w*sc),round(h*sc)
  im=cv2.resize(rgb,(ww,hh));K=np.array(r['cam_int']).copy();K[0]*=ww/w;K[1]*=hh/h
  mesh=trimesh.Trimesh(v*np.array([1,-1,-1]),faces,process=False)
  scene=pyrender.Scene(bg_color=[0,0,0,0],ambient_light=[.65,.65,.65])
  scene.add(pyrender.Mesh.from_trimesh(mesh,material=pyrender.MetallicRoughnessMaterial(baseColorFactor=(.3,.75,1.,1.),metallicFactor=0.,roughnessFactor=.8)))
  scene.add(pyrender.IntrinsicsCamera(K[0,0],K[1,1],K[0,2],K[1,2]),pose=np.eye(4))
  scene.add(pyrender.DirectionalLight(color=np.ones(3),intensity=2),pose=np.eye(4))
  renderer=pyrender.OffscreenRenderer(ww,hh);color,depth=renderer.render(scene);renderer.delete()
  mask=depth>0;im[mask]=(.5*im[mask]+.5*color[mask]).astype(np.uint8)
  im=cv2.copyMakeBorder(im,30,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25));cv2.putText(im,f'{tag} NME {dd.mean():.4f}',(5,21),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
  Image.fromarray(im).save(dest/(tag+'.jpg'),quality=90)
  if j%10==0:print(tag,j+1,len(val),flush=True)
(O/'metrics.json').write_text(json.dumps(metrics,indent=2))
for r in val:
 dest=O/r['id']; panels=[Image.open(dest/(t+'.jpg')) for t in ['baseline','epoch2','epoch10']]
 board=Image.new('RGB',(sum(im.width for im in panels),panels[0].height));x=0
 for im in panels:board.paste(im,(x,0));x+=im.width
 board.save(dest/'comparison.jpg',quality=90)
print('COMPLETE',len(val),'people',len(set(r['image'] for r in val)),'images',flush=True)
