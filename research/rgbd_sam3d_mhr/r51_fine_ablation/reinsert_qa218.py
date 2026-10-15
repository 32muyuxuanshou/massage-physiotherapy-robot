"""Put learned Fine weights back into original Coarse+Fine, cached backbone only."""
import json
import numpy as np
import torch
from core import WORK,G,CFG,FineOnly,load_parent,batch
from train218 import selected_rows
from frozen_render_losses import MeshRenderer


def main():
    torch.set_num_threads(2);renderer=MeshRenderer(torch.from_numpy(np.load(G/'assets/faces.npy')).cuda());checks=[]
    with torch.no_grad():
        for seed in CFG['seeds']:
            rows=selected_rows(seed)
            for arm in CFG['arms']:
                parent=load_parent(seed,renderer);fine=FineOnly(parent)
                learned=torch.load(WORK/'runs'/('%s_s%d'%(arm,seed))/'epoch_06.pt',map_location='cpu',weights_only=False)
                fine.load_state_dict(learned['model'])
                for domain in ['native','scan','real','behave']:
                    row=next(r for r in rows if r['domain']==domain)
                    rec=torch.load(row['source'],map_location='cpu',weights_only=False)
                    feature,depth,valid,rays=[rec[k].cuda() for k in ['backbone','depth','valid','rays']]
                    official={k:rec['official'][k].cuda() for k in ['pred_vertices','pred_cam_t']}
                    before=official['pred_vertices'].clone()
                    b={k:rec['batch'][k].cuda() for k in ['cam_int','ori_img_size','bbox_scale','affine_trans']}
                    actual,tr=parent(feature,depth,valid,rays,official,b);cached,_=fine(batch([row],seed))
                    difference=float((actual-cached).abs().max());coarse=float((tr['coarse_camera']-batch([row],seed)['coarse']).abs().max())
                    assert difference<.0001 and coarse<.000001,(arm,seed,domain,difference,coarse)
                    assert torch.equal(before,official['pred_vertices'])
                    checks.append(dict(arm=arm,seed=seed,domain=domain,key=row['key'],camera_max_difference_m=difference,coarse_max_difference_m=coarse,body_exact_unchanged=True))
    (WORK/'FULL_FORWARD_REINSERTION_QA.json').write_text(json.dumps(dict(status='PASS',checks=checks,scope='Original learned Coarse+Fine on cached backbone features; not raw RGB Backbone/Decoder end-to-end benchmark'),indent=2))
    print('REINSERTION_QA_PASS',len(checks),flush=True)


if __name__=='__main__':main()
