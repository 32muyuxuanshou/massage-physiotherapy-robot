"""Identical candidate skin/query inputs for a frozen paired CT-source cohort."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from anchored_field import AnchoredField
from source_batch import sample_pack
from reference_frame import make_frame,to_local,from_local,serializable
from train_source import paired,SERVER


def fit_prior(rows):
    values=[[] for _ in range(18)];used=[]
    for row in rows:
        if row['role'] not in ['TRAIN','TRAIN_STRUCTURE_CHECK'] or not paired(row):continue
        with np.load(row['pack']) as z:
            frame=make_frame(z['references_ras_mm'],[0.,-1.,0.],1.)
            xyz=to_local(z['level_xyz_mm'],frame)*500./frame['reference_length_mm']
            flags=z['level_valid']
        for i in np.flatnonzero(flags):values[i].append(xyz[i].tolist())
        used.append(row['case'])
    return dict(source_cases=used,counts=[len(x) for x in values],
                normalized_xyz=[np.median(x,axis=0).tolist() if x else None for x in values],
                source='paired TRAIN only; no test fit')


def evaluate_case(row,model,mode,prior,seed,noise_mm,device):
    # Anatomy is decoded on the original observed surface, as in deployment on a
    # recovered patient mesh. Geometry is assessed separately on disjoint queries.
    batch,identity=sample_pack(row['pack'],seed,1024,256,noise_mm)
    frame=identity['frame']
    with np.load(row['pack']) as z:points=z['points_ras_mm'];targets=z['level_xyz_mm'];flags=z['level_valid']
    local=to_local(points,frame)
    s=local[:,2]*500./frame['reference_length_mm']
    # Registered body ROI uses only supplied references and skin coordinates.
    candidate=np.flatnonzero((s>=-.4)&(s<=1.4)&(abs(local[:,0]*500.)<=150))
    assert len(candidate)>0
    observed=torch.from_numpy(batch['observed'][None]).to(device)
    refs=torch.from_numpy(batch['references'][None]).to(device)
    present=torch.ones(1,2,dtype=torch.bool,device=device)
    field=[]
    with torch.no_grad():
        for part in np.array_split(candidate,max(1,int(np.ceil(len(candidate)/512)))):
            query=torch.from_numpy(local[part].astype(np.float32)[None]).to(device)
            rays=np.zeros((1,len(part),3),np.float32);rays[:,:,1]=1
            out=model(observed,query,refs,present,torch.from_numpy(rays).to(device),hard=mode!='SOFT_ANATOMY')
            field.append(out['anatomical_coordinates'][0].cpu().numpy())
        b={k:torch.from_numpy(v[None]).to(device) for k,v in batch.items()}
        geom=model(b['observed'],b['query'],b['references'],b['reference_present'],b['query_rays'],hard=mode!='SOFT_ANATOMY')
    field=np.concatenate(field);span=frame['reference_length_mm'];prediction=[];prior_prediction=[]
    for level in range(18):
        grade=(level-3)/11.
        objective=((field[:,0]-grade)*span)**2+(field[:,1]*500.)**2
        prediction.append(points[candidate[int(objective.argmin())]])
        coefficient=prior['normalized_xyz'][level]
        if coefficient is None:prior_prediction.append([np.nan]*3);continue
        target=np.asarray(coefficient)*span/500.
        nearest=np.argmin(np.sum((local[candidate]-target)**2,axis=1))
        prior_prediction.append(points[candidate[nearest]])
    prediction=np.asarray(prediction);prior_prediction=np.asarray(prior_prediction)
    used=flags & np.array([c is not None for c in prior['normalized_xyz']]);used[[3,14]]=False
    full_error=np.linalg.norm(prediction-targets,axis=1);prior_error=np.linalg.norm(prior_prediction-targets,axis=1)
    xz_error=np.linalg.norm((prediction-targets)[:,[0,2]],axis=1)
    radial=geom['ray_delta'][0].cpu().numpy() if mode=='HARD_JOINT' else np.zeros(256)
    geometry_error=abs(radial-batch['ray_target'])*500.
    metrics=dict(case=row['case'],role=row['role'],model=mode,scored_levels=np.flatnonzero(used).tolist(),
                 level_error_xyz_mm=full_error.tolist(),level_error_xz_mm=xz_error.tolist(),
                 prior_level_error_xyz_mm=prior_error.tolist(),
                 case_mean_xyz_mm=float(full_error[used].mean()),case_mean_xz_mm=float(xz_error[used].mean()),
                 prior_case_mean_xyz_mm=float(prior_error[used].mean()),
                 ray_median_mm=float(np.median(geometry_error)),ray_p95_mm=float(np.quantile(geometry_error,.95)),
                 zero_ray_median_mm=float(np.median(abs(batch['ray_target'])*500.)),
                 candidate_count=len(candidate),reference_noise_mm=noise_mm,
                 metric_type='CT skin proxy; radial source corruption; not clinical or sensor accuracy')
    arrays=dict(points_ras_mm=points,target_level_xyz_mm=targets,level_valid=flags,scored_level_mask=used,
                predicted_level_xyz_mm=prediction,prior_level_xyz_mm=prior_prediction,candidate_indices=candidate,field=field,
                **batch,predicted_ray_delta=radial,observed_indices=identity['observed_indices'],query_indices=identity['query_indices'])
    assert len(np.intersect1d(identity['observed_indices'],identity['query_indices']))==0
    return metrics,arrays,serializable(frame)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SERVER/'v3_dataset')
    p.add_argument('--model',choices=['SOFT_ANATOMY','HARD_ANATOMY','HARD_JOINT'],required=True)
    p.add_argument('--seed',type=int,choices=[0,1,2],required=True);p.add_argument('--reference-noise-mm',type=float,choices=[0.,5.],default=0.)
    p.add_argument('--model-root',type=Path,default=SERVER.parent/'reference_anchored_surface_field_v2_20261005');args=p.parse_args()
    rows=json.loads((args.source/'CASE_MANIFEST.json').read_text());prior=fit_prior(rows)
    train=args.model_root/(args.model+'_seed'+str(args.seed))
    receipt=json.loads((train/'TRAINING_RECEIPT.json').read_text())
    assert receipt['status']=='SOURCE_TRAINING_COMPLETE_NO_TEST_READ'
    assert receipt['source_manifest_sha256']==hashlib.sha256((args.source/'CASE_MANIFEST.json').read_bytes()).hexdigest()
    checkpoint=train/'best.pt';assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==receipt['checkpoint_sha256']
    model=AnchoredField().cuda();model.load_state_dict(torch.load(checkpoint,map_location='cuda',weights_only=True));model.eval()
    output=train/('test_refnoise'+str(int(args.reference_noise_mm)));output.mkdir(exist_ok=True)
    (output/'PRIOR.json').write_text(json.dumps(prior,indent=2)+'\n');results=[];skipped=[]
    for row in rows:
        if row['role']!='AUTHOR_TEST_UNCONSUMED_IMAGE':continue
        if not paired(row):skipped.append(dict(case=row['case'],reason='SOURCE_OR_REFERENCE_PAIR_NOT_QUALIFIED'));continue
        seed=int(row['ct_sha256'][:8],16)
        metrics,arrays,frame=evaluate_case(row,model,args.model,prior,seed,args.reference_noise_mm,'cuda')
        cache=output/(row['case']+'.npz');np.savez_compressed(cache,**arrays)
        metrics.update(seed=args.seed,cache_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),
                       pack_sha256=row['pack_sha256'],frame=frame);results.append(metrics)
    (output/'RESULTS.json').write_text(json.dumps(dict(results=results,source_disqualifications=skipped,
                      original_author_test_images=88,unit='image_id_not_certified_patient',
                      checkpoint_sha256=receipt['checkpoint_sha256'],clinical_validated=False),indent=2)+'\n')


if __name__=='__main__':main()
