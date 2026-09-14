import argparse,json
from pathlib import Path
import numpy as np
from .feature_stability import classify
def load_payloads(batch_summary):
 batch=json.loads(Path(batch_summary).read_text());return [(row['frame_id'],json.loads(Path(row['summary']).read_text())['runs']) for row in batch['rows']]
def matrix(payloads,fn):return np.asarray([[fn(run) for run in runs] for _,runs in payloads])
def characterize(batch_summary,contract_path):
 payloads=load_payloads(batch_summary);contract=json.loads(Path(contract_path).read_text())['features'];extractors={
 'tx_mm':lambda r:r['translation_values'][0]*1000,'ty_mm':lambda r:r['translation_values'][1]*1000,'tz_mm':lambda r:r['translation_values'][2]*1000,'translation_norm_mm':lambda r:np.linalg.norm(r['translation_values'])*1000,
 'iteration_step_vectors_mm':lambda r:np.asarray([x['step_values'] for x in r['trace']])*1000,'iteration_step_norms_mm':lambda r:np.asarray([np.linalg.norm(x['step_values'])*1000 for x in r['trace']]),
 'trim_threshold_mm':lambda r:r['trace'][-1]['trim_threshold_raw']*1000,'retained_count':lambda r:r['trace'][-1]['retained_count'],'raw_correspondence_count':lambda r:r['trace'][-1]['raw_correspondence_count'],'fallback':lambda r:r['fallback'],'nearest_hash':lambda r:r['trace'][-1]['nearest']['sha256'],'keep_hash':lambda r:r['trace'][-1]['keep']['sha256']}
 results={}
 for name,fn in extractors.items():
  values=matrix(payloads,fn);feature_contract=contract[name]
  if name=='iteration_step_norms_mm':
   per={f'iter{i+1}':classify(values[:,:,i],feature_contract) for i in range(values.shape[-1])};rank={'STABLE':0,'CAUTION':1,'UNSTABLE':2};status=max((x['status'] for x in per.values()),key=rank.get);results[name]={'per_iteration':per,'status':status}
  else:results[name]=classify(values,feature_contract)
 counts={x:sum(v['status']==x for v in results.values()) for x in ('STABLE','CAUTION','UNSTABLE')};return {'status':'PASS_FEATURE_STABILITY_CHARACTERIZATION','outcome_fields_read':False,'features':results,'counts':counts}
def main():
 p=argparse.ArgumentParser();p.add_argument('--batch-summary',type=Path,required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(characterize(a.batch_summary,a.contract),indent=2)+'\n')
if __name__=='__main__':main()
