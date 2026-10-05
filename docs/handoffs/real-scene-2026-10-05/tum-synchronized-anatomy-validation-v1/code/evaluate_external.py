"""One external inference-only exam; frozen models, no TUM model selection."""
import sys,json,time,hashlib
from pathlib import Path
import numpy as np
import torch
ROOT=Path('/raid5/xuhd/datasets/tum_synchronized_anatomy_validation_20261005')
PILOT=Path('/raid5/xuhd/datasets/ct_anatomical_query_pilot_20261005')
sys.path.insert(0,str(PILOT/'code'))
from model import AnatomicalQuery
import evaluate_pilot as evaluate
# Reuse the unchanged numerical evaluator and plotter, redirect only output root.
evaluate.OUT=ROOT
sha=lambda path:evaluate.sha(Path(path))
write=evaluate.write
METHODS=['GLOBAL_REGRESSION','INDEPENDENT_HEATMAP','ORDERED_QUERY']

if __name__=='__main__':
    start=time.time();torch.set_num_threads(2)
    freeze=json.loads((ROOT/'MODEL_IDENTITY.json').read_text());assert freeze['model_code_sha256']==sha(PILOT/'code/model.py');assert freeze['eval_code_sha256']==sha(PILOT/'code/evaluate_pilot.py')
    rows=[r for r in json.loads((ROOT/'CASE_MANIFEST.json').read_text()) if r['eligible']]
    models={}
    for receipt in freeze['models']:
        path=Path(receipt['path']);assert receipt['sha256']==sha(path)
        checkpoint=torch.load(path,map_location='cuda',weights_only=False)
        assert checkpoint['config_sha256']==sha(PILOT/'PROTOCOL.json')
        model=AnatomicalQuery(receipt['method']).cuda();model.load_state_dict(checkpoint['state_dict']);model.eval();models[receipt['method'],receipt['seed']]=model
    old_rows=[r for r in json.loads((PILOT/'CASE_MANIFEST.json').read_text()) if r['eligible'] and r['role']=='train']
    train=[dict(np.load(r['path'])) for r in old_rows]
    median=np.stack([np.median(np.array([x['target_uv'][i] for x in train if x['target_valid'][i]]),axis=0) for i in range(5)])
    records=[]
    for row in rows:
        assert sha(row['path'])==row['input_sha256'];data=dict(np.load(row['path']));current=[evaluate.evaluate_one(row,'TRAIN_MEDIAN_POSITION',-1,median,data)]
        x=torch.tensor(data['input'][None],device='cuda')
        with torch.no_grad():
            for (method,seed),model in models.items():current.append(evaluate.evaluate_one(row,method,seed,model(x)[0].cpu().numpy(),data))
        records.extend(current);evaluate.plot_case(row,current,data);print('external_evaluated',row['subject'],flush=True)
    write(ROOT/'PER_CASE_RESULTS.json',records);summary={}
    for method in ['TRAIN_MEDIAN_POSITION']+METHODS:
        sub=[x for x in records if x['method']==method];subjects=sorted({x['subject'] for x in sub})
        values={s:float(np.median([x['mean_xz_mm'] for x in sub if x['subject']==s])) for s in subjects}
        perseed={str(seed):float(np.mean([x['mean_xz_mm'] for x in sub if x['seed']==seed])) for seed in sorted({x['seed'] for x in sub})}
        summary[method]=dict(case_count=len(subjects),subject_equal_mean_xz_mm=float(np.mean(list(values.values()))),per_subject=values,per_seed_case_mean_xz_mm=perseed,surface_hit_fraction=sum(x['valid_surface_hits'] for x in sub)/sum(x['valid_target_count'] for x in sub),total_order_violations=sum(x['order_violations'] for x in sub))
    groups={}
    for group in ['native_world','export_diagnostic']:
        subjects={r['subject'] for r in rows if r['native_world_validated']==(group=='native_world')};g={}
        for method in ['TRAIN_MEDIAN_POSITION']+METHODS:
            sub=[x for x in records if x['subject'] in subjects and x['method']==method];v=[float(np.median([x['mean_xz_mm'] for x in sub if x['subject']==q])) for q in sorted(subjects)]
            g[method]=dict(case_count=len(subjects),case_equal_xz_mm=float(np.mean(v)) if v else None,surface_hit_fraction=sum(x['valid_surface_hits'] for x in sub)/sum(x['valid_target_count'] for x in sub) if sub else None)
        groups[group]=g
    write(ROOT/'RESULTS.json',dict(summary=summary,coordinate_groups=groups,seconds=time.time()-start,manifest_sha256=sha(ROOT/'CASE_MANIFEST.json'),protocol_sha256=sha(ROOT/'PROTOCOL.json'),scope='External aged lean pathological TUM CT surface proxies; no prone sensor/no clinical acupoint accuracy/no retraining',primary='native_world subgroup of all valid CT-proxy X/Z errors; all17/export-only are separate diagnostics, no surface miss filtering'))
    assert all(sha(Path(x['path']))==x['sha256'] for x in freeze['models']);assert freeze['model_code_sha256']==sha(PILOT/'code/model.py')
    write(ROOT/'POST_EXECUTION_INTEGRITY.json',dict(status='PASS',model_freeze_sha256=sha(ROOT/'MODEL_IDENTITY.json'),models_unchanged=9,model_code_unchanged=True,manifest_sha256=sha(ROOT/'CASE_MANIFEST.json'),protocol_sha256=sha(ROOT/'PROTOCOL.json')))
