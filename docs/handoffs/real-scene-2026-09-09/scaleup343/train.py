import os
os.environ['PYOPENGL_PLATFORM']='egl'
import json,sys,time,hashlib,math
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
O=Path(__file__).resolve().parent; P=Path('/raid5/xuhd/sam3d_s01_pilot_20260906')
sys.path.insert(0,str(P/'sam-3d-body'))
from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
from sam_3d_body.data.utils.prepare_batch import prepare_batch
from sam_3d_body.utils import recursive_to
from sam_3d_body.metadata import MHR70_TO_OPENPOSE,OPENPOSE_TO_COCO
mapping=[MHR70_TO_OPENPOSE[i] for i in OPENPOSE_TO_COCO][5:17]
protocol=json.loads((O/'protocol.json').read_text()); rows=json.loads((O/'samples.json').read_text())
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
start=time.time(); baseline=evaluate('baseline'); opt=torch.optim.AdamW(params,lr=protocol['lr'],weight_decay=protocol['weight_decay'])
history=[]; rng=np.random.default_rng(protocol['seed']); updates=0
for epoch in range(protocol['epochs']):
 order=rng.permutation(len(train)); losses=[]
 for startidx in range(0,len(order),protocol['accumulation']):
  chunk=order[startidx:startidx+protocol['accumulation']];opt.zero_grad(set_to_none=True)
  for idx in chunk:
   r=train[int(idx)];out=forward(r);loss=loss_for(out,r);assert torch.isfinite(loss)
   (loss/len(chunk)).backward();losses.append(float(loss.detach()))
  norm=torch.nn.utils.clip_grad_norm_(params,1.,error_if_nonfinite=True);opt.step();updates+=1
  if updates%5==0:print('epoch',epoch+1,'exposures',min(startidx+len(chunk),len(train)),'updates',updates,'loss',np.mean(losses[-40:]),flush=True)
 metric=evaluate('epoch'+str(epoch+1));history.append(dict(epoch=epoch+1,updates=updates,train_loss=float(np.mean(losses)),validation=metric))
 torch.save(dict(heads={k:h.state_dict() for k,h in heads.items()},optimizer=opt.state_dict(),epoch=epoch+1,protocol=protocol,manifest_sha256=hashlib.sha256((O/'samples.json').read_bytes()).hexdigest()),O/('heads_epoch'+str(epoch+1)+'.pt'))
 (O/'history.json').write_text(json.dumps(history,indent=2))
report=dict(status='COMPLETED',baseline=baseline,history=history,updates=updates,training_exposures=len(train)*protocol['epochs'],trainable_parameters=sum(p.numel() for p in params),elapsed_seconds=time.time()-start,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,interpretation='COCO source fine-tuning holdout; no independent 3D surface or acupoint truth')
(O/'report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report),flush=True)
