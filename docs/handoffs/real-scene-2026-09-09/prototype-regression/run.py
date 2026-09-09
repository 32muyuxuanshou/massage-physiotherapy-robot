import os
os.environ['PYOPENGL_PLATFORM']='egl'
import sys,json,time,hashlib
from pathlib import Path
import numpy as np
import torch
from PIL import Image
O=Path(__file__).resolve().parent;D=O.parent/'dev40';P=Path('/raid5/xuhd/sam3d_s01_pilot_20260906')
sys.path.insert(0,str(P/'sam-3d-body'))
from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
torch.manual_seed(20260908)
w=O.parent/'finetune_prototype/prototype_heads.pt'
assert hashlib.sha256(w.read_bytes()).hexdigest()=='56b3a222a9c8190d83587b3df3d218d155f9e9a9e0ca410438ee087ef3d328ca'
ckpt=torch.load(w,map_location='cpu',weights_only=False)
assert hashlib.sha256((P/'weights/model.ckpt').read_bytes()).hexdigest()==ckpt['base_checkpoint_sha256']
model,cfg=load_sam_3d_body(str(P/'weights/model.ckpt'),device='cuda',mhr_path=str(P/'weights/assets/mhr_model.pt'))
model.head_pose.proj.load_state_dict(ckpt['heads']['pose'],strict=True);model.head_camera.proj.load_state_dict(ckpt['heads']['camera'],strict=True)
model.eval();model.requires_grad_(False);est=SAM3DBodyEstimator(model,cfg)
records=[]
for row in json.loads((O/'manifest.json').read_text()):
    src=D/row['input_relative'];assert hashlib.sha256(src.read_bytes()).hexdigest()==row['sha256']
    rgb=np.asarray(Image.open(src).convert('RGB')).copy();K=np.array(row['K'],np.float32);t=time.time()
    p=est.process_one_image(rgb,bboxes=np.asarray([row['bbox_xyxy']],np.float32),cam_int=torch.from_numpy(K[None]),inference_type='body')[0]
    p={k:np.asarray(v) for k,v in p.items() if v is not None};v=p['pred_vertices']+p['pred_cam_t'];assert np.isfinite(v).all() and (v[:,2]>0).all()
    dest=O/row['id'];dest.mkdir(exist_ok=True);np.savez_compressed(dest/'adapted.npz',**p,vertices_camera=v,K=K)
    records.append(dict(id=row['id'],role=row['regression_role'],seconds=time.time()-t));(O/'run_results.json').write_text(json.dumps(records,indent=2));print('DONE',records[-1],flush=True)
print('COMPLETE',len(records),flush=True)
