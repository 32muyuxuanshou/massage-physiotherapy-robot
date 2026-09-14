import argparse,itertools,json
from pathlib import Path
import numpy as np
from .sam_repro_analyzer import compare_arrays

def load_order_run(path):
 meta=json.loads(Path(path).read_text());rows={}
 for row in meta['rows']:
  rows[row['frame_id']]={'prepared_tensor_hash':row['prepared_tensor']['sha256'],'cam_int_hash':row['cam_int']['sha256'],'model_state_before':row['model_state_before_frame'],'model_state_after':row['model_state_after_frame'],'arrays':np.load(row['arrays_npz'])}
 return meta,rows
def analyze_paths(paths):
 runs={}
 for path in paths:
  meta,rows=load_order_run(path);runs[meta['run_id']]=rows
 return compare_order_runs(runs)
def compare_order_runs(runs):
 pairs=[]
 for a,b in itertools.combinations(runs,2):
  for fid in sorted(set(runs[a])&set(runs[b])):
   left,right=runs[a][fid],runs[b][fid];input_equal=left['prepared_tensor_hash']==right['prepared_tensor_hash'] and left['cam_int_hash']==right['cam_int_hash'];mutation=left['model_state_before']!=left['model_state_after'] or right['model_state_before']!=right['model_state_after'];same_before=left['model_state_before']==right['model_state_before'];drift=compare_arrays(left['arrays'],right['arrays']);different=drift['vertices']['max_mm']>0 or drift['anchors']['max_mm']>0 or drift['cam_t']['norm_mm']>0
   status='INPUT_IDENTITY_MISMATCH' if not input_equal else 'MODEL_STATE_MUTATION' if mutation or not same_before else 'FRAME_ORDER_DEPENDENCE' if different else 'NO_ORDER_DEPENDENCE';pairs.append({'frame_id':fid,'pair':[a,b],'status':status,'input_equal':input_equal,'model_state_before_equal':same_before,'drift':drift})
 priority=('INPUT_IDENTITY_MISMATCH','MODEL_STATE_MUTATION','FRAME_ORDER_DEPENDENCE');status=next((x for x in priority if any(r['status']==x for r in pairs)),'PASS_NO_FRAME_ORDER_DEPENDENCE');return {'comparisons':pairs,'status':status}
def main():
 p=argparse.ArgumentParser();p.add_argument('--runs',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(analyze_paths(a.runs),indent=2)+'\n')
if __name__=='__main__':main()
