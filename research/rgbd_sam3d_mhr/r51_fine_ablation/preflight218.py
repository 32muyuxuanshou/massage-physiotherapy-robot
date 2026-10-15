"""Main-path equivalence, immutable context and TRAIN-only L2 calibration."""
import json,time
import numpy as np
import torch
from torch.nn import functional as F
from core import WORK,CFG,G,FineOnly,load_parent,batch,objective,sha,evaluate
from train218 import rank,selected_rows
from frozen_render_losses import MeshRenderer


def main():
    torch.set_num_threads(2);faces=torch.from_numpy(np.load(G/'assets/faces.npy')).cuda();renderer=MeshRenderer(faces)
    checks=[]
    for seed in CFG['seeds']:
        parent=load_parent(seed,renderer);model=FineOnly(parent);rr=selected_rows(seed)
        for domain in ['native','scan']:
            row=next(r for r in rr if r['domain']==domain and r['role']=='TRAIN')
            rec=torch.load(row['source'],map_location='cpu',weights_only=False)
            tensors=[rec[k].cuda() for k in ['backbone','depth','valid','rays']]
            official={k:rec['official'][k].cuda() for k in ['pred_vertices','pred_cam_t']}
            b={k:rec['batch'][k].cuda() for k in ['cam_int','ori_img_size','bbox_scale','affine_trans']}
            camera,_=parent(*tensors,official,b);params=list(model.parameters())
            old_grads=torch.autograd.grad(camera.square().sum(),params)
            x=batch([row],seed);new,_=model(x);new_grads=torch.autograd.grad(new.square().sum(),params)
            max_camera=float((camera-new).abs().max());max_grad=max(float((a-b).abs().max()) for a,b in zip(old_grads,new_grads))
            assert max_camera<1e-4 and max_grad<1e-3,(max_camera,max_grad)
            assert all(not p.requires_grad for p in parent.coarse.parameters())
            loss,weighted,terms,c,delta=objective(model,renderer,x,domain,CFG['arms']['E0'])
            expected=(2*terms['camera']+.2*terms['z']+.2*terms['sil']) if domain=='native' else (CFG['scan_depth_weight']*terms['z']+CFG['scan_silhouette_weight']*terms['sil'])
            assert float((loss-expected).abs())<1e-7
            checks.append(dict(seed=seed,domain=domain,camera_equivalence_max_m=max_camera,parameter_gradient_max_abs=max_grad,E0_math_equal=True))
        torch.optim.AdamW(model.parameters(),lr=1e-4).zero_grad()
        x=batch([r for r in rr if r['domain']=='native' and r['role']=='TRAIN'][:2],seed)
        loss,*_=objective(model,renderer,x,'native',CFG['arms']['E0']);loss.backward()
        assert model.fine_head[-1].weight.grad.abs().sum()>0
        optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4);optimizer.step()
        assert all(p.grad is None for p in parent.coarse.parameters())
    # Independent untouched parent for calibration, never the preflight-updated model.
    seed=11;parent=load_parent(seed,renderer);model=FineOnly(parent);rr=selected_rows(seed)
    calibration=[];params=list(model.fine_head[-1].parameters())
    for domain in ['native','scan']:
        selected=sorted([r for r in rr if r['domain']==domain and r['role']=='TRAIN'],key=rank)[:32]
        for row in selected:
            x=batch([row],seed);value,weighted,terms,_,_=objective(model,renderer,x,domain,CFG['arms']['E0'])
            base_grad=torch.autograd.grad(value,params,retain_graph=True);reg_grad=torch.autograd.grad(terms['l2'],params)
            calibration.append(dict(key=row['key'],domain=domain,base_norm=float(torch.cat([v.flatten() for v in base_grad]).norm()),l2_norm=float(torch.cat([v.flatten() for v in reg_grad]).norm())))
    base=float(np.median([r['base_norm'] for r in calibration]));reg=float(np.median([r['l2_norm'] for r in calibration]));assert reg>0
    lam=.1*base/reg
    (WORK/'L2_CALIBRATION.json').write_text(json.dumps(dict(lambda_value=lam,**{'lambda':lam},records=calibration,target_gradient_ratio=.1,seed=11,VAL_read=False,Camera_B_read=False),indent=2))
    (WORK/'PREFLIGHT.json').write_text(json.dumps(dict(status='PASS',checks=checks,optimizer_step=True,coarse_grad_none=True,config_sha256=sha(WORK/'EXPERIMENT.json'),l2_lambda=lam),indent=2))
    print('PREFLIGHT_PASS',lam,flush=True)


if __name__=='__main__':main()
