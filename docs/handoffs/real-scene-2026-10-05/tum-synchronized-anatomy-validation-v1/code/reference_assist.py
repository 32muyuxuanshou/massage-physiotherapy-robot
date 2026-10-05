"""Two typed oracle references, fixed old-training prior or frozen prediction calibration.
No held-out target is read by estimate(); this is an engineering baseline, not a novel neural model.
"""
import json,sys,hashlib,time
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from prepare_external import ROOT, LEVELS, surface_at
PILOT=Path('/raid5/xuhd/datasets/ct_anatomical_query_pilot_20261005')
REF=[1,4];HELDOUT=[0,2,3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def relative(points,ref):
    first,last=ref;length=first[1]-last[1];r=(points[:,1]-first[1])/(last[1]-first[1])
    dx=(points[:,0]-((1-r)*first[0]+r*last[0]))/length
    return np.column_stack((dx,r)),float(length)

def estimate(parameters,ref,bounds):
    first,last=ref;dx,r=parameters.T;length=first[1]-last[1]
    x=(1-r)*first[0]+r*last[0]+dx*length;z=(1-r)*first[1]+r*last[1]
    xmin,xmax,zmin,zmax=bounds;return np.column_stack(((x-xmin)/(xmax-xmin),(zmax-z)/(zmax-zmin)))

def fit_source_prior():
    rows=[r for r in json.loads((PILOT/'CASE_MANIFEST.json').read_text()) if r['eligible'] and r['role']=='train'];values=[[] for _ in LEVELS];inputs=[]
    for row in rows:
        data=dict(np.load(row['path']))
        if not data['target_valid'][REF].all():continue
        p=data['target_xyz_mm'][:,[0,2]];params,_=relative(p,p[REF])
        for i in range(5):
            if data['target_valid'][i]:values[i].append(params[i])
        inputs.append(dict(subject=row['subject'],input_sha256=row['input_sha256']))
    prior=np.array([np.median(v,axis=0) for v in values]);assert np.isfinite(prior).all()
    output=dict(parameters=prior.tolist(),per_level_source_count=[len(v) for v in values],training_cases=inputs,prior_manifest_sha256=sha(PILOT/'CASE_MANIFEST.json'),reference_input_levels=['T3','L2'],fitted_from='previous source TRAIN only')
    (ROOT/'REFERENCE_PRIOR_FIT.json').write_text(json.dumps(output,indent=2)+'\n');return prior

def score(row,method,seed,uv,data,evaluation_mask,params=None):
    bounds=data['xz_bounds_mm'];scale=np.diff(bounds.reshape(2,2),axis=1).ravel();error=np.linalg.norm((uv-data['target_uv'])*scale,axis=1)
    xyz=np.full((5,3),np.nan);hit=np.zeros(5,bool)
    for i,p in enumerate(uv):
        q=surface_at(p,bounds,data['surface_height_mm'],data['surface_valid'])
        if q is not None:xyz[i]=q;hit[i]=True
    path=ROOT/'reference_predictions'/(row['subject']+'_'+method+'_seed'+str(seed)+'.npz');path.parent.mkdir(exist_ok=True)
    np.savez_compressed(path,pred_uv=uv,pred_xyz_mm=xyz,target_uv=data['target_uv'],target_xyz_mm=data['target_xyz_mm'],target_valid=data['target_valid'],evaluation_mask=evaluation_mask,xz_error_mm=error,surface_hit=hit,reference_xyz_mm=data['target_xyz_mm'][REF],reference_indices=REF)
    return dict(subject=row['subject'],method=method,seed=seed,path=str(path),cache_sha256=sha(path),mean_xz_mm=float(error[evaluation_mask].mean()),evaluated_targets=int(evaluation_mask.sum()),evaluated_surface_hits=int((hit&evaluation_mask).sum()),per_level_xz_mm=[float(e) if ok else None for e,ok in zip(error,evaluation_mask)],native_world_validated=row['native_world_validated'],parameters=None if params is None else params.tolist(),reference_source='exact CT-to-skin proxy oracle; not real clinical input')

if __name__=='__main__':
    start=time.time();prior=fit_source_prior();manifest=json.loads((ROOT/'CASE_MANIFEST.json').read_text());frozen=json.loads((ROOT/'PER_CASE_RESULTS.json').read_text());results=[];eligibility=[]
    for row in manifest:
        data=dict(np.load(row['path']));ok=row['eligible'] and data['target_valid'][REF].all();mask=data['target_valid'].copy();mask[REF]=False;ok=bool(ok and mask.sum()>0)
        eligibility.append(dict(subject=row['subject'],eligible=ok,missing_reference=[LEVELS[i] for i in REF if not data['target_valid'][i]],held_out_levels=[LEVELS[i] for i in range(5) if mask[i]]))
        if not ok:continue
        ref=data['target_xyz_mm'][REF][:,[0,2]];candidates=[]
        for method in ['GLOBAL_REGRESSION','INDEPENDENT_HEATMAP','ORDERED_QUERY']:
            for seed in [0,1,2]:
                entry=next(x for x in frozen if x['subject']==row['subject'] and x['method']==method and x['seed']==seed)
                cache=dict(np.load(entry['path']));assert sha(entry['path'])==entry['cache_sha256'];uv=cache['pred_uv'];candidates.append((method,seed,uv,None))
                if method in ['GLOBAL_REGRESSION','ORDERED_QUERY']:
                    bounds=data['xz_bounds_mm'];pred=np.column_stack((bounds[0]+uv[:,0]*(bounds[1]-bounds[0]),bounds[3]-uv[:,1]*(bounds[3]-bounds[2])))
                    params,length=relative(pred,pred[REF]);assert abs(length)>1e-6
                    name='GLOBAL_PLUS_TWO_REFERENCE' if method=='GLOBAL_REGRESSION' else 'QUERY_PLUS_TWO_REFERENCE'
                    candidates.append((name,seed,estimate(params,ref,bounds),params))
        candidates.append(('TWO_REFERENCE_PRIOR',-1,estimate(prior,ref,data['xz_bounds_mm']),prior))
        current=[score(row,c[0],c[1],c[2],data,mask,c[3]) for c in candidates];results.extend(current)
        methods=['GLOBAL_REGRESSION','ORDERED_QUERY','TWO_REFERENCE_PRIOR','QUERY_PLUS_TWO_REFERENCE'];fig,axes=plt.subplots(1,4,figsize=(14,7));image=np.ma.masked_where(~data['surface_valid'],data['surface_height_mm']);h,w=image.shape
        for ax,method in zip(axes,methods):
            ax.imshow(image,cmap='viridis',aspect='equal');target=data['target_uv']*[w-1,h-1];ax.scatter(target[REF,0],target[REF,1],c='cyan',s=35,label='two input oracle refs');ax.scatter(target[mask,0],target[mask,1],c='red',s=35,label='held-out proxy')
            entries=[x for x in current if x['method']==method]
            for e in entries:
                with np.load(e['path']) as p:pred=p['pred_uv']*[w-1,h-1]
                ax.scatter(pred[mask,0],pred[mask,1],c='white',s=15,alpha=.7)
            ax.set_title(method+'\n'+str(round(np.median([x['mean_xz_mm'] for x in entries]),2))+' mm held-out X/Z')
        fig.suptitle(row['subject']+' / two CT-proxy oracle references, no clinical labels');fig.tight_layout();(ROOT/'reference_figures').mkdir(exist_ok=True);fig.savefig(ROOT/'reference_figures'/(row['subject']+'.png'),dpi=130);plt.close(fig)
        print('reference_evaluated',row['subject'],flush=True)
    methods=sorted({r['method'] for r in results});summary={}
    for group in ['all_source','native_world','export_diagnostic']:
        summary[group]={}
        for method in methods:
            sub=[x for x in results if x['method']==method and (group=='all_source' or x['native_world_validated']==(group=='native_world'))];subjects=sorted({x['subject'] for x in sub});values={s:float(np.median([x['mean_xz_mm'] for x in sub if x['subject']==s])) for s in subjects}
            summary[group][method]=dict(case_count=len(subjects),case_equal_mean_xz_mm=float(np.mean(list(values.values()))) if values else None,per_subject=values,surface_hit_fraction=sum(x['evaluated_surface_hits'] for x in sub)/sum(x['evaluated_targets'] for x in sub) if sub else None)
    (ROOT/'REFERENCE_ASSIST_RESULTS.json').write_text(json.dumps(dict(summary=summary,eligibility=eligibility,records=results,seconds=time.time()-start,contract_sha256=sha(ROOT/'REFERENCE_ASSIST_PROTOCOL.json'),prior_sha256=sha(ROOT/'REFERENCE_PRIOR_FIT.json'),scope='Oracle-reference mechanism baseline, held-out reference levels excluded, no new training/fitting/clinical accuracy'),indent=2)+'\n')
