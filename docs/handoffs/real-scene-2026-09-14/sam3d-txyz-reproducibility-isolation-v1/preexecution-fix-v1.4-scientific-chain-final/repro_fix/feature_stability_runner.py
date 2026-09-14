import argparse,json
from pathlib import Path
import numpy as np
from .feature_stability import classify

def load_payloads(cohort_summary):
 cohort=json.loads(Path(cohort_summary).read_text())
 if cohort.get('status')!='PASS_SAM_COHORT_TXYZ_EXECUTION' or cohort.get('primary_runs')!=['RUN_B','RUN_C','RUN_D','RUN_E','RUN_F']:raise RuntimeError('SAM_COHORT_TXYZ_INPUT_INVALID')
 payloads=[]
 for row in cohort['rows']:
  if [run['run_id'] for run in row['runs']]!=cohort['primary_runs']:raise RuntimeError('SAM_COHORT_RUN_ORDER_INVALID')
  payloads.append((row['frame_id'],row['runs']))
 return payloads

def matrix(payloads,fn):return np.asarray([[fn(run) for run in runs] for _,runs in payloads])

def extractor_map():
 return {
  'tx_mm':lambda r:r['translation_values'][0]*1000,
  'ty_mm':lambda r:r['translation_values'][1]*1000,
  'tz_mm':lambda r:r['translation_values'][2]*1000,
  'translation_norm_mm':lambda r:np.linalg.norm(r['translation_values'])*1000,
  'iteration_step_vectors_mm':lambda r:np.asarray([x['step_values'] for x in r['trace']])*1000,
  'iteration_step_norms_mm':lambda r:np.asarray([x['step_norm_m'] for x in r['trace']])*1000,
  'convergence_ratio':lambda r:r['features']['convergence_ratio'],
  'direction_consistency':lambda r:r['features']['direction_consistency'],
  'oscillation':lambda r:r['features']['oscillation'],
  'fallback':lambda r:r['fallback'],
  'raw_residual_median_mm':lambda r:r['features']['raw_residual_median_mm'],
  'residual_mad_mm':lambda r:r['features']['residual_mad_mm'],
  'residual_p90_mm':lambda r:r['features']['residual_p90_mm'],
  'residual_p95_mm':lambda r:r['features']['residual_p95_mm'],
  'trim_threshold_mm':lambda r:r['trace'][-1]['trim_threshold_raw']*1000,
  'retained_count':lambda r:r['trace'][-1]['retained_count'],
  'raw_correspondence_count':lambda r:r['trace'][-1]['raw_correspondence_count'],
  'valid_depth_pixels':lambda r:r['data_features']['valid_depth_pixels'],
  'depth_support_fraction':lambda r:r['data_features']['depth_support_fraction'],
  'depth_hole_ratio':lambda r:r['data_features']['depth_hole_ratio'],
  'support_left_right_balance':lambda r:r['data_features']['support_left_right_balance'],
  'support_top_bottom_balance':lambda r:r['data_features']['support_top_bottom_balance'],
  'nearest_hash':lambda r:r['trace'][-1]['nearest']['sha256'],
  'keep_hash':lambda r:r['trace'][-1]['keep']['sha256'],
  'pointcloud_hash':lambda r:r['pointcloud_hash'],
  'anchor_hash':lambda r:r['anchor_hash'],
  'model_state_hash':lambda r:r['model_state_hash']}

def characterize(cohort_summary,contract_path):
 payloads=load_payloads(cohort_summary);contract_doc=json.loads(Path(contract_path).read_text());contracts=contract_doc['features'];extractors=extractor_map();required=set(contracts);implemented=set(extractors);missing=sorted(required-implemented);unexpected=sorted(implemented-required);coverage={'required_count':len(required),'characterized_count':len(implemented&required),'missing':missing,'unexpected':unexpected,'exact':not missing and not unexpected}
 if not coverage['exact']:return {'status':'FEATURE_STABILITY_CONTRACT_COVERAGE_FAILED','coverage':coverage,'outcome_fields_read':False}
 results={}
 for name in sorted(required):
  values=matrix(payloads,extractors[name]);feature_contract=contracts[name]
  if feature_contract.get('per_iteration') and feature_contract['type']!='VECTOR_MM':
   per={f'iter{i+1}':classify(values[:,:,i],feature_contract) for i in range(values.shape[-1])};rank={'STABLE':0,'CAUTION':1,'UNSTABLE':2};results[name]={'per_iteration':per,'status':max((value['status'] for value in per.values()),key=rank.get)}
  else:results[name]=classify(values,feature_contract)
 counts={status:sum(value['status']==status for value in results.values()) for status in ('STABLE','CAUTION','UNSTABLE')}
 return {'status':'PASS_FEATURE_STABILITY_CHARACTERIZATION','scientific_scope':'B-F SAM rerun anchors propagated through frozen Txyz on identical K0 points','primary_runs':['RUN_B','RUN_C','RUN_D','RUN_E','RUN_F'],'outcome_fields_read':False,'coverage':coverage,'features':results,'counts':counts}

def main():
 p=argparse.ArgumentParser();p.add_argument('--cohort-summary',type=Path,required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(characterize(a.cohort_summary,a.contract),indent=2)+'\n')
if __name__=='__main__':main()
