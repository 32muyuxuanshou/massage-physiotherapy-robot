"""One frozen exam for every checkpoint, with honest missed-surface accounting."""
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

from model import AnatomicalQuery
from prepare_pilot import OUT, LEVELS, sha, write


def surface_position(uv, data):
    xmin,xmax,zmin,zmax=data['xz_bounds_mm'];height=data['surface_height_mm'];valid=data['surface_valid']
    x=float(uv[0])*(height.shape[1]-1);y=float(uv[1])*(height.shape[0]-1)
    x0=int(np.floor(x));y0=int(np.floor(y));x1=min(x0+1,height.shape[1]-1);y1=min(y0+1,height.shape[0]-1)
    if not (0<=x0<height.shape[1] and 0<=y0<height.shape[0]) or not valid[y0:y1+1,x0:x1+1].all():
        return None
    a=x-x0;b=y-y0
    depth=(1-b)*((1-a)*height[y0,x0]+a*height[y0,x1])+b*((1-a)*height[y1,x0]+a*height[y1,x1])
    return np.array([xmin+uv[0]*(xmax-xmin),depth,zmax-uv[1]*(zmax-zmin)])


def evaluate_one(row, method, seed, uv, data):
    valid=data['target_valid'].astype(bool);scale=np.diff(data['xz_bounds_mm'].reshape(2,2),axis=1).ravel()
    error=np.linalg.norm((uv-data['target_uv'])*scale[None],axis=1)
    xyz=np.full((5,3),np.nan);hit=np.zeros(5,bool);distance=np.full(5,np.nan)
    for i,p in enumerate(uv):
        surface=surface_position(p,data)
        if surface is not None:
            xyz[i]=surface;hit[i]=True;distance[i]=np.linalg.norm(surface-data['target_xyz_mm'][i])
    path=OUT/'predictions'/row['role']/(row['subject']+'_'+method+'_seed'+str(seed)+'.npz');path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,pred_uv=uv,pred_xyz_mm=xyz,target_uv=data['target_uv'],target_xyz_mm=data['target_xyz_mm'],
                        target_valid=valid,surface_hit=hit,xz_error_mm=error,xyz_error_mm=distance)
    return dict(subject=row['subject'],role=row['role'],method=method,seed=seed,path=str(path),cache_sha256=sha(path),
                input_sha256=row['input_sha256'],valid_target_count=int(valid.sum()),valid_surface_hits=int((hit&valid).sum()),
                mean_xz_mm=float(error[valid].mean()),p95_xz_mm=float(np.percentile(error[valid],95)),
                per_level_xz_mm=[float(x) if ok else None for x,ok in zip(error,valid)],
                per_level_xyz_mm=[float(x) if ok and np.isfinite(x) else None for x,ok in zip(distance,valid)],
                order_violations=int(np.sum(np.diff(uv[:,1])<=0)),medical_validated=False)


def plot_case(row, values, data):
    fig,axes=plt.subplots(1,4,figsize=(14,7));methods=['TRAIN_MEDIAN_POSITION','GLOBAL_REGRESSION','INDEPENDENT_HEATMAP','ORDERED_QUERY']
    image=np.ma.masked_where(~data['surface_valid'],data['surface_height_mm'])
    for ax,method in zip(axes,methods):
        ax.imshow(image,cmap='viridis',aspect='equal');valid=data['target_valid'].astype(bool)
        h,w=image.shape;target=data['target_uv']*np.array([w-1,h-1])
        ax.scatter(target[valid,0],target[valid,1],c='red',s=30,label='CT-label proxy')
        records=[r for r in values if r['method']==method]
        for r in records:
            with np.load(r['path']) as cache:pred=cache['pred_uv']*np.array([w-1,h-1])
            ax.scatter(pred[valid,0],pred[valid,1],s=15,alpha=.6,c='white')
        for p,name,ok in zip(target,LEVELS,valid):
            if ok:ax.text(p[0]+5,p[1],name,color='red',fontsize=8)
        ax.set_title(method+'\n'+str(round(np.median([r['mean_xz_mm'] for r in records]),2))+' mm X/Z')
    fig.suptitle(row['subject']+' | '+row['role']+' | CT surface only; proxy reference, not acupoint accuracy')
    fig.tight_layout();path=OUT/'figures'/(row['subject']+'.png');path.parent.mkdir(exist_ok=True);fig.savefig(path,dpi=140);plt.close(fig)


def main():
    start=time.monotonic();torch.set_num_threads(2)
    rows=[r for r in json.loads((OUT/'CASE_MANIFEST.json').read_text()) if r['eligible']]
    training=[dict(np.load(r['path'])) for r in rows if r['role']=='train']
    med=np.stack([np.median(np.array([v['target_uv'][i] for v in training if v['target_valid'][i]]),axis=0) for i in range(5)])
    models={};receipts=[]
    for method in ['GLOBAL_REGRESSION','INDEPENDENT_HEATMAP','ORDERED_QUERY']:
        for seed in [0,1,2]:
            path=OUT/'models'/(method+'_seed'+str(seed))/'best.pt';checkpoint=torch.load(path,map_location='cuda',weights_only=False)
            assert checkpoint['config_sha256']==sha(OUT/'PROTOCOL.json')
            model=AnatomicalQuery(method).cuda();model.load_state_dict(checkpoint['state_dict']);model.eval();models[method,seed]=model
            receipts.append(dict(method=method,seed=seed,path=str(path),sha256=sha(path),epoch=checkpoint['epoch']))
    results=[]
    for row in rows:
        assert sha(Path(row['path']))==row['input_sha256'];data=dict(np.load(row['path']));current=[]
        current.append(evaluate_one(row,'TRAIN_MEDIAN_POSITION',-1,med,data))
        x=torch.tensor(data['input'][None],device='cuda')
        with torch.no_grad():
            for (method,seed),model in models.items():current.append(evaluate_one(row,method,seed,model(x)[0].cpu().numpy(),data))
        results.extend(current);plot_case(row,current,data)
        print('evaluated',row['subject'],row['role'],flush=True)
    write(OUT/'PER_CASE_RESULTS.json',results);write(OUT/'MODEL_RECEIPTS.json',receipts)
    summary={}
    for role in ['train','dev','test','author_val_supporting']:
        selected=[r for r in results if r['role']==role];subjects=sorted(set(r['subject'] for r in selected));report={}
        for method in ['TRAIN_MEDIAN_POSITION','GLOBAL_REGRESSION','INDEPENDENT_HEATMAP','ORDERED_QUERY']:
            mr=[r for r in selected if r['method']==method];subject_scores=[float(np.median([r['mean_xz_mm'] for r in mr if r['subject']==s])) for s in subjects]
            perseed={str(seed):float(np.mean([r['mean_xz_mm'] for r in mr if r['seed']==seed])) for seed in sorted(set(r['seed'] for r in mr))}
            report[method]=dict(case_count=len(subjects),subject_equal_mean_xz_mm=float(np.mean(subject_scores)) if subject_scores else None,
                      per_seed_case_mean_xz_mm=perseed,surface_hit_fraction=sum(r['valid_surface_hits'] for r in mr)/sum(r['valid_target_count'] for r in mr) if mr else None,
                      per_subject=dict(zip(subjects,subject_scores)),total_order_violations=sum(r['order_violations'] for r in mr))
        summary[role]=report
    write(OUT/'RESULTS.json',dict(summary=summary,seconds=time.monotonic()-start,config_sha256=sha(OUT/'PROTOCOL.json'),
          manifest_sha256=sha(OUT/'CASE_MANIFEST.json'),scope='CT-derived surface to CT-label proxy; not native prone sensor or acupoint error',
          primary='all valid CT target X/Z error, before any surface miss exclusion'))


if __name__=='__main__':main()
