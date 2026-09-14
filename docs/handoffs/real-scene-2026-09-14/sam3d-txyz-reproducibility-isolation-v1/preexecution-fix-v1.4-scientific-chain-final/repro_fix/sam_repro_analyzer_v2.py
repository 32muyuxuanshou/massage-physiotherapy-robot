import argparse,itertools,json
from pathlib import Path
import numpy as np
from .hashing import file_sha
from .sam_repro_analyzer import compare_arrays,distribution

def array_from_npz(path,key):
 z=np.load(path);return z[key] if key in z else z[z.files[0]]
def load_new_run(path):
 meta=json.loads(Path(path).read_text());return meta,{x['frame_id']:(x,np.load(x['arrays_npz'])) for x in meta['rows']}
def historical_anchor_comparisons(freeze_path,replay_manifest_path,new_paths):
 freeze=json.loads(Path(freeze_path).read_text());replay=json.loads(Path(replay_manifest_path).read_text());frozen={x['frame_id']:x for x in freeze['rows']};historical={x['frame_id']:x for x in replay['rows']};rows=[]
 for path in new_paths:
  meta,new=load_new_run(path)
  for fid,(new_row,new_arrays) in new.items():
   source=historical[fid];assert file_sha(source['anchors_npz'])==frozen[fid]['anchors_sha256'];old=array_from_npz(source['anchors_npz'],'anchors');drift=np.linalg.norm(old-new_arrays['anchors'],axis=-1)*1000;rows.append({'frame_id':fid,'against':meta['run_id'],'anchors':distribution(drift),'historical_fields_available':['anchors'],'historical_fields_unavailable':['vertices','cam_t','prepared_tensor','cam_int','model_state']})
 return rows
def cohort_comparisons(paths):
 loaded=[load_new_run(x) for x in paths];rows=[]
 for (am,a),(bm,b) in itertools.combinations(loaded,2):
  for fid,(ar,aa) in a.items():
   br,ba=b[fid];a_before=ar['model_state_before_frame']['model_state_sha256'];a_after=ar['model_state_after_frame']['model_state_sha256'];b_before=br['model_state_before_frame']['model_state_sha256'];b_after=br['model_state_after_frame']['model_state_sha256'];rows.append({'frame_id':fid,'pair':[am['run_id'],bm['run_id']],**compare_arrays(aa,ba),'exact':{'vertices':ar['pred_vertices']['sha256']==br['pred_vertices']['sha256'],'anchors':ar['anchors']['sha256']==br['anchors']['sha256'],'raw_rgb_file':ar['raw_rgb_file_sha256']==br['raw_rgb_file_sha256'],'decoded_rgb':ar['decoded_rgb']['sha256']==br['decoded_rgb']['sha256'],'raw_mask_file':ar['raw_mask_file_sha256']==br['raw_mask_file_sha256'],'decoded_mask':ar['decoded_mask']['sha256']==br['decoded_mask']['sha256'],'bbox':ar['bbox']['sha256']==br['bbox']['sha256'],'prepared_tensor':ar['prepared_tensor']['sha256']==br['prepared_tensor']['sha256'],'cam_int':ar['cam_int']['sha256']==br['cam_int']['sha256'],'model_state':am['model_state_sha256']==bm['model_state_sha256']==a_before==a_after==b_before==b_after,'model_state_unchanged_within_frame':a_before==a_after and b_before==b_after,'environment_fingerprint':am.get('environment_fingerprint')==bm.get('environment_fingerprint')}})
 return rows
def summarize(rows):
 return {'comparisons':len(rows),'vertices_max_drift':distribution([x['vertices']['max_mm'] for x in rows]),'anchors_max_drift':distribution([x['anchors']['max_mm'] for x in rows]),'cam_t_norm_drift':distribution([x['cam_t']['norm_mm'] for x in rows]),'exact_hash_matches':{k:sum(x['exact'][k] for x in rows) for k in rows[0]['exact']}}
def analyze(freeze,replay,new_paths):
 cohort=cohort_comparisons(new_paths);input_fields=('raw_rgb_file','decoded_rgb','raw_mask_file','decoded_mask','bbox','prepared_tensor','cam_int');status='MODEL_STATE_REPRODUCIBILITY_HARD_BLOCK' if any(not x['exact']['model_state'] or not x['exact']['model_state_unchanged_within_frame'] for x in cohort) else 'ENVIRONMENT_FINGERPRINT_MISMATCH' if any(not x['exact']['environment_fingerprint'] for x in cohort) else 'SAM_INPUT_IDENTITY_MISMATCH' if any(any(not x['exact'][field] for field in input_fields) for x in cohort) else 'PASS_SAM_REPRODUCIBILITY_ANALYSIS';return {'status':status,'complete_input_identity_fields':list(input_fields),'historical_evidence_scope':'ANCHORS_ONLY_RECONSTRUCTED_CANONICAL','historical_anchor_comparisons':historical_anchor_comparisons(freeze,replay,new_paths),'new_controlled_cohort':[Path(x).stem for x in new_paths],'new_cohort_pairwise':cohort,'new_cohort_summary':summarize(cohort)}
def main():
 p=argparse.ArgumentParser();p.add_argument('--run-a-freeze',type=Path,required=True);p.add_argument('--replay-manifest',type=Path,required=True);p.add_argument('--cohort',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(analyze(a.run_a_freeze,a.replay_manifest,a.cohort),indent=2)+'\n')
if __name__=='__main__':main()
