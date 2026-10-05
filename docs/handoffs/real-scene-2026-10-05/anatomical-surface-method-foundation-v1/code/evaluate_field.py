"""Fixed candidate surface and fixed observations for all CT source methods.

The endpoints supplied as oracle prompts are excluded from anatomy errors.
CT image-ID separation is not certified patient separation or clinical accuracy.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from acquire_full_v3 import ROOT
from fit_field_prior import predict as prior_predict
from joint_surface_field import JointSurfaceField
from train_field import GlobalField


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_case(row, reference_noise_mm=0.):
    with np.load(row['pack']) as data:
        points=data['points_ras_mm'].copy(); targets=data['level_xyz_mm'].copy(); valid=data['level_valid'].copy()
        references=data['references_ras_mm'].copy(); present=data['reference_present'].copy()
    rng=np.random.default_rng(int(row['ct_sha256'][:8],16)+700000)
    observed_index=rng.choice(len(points),1024,replace=False)
    rest=np.setdiff1d(np.arange(len(points)),observed_index)
    geometry_index=rng.choice(rest,256,replace=False)
    origin=np.median(points[observed_index],axis=0)
    observed=(points[observed_index]-origin)/500.+rng.normal(0,.004,(1024,3))
    refs=(references+rng.normal(0,reference_noise_mm,references.shape)-origin)/500.
    geometry_query=(points[geometry_index]-origin)/500.+rng.normal(0,.02,(256,3))
    return dict(points=points,targets=targets,target_valid=valid,references=references,
                origin=origin,observed=observed.astype(np.float32),reference_present=present,
                references_normalized=refs.astype(np.float32),geometry_query=geometry_query.astype(np.float32),
                observed_index=observed_index,geometry_index=geometry_index,reference_noise_mm=reference_noise_mm)


def model_prediction(model,kind,batch,device):
    observed=torch.as_tensor(batch['observed'][None],device=device)
    refs=torch.as_tensor(batch['references_normalized'][None],device=device)
    present=torch.as_tensor(batch['reference_present'][None],device=device)
    points=batch['points'];origin=batch['origin']
    fields=[]
    with torch.no_grad():
        # The reference implementation re-encodes the observation per chunk.
        # It is correct but can be optimized after timing, without changing inputs.
        for start in range(0,len(points),1024):
            query=torch.as_tensor(((points[start:start+1024]-origin)/500.)[None],dtype=torch.float32,device=device)
            pred=model(observed,query,refs,present)
            fields.append(pred['anatomical_coordinates'][0].cpu().numpy())
        query=torch.as_tensor(batch['geometry_query'][None],device=device)
        delta=model(observed,query,refs,present)['surface_delta'][0].cpu().numpy() if kind=='LOCAL_JOINT' else np.zeros((256,3),np.float32)
    field=np.concatenate(fields)
    longitudinal_scale=float(np.linalg.norm(batch['references_normalized'][1]-batch['references_normalized'][0])*500.) if batch['reference_present'].all() else 250.
    level_s=(np.arange(18)-3.)/11.
    indices=[]
    for value in level_s:
        residual=(field[:,0]-value)**2*longitudinal_scale**2+(field[:,1]*500.)**2
        indices.append(int(np.argmin(residual)))
    geometry=(batch['geometry_query']+delta)*500.+origin
    return dict(level_xyz_mm=points[indices],candidate_indices=np.array(indices),field=field,
                geometry_prediction_mm=geometry)


def scores(pred,batch,common_levels):
    valid=batch['target_valid'].copy();valid[[3,14]]=False
    valid &= common_levels
    anatomy=np.linalg.norm(pred['level_xyz_mm']-batch['targets'],axis=1)
    errors=anatomy[valid]
    assert len(errors)>0
    before=batch['geometry_query']*500.+batch['origin']
    target=batch['points'][batch['geometry_index']]
    geometry_before=np.linalg.norm(before-target,axis=1)
    geometry_after=np.linalg.norm(pred['geometry_prediction_mm']-target,axis=1)
    # Candidate discretization floor is oracle-only diagnostic, never a method.
    floor=np.array([np.linalg.norm(batch['points']-p,axis=1).min() for p in batch['targets'][valid]])
    return dict(anatomy_level_errors_mm=anatomy.tolist(),scored_levels=np.flatnonzero(valid).tolist(),
                anatomy_case_mean_mm=float(errors.mean()),anatomy_case_median_mm=float(np.median(errors)),
                geometry_before_mean_mm=float(geometry_before.mean()),geometry_after_mean_mm=float(geometry_after.mean()),
                geometry_after_p95_mm=float(np.quantile(geometry_after,.95)),
                candidate_oracle_floor_mean_mm=float(floor.mean()),
                geometry_metric='paired synthetic query displacement, NOT independent RGB-D surface accuracy')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--reference-noise-mm',type=float,default=0.)
    parser.add_argument('--no-references',action='store_true');args=parser.parse_args()
    source=ROOT/'v3_dataset';rows=json.loads((source/'CASE_MANIFEST.json').read_text())
    prior=json.loads((source/'TWO_REFERENCE_PRIOR.json').read_text())
    common=np.array([p is not None for p in prior['coefficients']])
    cases=[r for r in rows if r['eligible'] and r['role']=='AUTHOR_TEST_UNCONSUMED_IMAGE']
    tag='noreferences' if args.no_references else 'refnoise'+str(args.reference_noise_mm)
    output=ROOT/'source_evaluation'/('seed'+str(args.seed)+'_'+tag);output.mkdir(parents=True,exist_ok=True)
    models={};identity={}
    for kind in ['GLOBAL_ANATOMY','LOCAL_ANATOMY','LOCAL_JOINT']:
        train_root=ROOT/'source_training'/(kind+'_seed'+str(args.seed))
        receipt=json.loads((train_root/'TRAINING_RECEIPT.json').read_text());assert receipt['test_images_used']==0
        model=(GlobalField() if kind=='GLOBAL_ANATOMY' else JointSurfaceField()).cuda()
        model.load_state_dict(torch.load(train_root/'best.pt',map_location='cuda',weights_only=True));model.eval()
        models[kind]=model;identity[kind]=dict(checkpoint_sha256=sha(train_root/'best.pt'),training_receipt_sha256=sha(train_root/'TRAINING_RECEIPT.json'))
    results=[]
    for row in cases:
        batch=prepare_case(row,args.reference_noise_mm)
        if args.no_references:
            batch['reference_present'][:]=False
        case_dir=output/row['case'];case_dir.mkdir(exist_ok=True)
        np.savez_compressed(case_dir/'shared_input.npz',**batch)
        for kind,model in models.items():
            pred=model_prediction(model,kind,batch,'cuda')
            np.savez_compressed(case_dir/(kind+'.npz'),**pred)
            results.append(dict(case=row['case'],method=kind,seed=args.seed,oracle_reference_present=batch['reference_present'].tolist(),**scores(pred,batch,common)))
        if batch['reference_present'].all():
            refs=batch['references_normalized']*500.+batch['origin']
            xyz,raw=prior_predict(prior,batch['points'],refs)
            pred=dict(level_xyz_mm=xyz,geometry_prediction_mm=batch['geometry_query']*500.+batch['origin'],raw_prior_xz_mm=raw)
            np.savez_compressed(case_dir/'TWO_REFERENCE_PRIOR.npz',**pred)
            results.append(dict(case=row['case'],method='TWO_REFERENCE_PRIOR',seed=args.seed,oracle_reference_present=[True,True],**scores(pred,batch,common)))
        if args.no_references:
            raw=batch['origin']+500.*np.asarray(prior['global_prior_normalized_xyz'])
            indices=[int(np.argmin(np.sum((batch['points'][:,[0,2]]-p[[0,2]])**2,axis=1))) for p in raw]
            pred=dict(level_xyz_mm=batch['points'][indices],geometry_prediction_mm=batch['geometry_query']*500.+batch['origin'])
            np.savez_compressed(case_dir/'TRAIN_GLOBAL_PRIOR.npz',**pred)
            results.append(dict(case=row['case'],method='TRAIN_GLOBAL_PRIOR',seed=args.seed,oracle_reference_present=[False,False],**scores(pred,batch,common)))
        (output/'PER_CASE.json').write_text(json.dumps(results,indent=2)+'\n')
        print(row['case'],'evaluated',flush=True)
    receipt=dict(status='SOURCE_EVAL_COMPLETE_NOT_CLINICAL',CT_images=len(cases),seed=args.seed,
                 reference_noise_mm=args.reference_noise_mm,models=identity,
                 reference_mode='NONE' if args.no_references else 'CT_ORACLE_WITH_REGISTERED_NOISE',
                 source_manifest_sha256=sha(source/'CASE_MANIFEST.json'),prior_sha256=sha(source/'TWO_REFERENCE_PRIOR.json'),
                 target_refs_excluded=['T3','L2'],candidate_source='same 8192-point CT posterior surface pack for all methods',
                 geometry_observation_query_disjoint=True,patient_disjointness_certified=False)
    (output/'EVALUATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    main()
