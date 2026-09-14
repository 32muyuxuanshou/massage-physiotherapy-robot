import argparse,json
from pathlib import Path
import numpy as np
from .execution_guard import require_master_authorization
from .formal_identity import load_formal_rows
from .hashing import array_record,file_sha
from .k0_data_features import extract as extract_k0_features
from .txyz_fresh_process_runner import fit

PRIMARY_RUNS=('RUN_B','RUN_C','RUN_D','RUN_E','RUN_F')

def load_sam_runs(paths,expected_ids):
 runs={}
 for path in paths:
  meta=json.loads(Path(path).read_text());run_id=meta['run_id']
  if run_id in runs or run_id not in PRIMARY_RUNS:raise RuntimeError('SAM_COHORT_RUN_ID_INVALID')
  rows={row['frame_id']:row for row in meta['rows']}
  if set(rows)!=expected_ids or len(rows)!=len(expected_ids):raise RuntimeError(f'SAM_COHORT_FRAME_IDENTITY_MISMATCH:{run_id}')
  runs[run_id]=(meta,rows)
 if set(runs)!=set(PRIMARY_RUNS):raise RuntimeError('SAM_COHORT_B_TO_F_INCOMPLETE')
 return runs

def execute(replay_manifest,sam_paths,formal_manifest,pointcloud_manifest,workers=-1):
 replay=json.loads(Path(replay_manifest).read_text());replay_rows={row['frame_id']:row for row in replay['rows']};formal_ids={fid for fid,_ in load_formal_rows(formal_manifest)}
 if set(replay_rows)!=formal_ids or len(replay_rows)!=45:raise RuntimeError('REPLAY_FORMAL_FRAME_IDENTITY_MISMATCH')
 pointcloud={row['frame_id']:row for row in json.loads(Path(pointcloud_manifest).read_text())['rows']}
 if set(pointcloud)!=formal_ids:raise RuntimeError('POINTCLOUD_FORMAL_FRAME_IDENTITY_MISMATCH')
 sam_runs=load_sam_runs(sam_paths,formal_ids);rows=[]
 for fid in sorted(formal_ids):
  replay_row=replay_rows[fid]
  if file_sha(replay_row['points_npz'])!=replay_row['points_sha256'] or file_sha(replay_row['anchors_npz'])!=replay_row['anchors_sha256']:raise RuntimeError(f'RUN_A_ACTUAL_ASSET_HASH_MISMATCH:{fid}')
  points=np.load(replay_row['points_npz'])['points'];historical_anchors=np.load(replay_row['anchors_npz'])['anchors'];data_features=extract_k0_features(pointcloud[fid]['depth'],pointcloud[fid]['mask'],pointcloud[fid]['depth_sha256'],pointcloud[fid]['mask_sha256'])
  reference=fit(points,historical_anchors,workers);reference.update({'run_id':'RUN_A','role':'HISTORICAL_RECONSTRUCTED_REFERENCE_ONLY','pointcloud_hash':array_record(points)['sha256'],'anchor_hash':array_record(historical_anchors)['sha256'],'model_state_hash':None,'data_features':data_features})
  primary=[]
  for run_id in PRIMARY_RUNS:
   meta,sam_rows=sam_runs[run_id];sam_row=sam_rows[fid]
   if file_sha(sam_row['arrays_npz'])!=sam_row['arrays_npz_sha256']:raise RuntimeError(f'SAM_COHORT_ARRAY_FILE_HASH_MISMATCH:{run_id}:{fid}')
   arrays=np.load(sam_row['arrays_npz']);anchors=arrays['anchors'];anchor_hash=array_record(anchors)['sha256']
   if anchor_hash!=sam_row['anchors']['sha256']:raise RuntimeError(f'SAM_COHORT_ANCHOR_ARRAY_HASH_MISMATCH:{run_id}:{fid}')
   before=sam_row['model_state_before_frame']['model_state_sha256'];after=sam_row['model_state_after_frame']['model_state_sha256']
   if before!=after or before!=meta['model_state_sha256']:raise RuntimeError(f'SAM_COHORT_MODEL_STATE_MISMATCH:{run_id}:{fid}')
   result=fit(points,anchors,workers);result.update({'run_id':run_id,'role':'PRIMARY_CONTROLLED_COHORT','pointcloud_hash':array_record(points)['sha256'],'anchor_hash':anchor_hash,'model_state_hash':before,'data_features':data_features});primary.append(result)
  rows.append({'frame_id':fid,'historical_reference':reference,'runs':primary})
 return {'status':'PASS_SAM_COHORT_TXYZ_EXECUTION','scientific_question':'stability of frozen Txyz diagnostics under controlled SAM rerun anchor variation','historical_reference':'RUN_A is reported but excluded from primary stability classification','primary_runs':list(PRIMARY_RUNS),'frame_count':len(rows),'rows':rows}

def main():
 p=argparse.ArgumentParser();p.add_argument('--authorized-formal',action='store_true');p.add_argument('--replay-manifest',type=Path,required=True);p.add_argument('--sam-runs',type=Path,nargs='+',required=True);p.add_argument('--formal-manifest',type=Path,required=True);p.add_argument('--pointcloud-manifest',type=Path,required=True);p.add_argument('--workers',type=int,default=-1);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if not a.authorized_formal:raise RuntimeError('FORMAL_RUN_REQUIRES_MASTER_ORCHESTRATOR_GO')
 require_master_authorization();a.output.write_text(json.dumps(execute(a.replay_manifest,a.sam_runs,a.formal_manifest,a.pointcloud_manifest,a.workers),indent=2)+'\n')
if __name__=='__main__':main()
