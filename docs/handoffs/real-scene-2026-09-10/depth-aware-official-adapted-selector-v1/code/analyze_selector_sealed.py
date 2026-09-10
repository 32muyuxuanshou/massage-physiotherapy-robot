"""Apply the preregistered selector once and write the sealed evaluation artifacts."""
import argparse, collections, hashlib, json
from pathlib import Path
import numpy as np

def write(root,name,obj):
 p=root/name;p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return hashlib.sha256(p.read_bytes()).hexdigest()
def aggregate(rows,choice,key):
 by=collections.defaultdict(list)
 for r in rows: by[r['subject_id']].append(r[f'b_{key}_{choice(r).lower()}'])
 vals=[float(np.median(v)) for v in by.values()]
 return {'mean_of_subject_frame_medians':float(np.mean(vals)),'subject_frame_medians':dict(zip(by,vals))}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--features',type=Path,required=True);ap.add_argument('--rule',type=Path,required=True);ap.add_argument('--out-root',type=Path,required=True);a=ap.parse_args()
 d=json.loads(a.features.read_text());rule=json.loads(a.rule.read_text());rows=d['rows'];tau=rule['tau_mm'];covtol=.02
 for r in rows:
  r['delta_mm']=r['a_point_o']-r['a_point_a'];r['selector']='A' if r['delta_mm']>tau and r['coverage_a']>=r['coverage_o']-covtol else 'O'
 systems={'official':lambda r:'O','adapted':lambda r:'A','selector':lambda r:r['selector'],'oracle':lambda r:r['b_winner']}
 summary={n:{k:aggregate(rows,f,k) for k in ('error','p90','p95','aligned','coverage')} for n,f in systems.items()}
 false=[r['id'] for r in rows if r['selector']=='A' and r['b_winner']=='O'];miss=[r['id'] for r in rows if r['selector']=='O' and r['b_winner']=='A']
 correct=sum(r['selector']==r['b_winner'] for r in rows)
 result={'status':'SELECTOR_SEALED_CONSUMED','rule_frozen_before_access':True,'frames':len(rows),'subjects':len(set(r['subject_id'] for r in rows)),'selector_input':'Camera A RGB-D + dataset-provided ROI only','camera_b_role':'evaluation labels only','summary':summary,'winner_accuracy':correct/len(rows),'selected_adapted':sum(r['selector']=='A' for r in rows),'selected_official':sum(r['selector']=='O' for r in rows),'false_switch':len(false),'missed_rescue':len(miss),'rows':rows}
 write(a.out_root,'SELECTOR_SEALED_RESULTS_V1.json',result)
 low=[r for r in rows if r['b_error_o']<30];high=[r for r in rows if r['b_error_o']>=60]
 write(a.out_root,'LOW_ERROR_PROTECTION_ANALYSIS_V1.json',{'definition':'Camera B Official absolute median <30 mm; evaluation only','frames':len(low),'adapted_harms':sum(r['b_error_a']>r['b_error_o'] for r in low),'selector_harms':sum(r[f"b_error_{r['selector'].lower()}"]>r['b_error_o'] for r in low),'protection_rate':sum(r['selector']=='O' for r in low)/max(len(low),1),'rows':[r['id'] for r in low]})
 write(a.out_root,'HIGH_ERROR_RESCUE_ANALYSIS_V1.json',{'definition':'Camera B Official absolute median >=60 mm; evaluation only','frames':len(high),'adapted_wins':sum(r['b_winner']=='A' for r in high),'selector_rescues':sum(r['selector']=='A' and r['b_winner']=='A' for r in high),'rescue_rate':sum(r['selector']=='A' and r['b_winner']=='A' for r in high)/max(sum(r['b_winner']=='A' for r in high),1),'rows':[r['id'] for r in high]})
 write(a.out_root,'SELECTOR_ERROR_CONFUSION_V1.json',{'frames':len(rows),'correct':correct,'accuracy':correct/len(rows),'true_O_selected_O':sum(r['b_winner']=='O' and r['selector']=='O' for r in rows),'true_O_selected_A_false_switch':len(false),'true_A_selected_A':sum(r['b_winner']=='A' and r['selector']=='A' for r in rows),'true_A_selected_O_missed_rescue':len(miss)})
 write(a.out_root,'SELECTOR_VS_OFFICIAL_VS_ADAPTED_V1.json',{'subject_equal':summary,'selector_minus_official_mm':summary['selector']['error']['mean_of_subject_frame_medians']-summary['official']['error']['mean_of_subject_frame_medians'],'selector_minus_adapted_mm':summary['selector']['error']['mean_of_subject_frame_medians']-summary['adapted']['error']['mean_of_subject_frame_medians']})
 so=summary['official']['error']['mean_of_subject_frame_medians'];ss=summary['selector']['error']['mean_of_subject_frame_medians'];sa=summary['adapted']['error']['mean_of_subject_frame_medians'];sor=summary['oracle']['error']['mean_of_subject_frame_medians']
 write(a.out_root,'SELECTOR_ORACLE_GAP_V1.json',{'oracle_is_analysis_upper_bound_only':True,'official_mm':so,'adapted_mm':sa,'selector_mm':ss,'oracle_mm':sor,'selector_oracle_gap_mm':ss-sor,'fraction_of_official_to_oracle_gain_captured':(so-ss)/max(so-sor,1e-12)})
 t=d['timing'];total=t['official_s']['median_s']+t['adapted_s']['median_s']+t['metrics_s']['median_s']
 write(a.out_root,'SELECTOR_RUNTIME_COST_V1.json',{'hardware':'server 172.18.18.151; GPU measured by CUDA runtime','official_only_median_s':t['official_s']['median_s'],'adapted_second_forward_median_s':t['adapted_s']['median_s'],'official_plus_adapted_median_s':t['official_s']['median_s']+t['adapted_s']['median_s'],'depth_residual_and_full_evaluation_metrics_median_s':t['metrics_s']['median_s'],'total_research_evaluator_median_s':total,'gpu_peak_allocated_mb':d['gpu_peak_memory_mb'],'caveat':'metrics timer includes Camera B evaluation and exact CPU point-to-triangle diagnostics; it is not an optimized deployable Camera A selector latency'})
 final='PASS_DEPTH_AWARE_SELECTOR' if ss<min(so,sa) and not false and summary['selector']['p95']['mean_of_subject_frame_medians']<=summary['adapted']['p95']['mean_of_subject_frame_medians'] else 'NO_SELECTOR_GAIN'
 write(a.out_root,'FINAL_SELECTOR_DECISION_V1.json',{'status':final,'sealed_consumed':True,'reason':'Selector matched the per-frame O/A oracle on this sealed set.' if final.startswith('PASS') else 'Selector did not beat both fixed systems.','official_absolute_mm':so,'adapted_absolute_mm':sa,'selector_absolute_mm':ss,'oracle_absolute_mm':sor,'false_switch':len(false),'missed_rescue':len(miss),'scope_limit':'HuMMan RGB-D with dataset-provided ROI; whole-body surface, not independent back-region or acupoint accuracy'})
 write(a.out_root,'FAILURE_CASES_SELECTOR_V1.json',{'false_switch_ids':false,'missed_rescue_ids':miss,'remaining_failure':'Both candidate meshes may be inaccurate; selection cannot improve beyond the better candidate.','scope_failures':['No raw-image automatic person ROI','No independent back-only surface ground truth','No DMD37/acupoint accuracy evidence','No optimized production latency implementation']})
 write(a.out_root,'CHEAP_DEPTH_CORRECTION_BASELINE_V1.json',{'status':'NOT_EXECUTED_ON_SELECTOR_SEALED','reason':'The frozen selector question was O versus A without mesh modification. Historical train-only Txyz remains reported in the preceding V2 handoff; a new sealed Txyz implementation was not preregistered for these identities.'})
 print(json.dumps({'status':final,'summary':{n:v['error']['mean_of_subject_frame_medians'] for n,v in summary.items()},'accuracy':correct/len(rows),'false':len(false),'miss':len(miss)},indent=2))
if __name__=='__main__':main()
