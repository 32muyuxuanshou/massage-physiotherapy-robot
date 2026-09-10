import argparse, glob, json, os, sys
from pathlib import Path
import numpy as np, torch
p=argparse.ArgumentParser(); p.add_argument('--sam-repo'); p.add_argument('--official'); p.add_argument('--mhr'); p.add_argument('--trainer'); p.add_argument('--paths'); p.add_argument('--out'); a=p.parse_args()
sys.path[:0]=[a.sam_repo,str(Path(a.trainer).parent)]
from sam_3d_body import SAM3DBodyEstimator,load_sam_3d_body
from sam_3d_body.data.utils.prepare_batch import prepare_batch
from sam_3d_body.utils import recursive_to
from train_rgbd_surface import forward_observation
model,cfg=load_sam_3d_body(a.official,device='cuda',mhr_path=a.mhr); model.eval().requires_grad_(False); est=SAM3DBodyEstimator(model,cfg)
out={}
with torch.inference_mode():
 for path in json.loads(Path(a.paths).read_text()):
  pred,_=forward_observation(model,est,prepare_batch,recursive_to,Path(path)); out[Path(path).stem]={'vertices':(pred['pred_vertices']+pred['pred_cam_t'][:,None])[0].cpu(),'cam':pred['pred_cam_t'][0].cpu(),'path':path}
torch.save(out,a.out)
