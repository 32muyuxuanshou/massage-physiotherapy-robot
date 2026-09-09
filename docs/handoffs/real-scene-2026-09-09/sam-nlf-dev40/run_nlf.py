"""Fixed-box, shared-camera NLF inference; no training or Atlas changes."""
import os,json,time,hashlib
from pathlib import Path
import numpy as np
import torch
import torchvision
from PIL import Image

O=Path(__file__).resolve().parent
W=Path('/raid5/xuhd/nlf_pilot_20260908/models/nlf_l_multi_0.3.2.patch4.torchscript')
torch.manual_seed(20260908)
torch.set_grad_enabled(False)
m=torch.jit.load(str(W),map_location='cuda').eval()
print('METHODS',m._c._method_names(),flush=True)
for name in ['get_weights_for_canonical_points','estimate_poses','estimate_smpl_batched','estimate_parametric_batched']:
    if hasattr(m,name): print(str(getattr(m,name).schema),flush=True)
print('BODY_BUFFERS',[(n,tuple(b.shape)) for n,b in m.named_buffers() if 'template' in n or 'face' in n],flush=True)
rows=json.loads((O/'manifest.json').read_text())
if isinstance(rows,dict): rows=rows['samples']
records=[]
fn=m.estimate_parametric_batched if hasattr(m,'estimate_parametric_batched') else m.estimate_smpl_batched
for row in rows:
    ident=row['id']; src=O/'inputs'/f'{ident}.jpg'
    if not src.exists(): src=Path(row['source_remote'])
    rgb=np.asarray(Image.open(src).convert('RGB')).copy()
    h,w=rgb.shape[:2]
    frame=torch.from_numpy(rgb).permute(2,0,1).cuda()
    x1,y1,x2,y2=row['bbox_xyxy']
    box=torch.tensor([[x1,y1,x2-x1,y2-y1]],device='cuda',dtype=torch.float32)
    K=torch.tensor([[[float(np.hypot(w,h)),0,w/2],[0,float(np.hypot(w,h)),h/2],[0,0,1]]],device='cuda')
    start=time.time();torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode(),torch.device('cuda'):
        out=fn(frame[None],[box],intrinsic_matrix=K,internal_batch_size=1,num_aug=1,model_name='smpl')
    torch.cuda.synchronize()
    arrays={k:v[0].detach().cpu().numpy() for k,v in out.items()}
    arrays['K']=K[0].cpu().numpy()
    dest=O/ident;dest.mkdir(exist_ok=True)
    np.savez_compressed(dest/'nlf.npz',**arrays)
    v=arrays['vertices3d'][0];uv=v@arrays['K'].T;uv=uv[:,:2]/uv[:,2:]
    residual=float(np.max(np.linalg.norm(uv-arrays['vertices2d'][0],axis=1)))
    rec=dict(id=ident,seconds=time.time()-start,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
             vertex_count=len(v),projection_self_check_max_px=residual,output_shapes={k:list(a.shape) for k,a in arrays.items()})
    records.append(rec)
    (O/'nlf_results.json').write_text(json.dumps(records,indent=2))
    print('DONE',rec,flush=True)
(O/'nlf_run_metadata.json').write_text(json.dumps(dict(checkpoint=str(W),sha256=hashlib.sha256(W.read_bytes()).hexdigest(),
    torch=torch.__version__,torchvision=torchvision.__version__,device=torch.cuda.get_device_name(),
    seed=20260908,bbox='xywh converted from original xyxy',camera='shared hypot focal centered K',
    output_units='vertices3d/joints3d millimeters; trans meters; image pixels',count=len(records)),indent=2))
print('COMPLETE',len(records),flush=True)
