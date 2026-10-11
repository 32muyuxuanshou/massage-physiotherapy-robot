"""Shared TRAIN/VAL spatial caches and deterministic sensor-sampling controls."""
import hashlib,json
from collections import Counter
from pathlib import Path
from functools import lru_cache
import torch


@lru_cache(maxsize=12)
def read(path):
    return torch.load(path,map_location='cpu',weights_only=False)


def augment_depth(rec,seed,epoch):
    # Controlled zero-baseline sensor lattice in original RGB pixel coordinates.
    # It changes sampling/noise, never the camera K/rays or clean surface target.
    key=f"{seed}:{epoch}:{rec['sample']}"
    digest=int(hashlib.sha256(key.encode()).hexdigest()[:12],16)
    generator=torch.Generator().manual_seed(digest)
    depth=rec['depth'].clone();valid=rec['valid'].clone()
    profile=digest%3
    if profile:
        K=rec['batch']['cam_int'].reshape(-1,3,3)[0].float()
        ray=rec['rays'][0].float()
        u=(ray[0]*K[0,0]+K[0,2]).round().long()
        v=(ray[1]*K[1,1]+K[1,2]).round().long()
        stride=2 if profile==1 else 3
        phase_x=(digest//3)%stride;phase_y=(digest//9)%stride
        keep=((u%stride)==phase_x)&((v%stride)==phase_y)
        valid &= keep[None,None]
    holes=torch.rand(depth.shape,generator=generator)<.02
    valid &= ~holes
    sigma=(0.,.001,.003)[(digest//27)%3]
    depth=torch.where(valid,depth+torch.randn(depth.shape,generator=generator)*sigma,0)
    valid &= torch.isfinite(depth)&(depth>.05)
    return torch.where(valid,depth,0),valid


def rows(cache,domain):
    manifest=json.loads((Path(cache)/'CACHE_MANIFEST.json').read_text())
    assert all(r['role'] in ['TRAIN','VAL'] for r in manifest['records'])
    result=[dict(r,domain=domain,path=str(Path(cache)/r['cache_file'])) for r in manifest['records']]
    if domain=='scan':
        groups=Counter((r['asset_id'],r['view']['group']) for r in result)
        totals=Counter(r['asset_id'] for r in result)
        number={asset:sum(key[0]==asset for key in groups) for asset in totals}
        for r in result:
            r['surface_weight']=totals[r['asset_id']]/(number[r['asset_id']]*groups[r['asset_id'],r['view']['group']])
    return result


def batch(records,device='cuda',seed=None,epoch=None):
    values=[read(r['path']) for r in records]
    b={k:torch.cat([v['batch'][k] for v in values]).to(device) for k in values[0]['batch']}
    official={k:torch.cat([v['official'][k] for v in values]).to(device) for k in values[0]['official']}
    truth={k:torch.cat([v['truth'][k] for v in values]).to(device) for k in values[0].get('truth',{})}
    if seed is None:
        pairs=[(v['depth'],v['valid']) for v in values]
    else:
        pairs=[augment_depth(v,seed,epoch) for v in values]
    return dict(batch=b,surface_weight=torch.tensor([r.get('surface_weight',1.) for r in records],device=device),
        feature=torch.cat([v['backbone'] for v in values]).to(device),
        depth=torch.cat([p[0] for p in pairs]).to(device),valid=torch.cat([p[1] for p in pairs]).to(device),
        rays=torch.cat([v['rays'] for v in values]).to(device),official=official,truth=truth,
        target_depth=torch.cat([v['target_depth'] for v in values]).to(device) if 'target_depth' in values[0] else None,
        target_mask=torch.cat([v['target_mask'] for v in values]).to(device) if 'target_mask' in values[0] else None,
        K=torch.cat([v.get('K',v['batch']['cam_int']) for v in values]).to(device))


def compact_features(x):
    # Exactly the historical 36-channel MLP representation, now shared inputs.
    summaries=[]
    for d,v,r in zip(x['depth'][:,0],x['valid'][:,0],x['rays']):
        z=d[v];xyz=torch.cat((r[:,v].T*z[:,None],z[:,None]),1)
        if len(z):
            q=torch.quantile(z,z.new_tensor([.1,.25,.5,.75,.9]))
            s=torch.cat((q,xyz.mean(0),xyz.std(0,unbiased=False),(q[-1]-q[0])[None],v.float().mean()[None]))
        else:s=d.new_zeros(13)
        summaries.append(s)
    b=x['batch'];K=b['cam_int'].float();size=b['ori_img_size'].reshape(-1,2).float()
    body=x['official']['pred_vertices'].float()
    quartile=torch.quantile(body,body.new_tensor([.25,.5,.75]),dim=1).permute(1,0,2).flatten(1)
    intrinsic=torch.stack((K[:,0,0]/size[:,0],K[:,1,1]/size[:,1],K[:,0,2]/size[:,0],
        K[:,1,2]/size[:,1],b['bbox_scale'].reshape(-1,2)[:,0]/size[:,0]),1)
    return torch.cat((torch.stack(summaries),intrinsic,x['official']['pred_cam_t'].float(),
                      quartile,body.mean(1),body.std(1,unbiased=False)),1)
