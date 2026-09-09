import os
os.environ['PYOPENGL_PLATFORM']='egl'
import sys,json,time,hashlib
from pathlib import Path
import numpy as np
import torch
from PIL import Image
O=Path(__file__).resolve().parent
P=Path('/raid5/xuhd/sam3d_s01_pilot_20260906')
sys.path.insert(0,str(P/'sam-3d-body'))
from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
torch.manual_seed(20260908)
model,cfg=load_sam_3d_body(str(P/'weights/model.ckpt'),device='cuda',mhr_path=str(P/'weights/assets/mhr_model.pt'))
est=SAM3DBodyEstimator(model,cfg)
np.save(O/'sam_faces.npy',est.faces)
records=[]
for row in json.loads((O/'manifest.json').read_text()):
    ident=row['id'];src=O/row['input_relative']
    assert hashlib.sha256(src.read_bytes()).hexdigest()==row['sha256']
    rgb=np.asarray(Image.open(src).convert('RGB')).copy();K=np.asarray(row['K'],np.float32)
    start=time.time();torch.cuda.reset_peak_memory_stats()
    pred=est.process_one_image(rgb,bboxes=np.asarray([row['bbox_xyxy']],np.float32),
        cam_int=torch.from_numpy(K[None]),inference_type='body')[0]
    pred={k:np.asarray(v) for k,v in pred.items() if v is not None}
    v=pred['pred_vertices']+pred['pred_cam_t'];p=v@K.T;uv=p[:,:2]/p[:,2:]
    dest=O/ident;dest.mkdir(exist_ok=True)
    np.savez_compressed(dest/'sam.npz',**pred,vertices_camera=v,uv=uv,K=K)
    rec=dict(id=ident,seconds=time.time()-start,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30)
    records.append(rec);(O/'sam_results.json').write_text(json.dumps(records,indent=2))
    print('DONE',rec,flush=True)
print('COMPLETE',len(records),flush=True)
