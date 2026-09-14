import argparse,json
from pathlib import Path
import numpy as np

def distribution(values):
 x=np.asarray(values,float);return {'mean_mm':float(x.mean()),'median_mm':float(np.median(x)),'p90_mm':float(np.percentile(x,90)),'p95_mm':float(np.percentile(x,95)),'max_mm':float(x.max())}
def compare_arrays(a,b):
 va,ca,aa=a['vertices'],a['cam_t'],a['anchors'];vb,cb,ab=b['vertices'],b['cam_t'],b['anchors']
 vertex=np.linalg.norm(va-vb,axis=-1)*1000;anchor=np.linalg.norm(aa-ab,axis=-1)*1000;delta=(cb-ca)*1000
 return {'vertices':distribution(vertex),'anchors':distribution(anchor),'cam_t':{'dx_mm':float(delta[0]),'dy_mm':float(delta[1]),'dz_mm':float(delta[2]),'norm_mm':float(np.linalg.norm(delta))}}
def load_run(path):
 meta=json.loads(Path(path).read_text());return meta,{x['frame_id']:(x,np.load(x['arrays_npz'])) for x in meta['rows']}
def analyze(run_a_path,other_paths):
 a_meta,a=load_run(run_a_path);comparisons=[];hash_counts={k:0 for k in ('vertices','anchors','prepared_tensor','cam_int','model_state')};total=0
 for path in other_paths:
  b_meta,b=load_run(path)
  if b_meta['mode']=='CONTROLLED' and b_meta['model_state_sha256']!=a_meta['model_state_sha256']:raise RuntimeError('MODEL_STATE_REPRODUCIBILITY_HARD_BLOCK')
  for fid,(ar,aa) in a.items():
   br,ba=b[fid];row={'frame_id':fid,'against':b_meta['run_id'],**compare_arrays(aa,ba),'exact':{'vertices':ar['pred_vertices']['sha256']==br['pred_vertices']['sha256'],'anchors':ar['anchors']['sha256']==br['anchors']['sha256'],'prepared_tensor':ar['prepared_tensor']['sha256']==br['prepared_tensor']['sha256'],'cam_int':ar['cam_int']['sha256']==br['cam_int']['sha256'],'model_state':a_meta['model_state_sha256']==b_meta['model_state_sha256']}};comparisons.append(row);total+=1
   for key,value in row['exact'].items():hash_counts[key]+=int(value)
 summary={}
 for target in ('vertices','anchors'):
  vals=[x[target]['max_mm'] for x in comparisons];summary[target+'_per_comparison_max_drift']=distribution(vals)
 summary['cam_t_norm']=distribution([x['cam_t']['norm_mm'] for x in comparisons]);summary['exact_hash_matches']={k:{'matches':v,'comparisons':total,'rate':v/total} for k,v in hash_counts.items()}
 return {'canonical_run_a':str(run_a_path),'comparisons':comparisons,'summary':summary}
def main():
 p=argparse.ArgumentParser();p.add_argument('--run-a',type=Path,required=True);p.add_argument('--others',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(analyze(a.run_a,a.others),indent=2)+'\n')
if __name__=='__main__':main()
