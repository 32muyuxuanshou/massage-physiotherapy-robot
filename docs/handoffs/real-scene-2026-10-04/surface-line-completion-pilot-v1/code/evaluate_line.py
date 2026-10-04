"""Freeze all estimator outputs first; score them against author lines afterwards."""
import argparse,time,sys
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree
from data_line import read,write,sha,features,drop_blocks
from line_net import LineNet
from train_line import fixed_drop_seed

GEOMETRY_ROOT=Path('/raid5/xuhd/datasets/back_reference_extraction_v1_20261004')
sys.path.insert(0,str(GEOMETRY_ROOT/'code'))
from extract_geometry import extract


def predict(root):
    completion=read(root/'TRAINING_COMPLETE.json');assert completion['models']==6
    torch.set_num_threads(4);models=[]
    for trained in read(root/'TRAINING_LEDGER.json'):
        assert sha(trained['checkpoint_path'])==trained['checkpoint_sha256']
        model=LineNet().cuda();model.load_state_dict(torch.load(trained['checkpoint_path'],weights_only=True)['state_dict']);model.eval()
        models.append((trained,model))
    config=read(GEOMETRY_ROOT/'CONFIG.json');outputs=[];(root/'predictions').mkdir(exist_ok=True)
    for row in read(root/'DATA_MANIFEST.json'):
        if row['role']!='consumed_evaluation':continue
        assert sha(row['path'])==row['sha256']
        # NPZ arrays are lazy: reference_line/target arrays are not accessed here.
        with np.load(row['path']) as z:
            points=z['points_m'];xs=z['xs_m'];ys=z['ys_m']
        for condition in ['FULL','MISSING_0','MISSING_1','MISSING_2']:
            if condition=='FULL':visible=points;indices=np.arange(len(points))
            else:visible,indices=drop_blocks(points,fixed_drop_seed(row['candidate_id'],int(condition[-1])))
            tensor,valid=features(visible,xs,ys)
            input_file=root/'predictions'/f"{row['candidate_id']}_{condition}_input.npz"
            np.savez_compressed(input_file,visible_point_indices=indices,features=tensor,xs_m=xs,ys_m=ys,valid=valid)
            estimates=[]
            with torch.no_grad():
                for trained,model in models:
                    torch.cuda.synchronize();start=time.monotonic()
                    logits=model(torch.as_tensor(tensor[None],device='cuda:0'))
                    pred=(logits.softmax(-1)*torch.as_tensor(xs,dtype=torch.float32,device='cuda:0')[None,None,:]).sum(-1)[0].cpu().numpy()
                    torch.cuda.synchronize();elapsed=time.monotonic()-start
                    estimates.append((trained['strategy'],trained['seed'],np.column_stack([pred,ys]),'COMPLETE',elapsed))
            start=time.monotonic();geometry,_=extract(visible,config);elapsed=time.monotonic()-start
            for method,result in geometry.items():
                estimates.append((method,None,result.get('query_xy_m'),result['status'],elapsed))
            for method,seed,xy,status,elapsed in estimates:
                name=f"{row['candidate_id']}_{condition}_{method}"+(f'_seed{seed}' if seed is not None else '')
                record=dict(candidate_id=row['candidate_id'],scan_id=row['scan_id'],condition=condition,method=method,seed=seed,
                    status=status,input_path=str(input_file),input_sha256=sha(input_file),visible_points=len(indices),prediction_seconds=elapsed)
                if status=='COMPLETE':
                    snap,nearest=cKDTree(visible[:,:2]).query(xy)
                    path=root/'predictions'/(name+'.npz')
                    np.savez_compressed(path,query_xy_m=xy,curve_m=visible[nearest],source_point_indices=indices[nearest],
                        xy_snap_distance_m=snap,visible_point_indices=indices)
                    record.update(path=str(path),sha256=sha(path),supported_fraction_3mm=float(np.mean(snap<=.003)))
                outputs.append(record)
            print('PREDICTED',row['candidate_id'],condition,'visible',len(indices),flush=True)
    assert len(outputs)==216
    write(root/'PREDICTION_MANIFEST.json',outputs)
    write(root/'PREDICTION_FREEZE.json',dict(manifest_sha256=sha(root/'PREDICTION_MANIFEST.json'),
        input_sha256={r['input_path']:r['input_sha256'] for r in outputs},
        prediction_sha256={r['path']:r['sha256'] for r in outputs if 'path' in r},reference_labels_used_by_estimators=False))


def score(root):
    freeze=read(root/'PREDICTION_FREEZE.json');assert sha(root/'PREDICTION_MANIFEST.json')==freeze['manifest_sha256']
    rows=read(root/'PREDICTION_MANIFEST.json');cases={r['candidate_id']:r for r in read(root/'DATA_MANIFEST.json')}
    summaries=[];paired=[]
    for candidate in sorted({r['candidate_id'] for r in rows}):
        with np.load(cases[candidate]['path']) as z:
            ys=z['ys_m'];targets=z['target_x_m'];label_valid=z['target_row_valid']
        for condition in ['FULL','MISSING_0','MISSING_1','MISSING_2']:
            group=[r for r in rows if r['candidate_id']==candidate and r['condition']==condition];cached=[]
            for row in group:
                summary=dict(row)
                if row['status']=='COMPLETE':
                    assert sha(row['path'])==row['sha256']
                    with np.load(row['path']) as z:xy=z['query_xy_m']
                    keep=label_valid&(ys>=xy[:,1].min())&(ys<=xy[:,1].max())
                    estimate=np.interp(ys,xy[:,1],xy[:,0]);error=np.abs(estimate-targets)*1000
                    summary.update(lateral_median_mm=float(np.median(error[keep])),lateral_p95_mm=float(np.quantile(error[keep],.95)),
                        label_coverage=float(keep.sum()/label_valid.sum()),evaluated_rows=int(keep.sum()))
                    cached.append((summary,error,keep))
                summaries.append(summary)
            common=label_valid.copy()
            for _,_,keep in cached:common&=keep
            for summary,error,_ in cached:
                paired.append(dict(candidate_id=candidate,condition=condition,method=summary['method'],seed=summary['seed'],
                    common_rows=int(common.sum()),common_lateral_median_mm=float(np.median(error[common])),
                    completed_methods_in_comparison=len(cached),failed_methods=[r['method'] for r in group if r['status']!='COMPLETE']))
    per_scan=[]
    for candidate in sorted(cases):
        for method in sorted({r['method'] for r in summaries}):
            for condition_group in ['FULL','MISSING']:
                subset=[r for r in summaries if r['candidate_id']==candidate and r['method']==method
                        and r['condition'].startswith(condition_group)]
                if not subset:continue
                successful=[r for r in subset if r['status']=='COMPLETE']
                # Equal seeds, then equal missing realizations; each has the same count.
                per_scan.append(dict(candidate_id=candidate,method=method,condition=condition_group,total=len(subset),complete=len(successful),
                    lateral_median_mm=float(np.mean([r['lateral_median_mm'] for r in successful])) if successful else None,
                    lateral_p95_mm=float(np.mean([r['lateral_p95_mm'] for r in successful])) if successful else None,
                    supported_fraction_3mm=float(np.mean([r['supported_fraction_3mm'] for r in successful])) if successful else None))
    aggregate=[]
    for method in sorted({r['method'] for r in summaries}):
        for condition in ['FULL','MISSING']:
            scan=[r for r in per_scan if r['method']==method and r['condition']==condition]
            complete=[r for r in scan if r['complete']==r['total']]
            aggregate.append(dict(method=method,condition=condition,scans=6,complete_scans=len(complete),
                attempts=sum(r['total'] for r in scan),complete_attempts=sum(r['complete'] for r in scan),
                median_of_scan_lateral_median_mm=float(np.median([r['lateral_median_mm'] for r in complete])) if complete else None,
                median_of_scan_lateral_p95_mm=float(np.median([r['lateral_p95_mm'] for r in complete])) if complete else None,
                median_supported_fraction_3mm=float(np.median([r['supported_fraction_3mm'] for r in complete])) if complete else None))
    write(root/'RESULTS.json',dict(records=summaries,common_positions=paired,per_scan=per_scan,aggregate=aggregate,
        clinical_accuracy_validated=False,independent_patient_identity_verified=False,comparison_target='author surface line, native X at same native Y'))
    print('RESULTS',aggregate,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    predict(args.root);score(args.root)
