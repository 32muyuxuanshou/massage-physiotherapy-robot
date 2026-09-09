import json,time,hashlib,argparse
from pathlib import Path
import numpy as np
import torch,torchvision
from PIL import Image
O=Path(__file__).resolve().parent;BASE=O.parent/'dev40'
parser=argparse.ArgumentParser();parser.add_argument('--anchors',action='store_true');args=parser.parse_args()
W=O.parent/'models/nlf_l_multi_0.3.2.patch4.torchscript'
torch.manual_seed(20260908);torch.set_grad_enabled(False)
m=torch.jit.load(str(W),map_location='cuda').eval()
print(m.estimate_poses.schema,flush=True)
points=torch.from_numpy(np.load(O/'query_canonical.npy')).cuda()
if args.anchors:
    anchors=m.cano_all['smpl']
    print('ANCHORS',anchors.shape,flush=True)
    points=torch.cat([points,anchors],dim=0)
with torch.inference_mode(),torch.device('cuda'): weights=m.get_weights_for_canonical_points(points)
rows=[r for r in json.loads((BASE/'manifest.json').read_text()) if r['id'] in ['B1','B2','B3','B4','B5','N1']]
stats=[]
for r in rows:
    src=BASE/r['input_relative'];assert hashlib.sha256(src.read_bytes()).hexdigest()==r['sha256']
    im=torch.from_numpy(np.asarray(Image.open(src).convert('RGB')).copy()).permute(2,0,1).cuda()
    x,y,x2,y2=r['bbox_xyxy'];box=torch.tensor([[x,y,x2-x,y2-y]],dtype=torch.float32,device='cuda')
    K=torch.tensor(r['K'],dtype=torch.float32,device='cuda');start=time.time()
    with torch.inference_mode(),torch.device('cuda'):
        out=m.estimate_poses(im,box,weights,intrinsic_matrix=K,num_aug=1,internal_batch_size=1)
    torch.cuda.synchronize()
    d={k:v.detach().cpu().numpy() for k,v in out.items()}
    folder=O/r['id'];folder.mkdir(exist_ok=True);np.savez_compressed(folder/('query_anchored.npz' if args.anchors else 'query.npz'),**d,K=K.cpu().numpy())
    rec=dict(id=r['id'],seconds=time.time()-start,shapes={k:list(v.shape) for k,v in d.items()})
    stats.append(rec);(O/('run_anchored_results.json' if args.anchors else 'run_results.json')).write_text(json.dumps(stats,indent=2));print('DONE',rec,flush=True)
print('COMPLETE',len(stats),flush=True)
