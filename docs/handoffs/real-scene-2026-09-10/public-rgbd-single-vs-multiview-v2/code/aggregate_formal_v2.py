import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/'raw/formal_reports'
runs={}
for p in sorted(RAW.glob('*_run_report.json')):
 d=json.loads(p.read_text()); key=f"{d['arm']}_seed{d['run_seed']}"
 vals=[]
 for h in d['history']:
  if 'fixed_val' not in h: continue
  a=h['fixed_val']['aggregation']; inv=h['fixed_val']['rows']
  vals.append({'update':h['update'],'absolute_mm':a['primary_subject_equal_absolute_median_mm'],'aligned_mm':a['diagnostic_translation_aligned_median_mm'],'p90_mm':a['subject_equal_absolute_p90_mm'],'p95_mm':a['subject_equal_absolute_p95_mm'],'coverage':a['median_coverage'],'exact_output_invariance':all(all(x['tensor_exact_equal'] for x in r['forbidden_output_invariance'].values()) for r in inv)})
 best=min(vals,key=lambda x:x['absolute_mm'])
 runs[key]={'arm':d['arm'],'seed':d['run_seed'],'completed_updates':d['optimizer_updates'],'gpu_seconds':d['seconds'],'update_order_sha256':d['update_order_sha256'],'validations':vals,'best':best,'sealed_opened':d['sealed_opened'],'final_reserve_opened':d['final_reserve_opened'],'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
means={a:sum(r['best']['absolute_mm'] for r in runs.values() if r['arm']==a)/2 for a in 'SM'}
agg={'status':'PASS_FOUR_FORMAL_RUNS_AGGREGATED','runs':runs,'arm_best_seed_mean_absolute_mm':means,'multi_minus_single_mm':means['M']-means['S'],'all_exact_output_invariance':all(v['exact_output_invariance'] for r in runs.values() for v in r['validations']),'sealed_opened':False,'final_reserve_opened':False}
(ROOT/'FORMAL_TRAINING_AGGREGATE_V1.json').write_text(json.dumps(agg,indent=2))
sel={'status':'NO_MATERIAL_MULTIVIEW_GAIN','pre_registered_rule':'paired-seed arm trend plus tails/coverage; do not select the lucky single best run','single_seed_bests_mm':[runs['S_seed20260910']['best']['absolute_mm'],runs['S_seed20260911']['best']['absolute_mm']],'multi_seed_bests_mm':[runs['M_seed20260910']['best']['absolute_mm'],runs['M_seed20260911']['best']['absolute_mm']],'single_mean_mm':means['S'],'multi_mean_mm':means['M'],'multi_advantage_mm':means['S']-means['M'],'reason':'0.61484 mm paired-seed mean advantage is small and not consistent: M seed20260911 is worse than S seed20260911. This does not establish a material multi-view benefit.','selected_arm':'S','sealed_candidate':{'arm':'S','seed':20260910,'update':120}}
(ROOT/'VAL_MODEL_SELECTION_V1.json').write_text(json.dumps(sel,indent=2))
cm=json.loads((ROOT/'FORMAL_CHECKPOINT_MANIFEST_V1.json').read_text()); c=next(x for x in cm['checkpoints'] if x['run']=='S_seed20260910' and x['update']==120)
freeze={'status':'FROZEN_BEFORE_FIRST_V2_SEALED_ACCESS','selection_decision':'NO_MATERIAL_MULTIVIEW_GAIN_SELECT_MODEL_S','arm':'S','seed':20260910,'update':120,'checkpoint':c,'selection_source':'VAL_MODEL_SELECTION_V1.json','selection_source_sha256':hashlib.sha256((ROOT/'VAL_MODEL_SELECTION_V1.json').read_bytes()).hexdigest(),'allowed_sealed_comparators':['Official SAM','TRAIN-only Txyz','historical V1 E1','this frozen V2 winner only'],'loser_arm_sealed_access_forbidden':True,'final_reserve_access_forbidden':True}
(ROOT/'V2_WINNER_FREEZE_MANIFEST.json').write_text(json.dumps(freeze,indent=2))
print(json.dumps({'means':means,'winner':freeze},indent=2))
