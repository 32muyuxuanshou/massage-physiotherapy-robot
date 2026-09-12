import hashlib,json
import numpy as np
from .hashing import array_record,aggregate
from pathlib import Path
import argparse,subprocess,sys
def tensor_record(key,tensor):
 a=tensor.detach().cpu().contiguous().numpy();r=array_record(a);r['key']=key;return r
def audit_model(model,missing_keys,unexpected_keys,forward_used_trainable=None):
 params=dict(model.named_parameters());buffers=dict(model.named_buffers());state=dict(model.state_dict());missing=[]
 for key in missing_keys:
  obj=params.get(key,buffers.get(key));exists_p=key in params;exists_b=key in buffers;missing.append({'key':key,'exists_in_named_parameters':exists_p,'exists_in_named_buffers':exists_b,'requires_grad':bool(obj.requires_grad) if exists_p else None,'dtype':str(obj.dtype) if obj is not None else None,'shape':list(obj.shape) if obj is not None else None,'value_sha256':tensor_record(key,obj)['sha256'] if obj is not None else None,'classification':'TRAINABLE_PARAMETER' if exists_p else 'BUFFER' if exists_b else 'UNRESOLVED'})
 state_records=[tensor_record(k,v) for k,v in state.items()];param_records=[tensor_record(k,v) for k,v in params.items() if v.requires_grad];buffer_records=[tensor_record(k,v) for k,v in buffers.items()];used=set(forward_used_trainable or []);hard=[x['key'] for x in missing if x['classification']=='TRAINABLE_PARAMETER' and (not used or x['key'] in used)]
 return {'missing_keys':missing,'unexpected_keys':list(unexpected_keys),'model_state_aggregate_sha256':aggregate(state_records),'trainable_parameter_aggregate_sha256':aggregate(param_records),'buffer_aggregate_sha256':aggregate(buffer_records),'hard_block_keys':hard,'status':'MODEL_LOAD_REPRODUCIBILITY_HARD_BLOCK' if hard else 'PASS_MODEL_LOAD_AUDIT'}
def fingerprints_equal(audits):return len({(x['model_state_aggregate_sha256'],x['trainable_parameter_aggregate_sha256'],x['buffer_aggregate_sha256']) for x in audits})==1

def load_and_audit(sam_repo,checkpoint,mhr,output):
 import torch
 sys.path.insert(0,str(sam_repo));from sam_3d_body import load_sam_3d_body
 model,_=load_sam_3d_body(str(checkpoint),device='cuda',mhr_path=str(mhr));raw=torch.load(checkpoint,map_location='cpu',weights_only=False);state=raw.get('state_dict',raw.get('model',raw));model_keys=set(model.state_dict());checkpoint_keys=set(state);missing=sorted(model_keys-checkpoint_keys);unexpected=sorted(checkpoint_keys-model_keys);result=audit_model(model,missing,unexpected);Path(output).write_text(json.dumps(result,indent=2)+'\n');return result
def run_fresh(a):
 rows=[]
 for i in range(a.runs):
  out=a.output.with_suffix(f'.run{i}.json');subprocess.run([sys.executable,'-m','repro_fix.model_load_auditor','--worker','--sam-repo',str(a.sam_repo),'--checkpoint',str(a.checkpoint),'--mhr',str(a.mhr),'--output',str(out)],check=True);rows.append(json.loads(out.read_text()));out.unlink()
 stable=fingerprints_equal(rows);hard=any(x['status']=='MODEL_LOAD_REPRODUCIBILITY_HARD_BLOCK' for x in rows);result={'fresh_processes':a.runs,'fingerprints_equal':stable,'runs':rows,'status':'MODEL_LOAD_REPRODUCIBILITY_HARD_BLOCK' if hard or not stable else 'PASS_MODEL_LOAD_REPRODUCIBILITY'};a.output.write_text(json.dumps(result,indent=2)+'\n');return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--runs',type=int,default=5);p.add_argument('--sam-repo',type=Path,required=True);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--mhr',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.worker:load_and_audit(a.sam_repo,a.checkpoint,a.mhr,a.output)
 else:run_fresh(a)
if __name__=='__main__':main()
