"""One frozen Coarse/visibility context per image/parent seed, never using B."""
import argparse,json,time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from core import BASE,WORK,OLD,G,sha,load_parent,FineOnly
from frozen_render_losses import MeshRenderer


def main(seed,domains):
    torch.set_num_threads(2);started=time.monotonic()
    manifest=json.loads((WORK/'DATA_MANIFEST.json').read_text());rows=[]
    for domain in [d for d in ['native','scan'] if d in domains]:
        source=manifest[domain];counts=Counter((r.get('asset_id'),r.get('view',{}).get('group')) for r in source)
        # Match original camera-group weights computed on the original full role manifest.
        original=json.loads((WORK/(domain.upper()+'_SOURCE_MANIFEST.json')).read_text())['records']
        if domain=='scan':
            groups=Counter((r['asset_id'],r['view']['group']) for r in original);totals=Counter(r['asset_id'] for r in original)
            number={asset:sum(k[0]==asset for k in groups) for asset in totals}
        for r in source:
            row=dict(domain=domain,key=Path(r['cache_file']).stem,identity=r['identity'],role=r['role'],cache_file=r['cache_file'],source=str(WORK/'cache'/domain/r['cache_file']))
            if domain=='scan':row.update(asset_id=r['asset_id'],camera_group=r['view']['group'],surface_weight=totals[r['asset_id']]/(number[r['asset_id']]*groups[r['asset_id'],r['view']['group']]))
            rows.append(row)
    tasks=json.loads((G/'MANIFEST.json').read_text())['tasks']
    for t in tasks:
        if t['seed']==seed and t['dataset'] in domains and t['dataset'] in ['real','behave']:
            domain=t['dataset'];sub='humman_development_v1' if domain=='real' else 'behave/s%d'%seed
            rows.append(dict(domain=domain,key=t['key'],identity=t['identity'],role=t['role'],source=str(OLD/'cache'/sub/(t['key']+'.pt'))))
    faces=torch.from_numpy(np.load(G/'assets/faces.npy')).cuda();renderer=MeshRenderer(faces)
    full=load_parent(seed,renderer);fine=FineOnly(full);captures={}
    hook=full.local.register_forward_pre_hook(lambda module,args:captures.update(input=args[0].detach()))
    out=WORK/'prepared'/('s%d'%seed);out.mkdir(parents=True,exist_ok=True);records=[]
    with torch.no_grad():
        for i,r in enumerate(rows):
            p=Path(r['source']);rec=torch.load(p,map_location='cpu',weights_only=False)
            b={k:rec['batch'][k].cuda() for k in ['cam_int','ori_img_size','bbox_scale','affine_trans']}
            official={k:rec['official'][k].cuda() for k in ['pred_vertices','pred_cam_t']}
            feature,depth,valid,rays=[rec[k].cuda() for k in ['backbone','depth','valid','rays']]
            camera,tr=full(feature,depth,valid,rays,official,b);captured=captures['input'];geometry=captured[:,:,64:]
            rgb=F.grid_sample(feature.float(),geometry[:,:,15:17][:,:,None],align_corners=True)[:,:,:,0].transpose(1,2)
            x=dict(rgb_queries=rgb,geometry=geometry,coarse=tr['coarse_camera'])
            replay,delta=fine(x);error=float((camera-replay).abs().max());assert error<.0001,error
            values={k:v[0].cpu().numpy() for k,v in x.items()}
            values.update(body=official['pred_vertices'][0].float().cpu().numpy(),initial_camera=camera[0].cpu().numpy(),
                target_depth=rec.get('target_depth',torch.empty((1,0,0)))[0].float().numpy(),
                target_mask=rec.get('target_mask',torch.empty((1,0,0)))[0].bool().numpy(),
                K=rec.get('K',rec['batch']['cam_int'])[0].float().numpy())
            if r['domain']=='native':values.update(gt_camera=rec['truth']['pred_cam_t'][0].float().numpy(),gt_body=rec['truth']['pred_vertices'][0].float().numpy())
            dest=out/r['domain']/(r['key']+'.npz');dest.parent.mkdir(exist_ok=True)
            np.savez_compressed(dest,**values)
            records.append(dict(r,source_sha256=sha(p),prepared_sha256=sha(dest),fine_equivalence_max_m=error))
            if (i+1)%100==0:print('PREPARED',seed,i+1,len(rows),round(time.monotonic()-started,1),flush=True)
        hook.remove()
    part=dict(status='COMPLETE',seed=seed,records=records,seconds=time.monotonic()-started,body_coarse_queries_immutable=True,Camera_B_input=False)
    (out/('MANIFEST_'+ '_'.join(domains)+'.json')).write_text(json.dumps(part,indent=2))
    merged={}
    for p in sorted(out.glob('MANIFEST_*.json')):
        for r in json.loads(p.read_text())['records']:merged[r['domain'],r['key']]=r
    (out/'MANIFEST.json').write_text(json.dumps(dict(part,records=list(merged.values()),status='COMPLETE' if len(merged)==2950 else 'PARTIAL'),indent=2))
    print('PREPARED_COMPLETE',seed,len(records),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--domains',default='native,scan,real,behave');a=p.parse_args();main(a.seed,a.domains.split(','))
