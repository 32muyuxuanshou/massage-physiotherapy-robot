"""Fixed pre-inference protocol: 6 dev photos x original/padded/cropped, no training."""
import argparse,json,time,sys,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
import torch
import torchvision

O=Path(__file__).resolve().parent;D=O.parent/'dev40'
args=argparse.ArgumentParser();args.add_argument('model',choices=['sam','nlf']);args=args.parse_args()
torch.manual_seed(20260908);torch.set_grad_enabled(False)
if args.model=='sam':
    P=Path('/raid5/xuhd/sam3d_s01_pilot_20260906')
    sys.path.insert(0,str(P/'sam-3d-body'))
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    model,cfg=load_sam_3d_body(str(P/'weights/model.ckpt'),device='cuda',mhr_path=str(P/'weights/assets/mhr_model.pt'))
    est=SAM3DBodyEstimator(model,cfg)
    b=json.loads((O/'native_binding.json').read_text())
else:
    model=torch.jit.load(str(O.parent/'models/nlf_l_multi_0.3.2.patch4.torchscript'),map_location='cuda').eval()
    q=torch.from_numpy(np.load(O.parent/'atlas_query/query_canonical.npy')).cuda()
    with torch.inference_mode(),torch.device('cuda'):
        weights=model.get_weights_for_canonical_points(torch.cat([q,model.cano_all['smpl']],0))
    b=json.loads((O/'binding.json').read_text())
idx=np.array([p['vertex_indices'] for p in b['points']]);bc=np.array([p['barycentric'] for p in b['points']])
records=[]
for row in json.loads((D/'manifest.json').read_text()):
    if row['id'] not in ['B1','B2','B3','B4','B5','N1']:continue
    src=D/row['input_relative'];assert hashlib.sha256(src.read_bytes()).hexdigest()==row['sha256']
    im=np.asarray(Image.open(src).convert('RGB')).copy();h,w=im.shape[:2]
    box=np.array(row['bbox_xyxy'],dtype=np.float32);K=np.array(row['K'],dtype=np.float32)
    dx=int(round(.4*w));dy=int(round(.15*h))
    pad=np.full((h+2*dy,w+dx+int(round(.1*w)),3),127,np.uint8);pad[dy:dy+h,dx:dx+w]=im
    bw,bh=box[2:]-box[:2]
    left=max(0,int(np.floor(box[0]-.1*bw)));top=max(0,int(np.floor(box[1]-.1*bh)))
    right=min(w,int(np.ceil(box[2]+.1*bw)));bottom=min(h,int(np.ceil(box[3]+.1*bh)))
    for variant,rgb,tx,ty in [('original',im,0,0),('pad_shift',pad,dx,dy),('crop',im[top:bottom,left:right].copy(),-left,-top)]:
        A=np.array([[1,0,tx],[0,1,ty],[0,0,1]],np.float32);kv=A@K;bv=box+np.array([tx,ty,tx,ty],np.float32)
        t=time.time()
        if args.model=='sam':
            out=est.process_one_image(rgb,bboxes=bv[None],cam_int=torch.from_numpy(kv[None]),inference_type='body')[0]
            verts=np.asarray(out['pred_vertices'])+np.asarray(out['pred_cam_t'])
            xyz=(verts[idx]*bc[...,None]).sum(1)*1000
        else:
            frame=torch.from_numpy(rgb).permute(2,0,1).cuda();x,y,x2,y2=bv
            bbox=torch.tensor([[x,y,x2-x,y2-y]],dtype=torch.float32,device='cuda')
            with torch.inference_mode(),torch.device('cuda'):
                out=model.estimate_poses(frame,bbox,weights,intrinsic_matrix=torch.from_numpy(kv).cuda(),num_aug=1,internal_batch_size=1)
            xyz=out['poses3d'][0,:37].cpu().numpy()
        assert xyz.shape==(37,3) and np.isfinite(xyz).all() and (xyz[:,2]>0).all()
        uv=xyz@kv.T;uv=uv[:,:2]/uv[:,2:];original_uv=uv-np.array([tx,ty])
        dest=O/row['id']/variant;dest.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(dest/(args.model+'.npz'),xyz_mm=xyz,uv=uv,original_uv=original_uv,K=kv,A=A)
        rec=dict(id=row['id'],variant=variant,model=args.model,seconds=time.time()-t,shape=list(rgb.shape),A=A.tolist(),K=kv.tolist(),bbox=bv.tolist())
        records.append(rec);(O/(args.model+'_results.json')).write_text(json.dumps(records,indent=2));print('DONE',rec,flush=True)
print('COMPLETE',len(records),flush=True)
