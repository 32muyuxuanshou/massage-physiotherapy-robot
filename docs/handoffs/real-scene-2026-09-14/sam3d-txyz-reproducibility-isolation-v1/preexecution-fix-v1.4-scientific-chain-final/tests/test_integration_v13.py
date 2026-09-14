import json,tempfile,unittest
from pathlib import Path
import cv2,numpy as np
from repro_fix.hashing import array_record,file_sha
from repro_fix.input_source_snapshot import build as build_snapshot
from repro_fix.runtime_asset_verifier import tree_sha,bundle_sha,verify_assets
from repro_fix.sam_repro_analyzer_v2 import analyze
from repro_fix.frame_order_analyzer import analyze_paths
from repro_fix.run_reproducibility_isolation_v1 import STAGES,PASS,child_environment,execute_stages
from repro_fix.execution_guard import require_master_authorization

ROOT=Path(__file__).parents[1]
def sam_record(fid,npz):
 z=np.load(npz);return {'frame_id':fid,'arrays_npz':str(npz),'arrays_npz_sha256':file_sha(npz),'pred_vertices':array_record(z['vertices']),'anchors':array_record(z['anchors']),'raw_rgb_file_sha256':'rgb','decoded_rgb':array_record(np.zeros((1,1,3),np.uint8)),'raw_mask_file_sha256':'mask','decoded_mask':array_record(np.ones((1,1),np.uint8)),'bbox':array_record(np.zeros((1,4),np.float32)),'prepared_tensor':array_record(np.zeros(1)),'cam_int':array_record(np.eye(3)),'model_state_before_frame':{'model_state_sha256':'m'},'model_state_after_frame':{'model_state_sha256':'m'}}
def sam_meta(run,fid,npz):return {'run_id':run,'mode':'CONTROLLED','model_state_sha256':'m','rows':[sam_record(fid,npz)]}

class Integration(unittest.TestCase):
 def test_01_historical_boundary_is_anchor_only(self):
  b=json.loads((ROOT/'SAM_REPRODUCIBILITY_EVIDENCE_BOUNDARY_V1_4.json').read_text());self.assertEqual(b['historical_run_a']['permitted_comparison'],'anchors_only_and_reconstructed_txyz_reference');self.assertIn('full_vertices',b['historical_run_a']['unavailable'])
 def test_02_historical_analyzer_real_schema(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);hist=t/'hist.npz';new=t/'new.npz';np.savez(hist,anchors=np.zeros((2,3)));np.savez(new,vertices=np.zeros((2,3)),cam_t=np.zeros(3),anchors=np.zeros((2,3)));fid='f';freeze={'rows':[{'frame_id':fid,'anchors_sha256':file_sha(hist)}]};replay={'rows':[{'frame_id':fid,'anchors_npz':str(hist)}]};(t/'freeze.json').write_text(json.dumps(freeze));(t/'replay.json').write_text(json.dumps(replay));(t/'B.json').write_text(json.dumps(sam_meta('RUN_B',fid,new)));(t/'C.json').write_text(json.dumps(sam_meta('RUN_C',fid,new)));r=analyze(t/'freeze.json',t/'replay.json',[t/'B.json',t/'C.json']);self.assertEqual(r['historical_evidence_scope'],'ANCHORS_ONLY_RECONSTRUCTED_CANONICAL');self.assertIn('vertices',r['historical_anchor_comparisons'][0]['historical_fields_unavailable'])
 def test_03_new_cohort_pairwise_full_outputs(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);hist=t/'hist.npz';new=t/'new.npz';np.savez(hist,anchors=np.zeros((2,3)));np.savez(new,vertices=np.zeros((2,3)),cam_t=np.zeros(3),anchors=np.zeros((2,3)));fid='f';(t/'freeze.json').write_text(json.dumps({'rows':[{'frame_id':fid,'anchors_sha256':file_sha(hist)}]}));(t/'replay.json').write_text(json.dumps({'rows':[{'frame_id':fid,'anchors_npz':str(hist)}]}));[(t/f'{x}.json').write_text(json.dumps(sam_meta('RUN_'+x,fid,new))) for x in 'BC'];self.assertEqual(len(analyze(t/'freeze.json',t/'replay.json',[t/'B.json',t/'C.json'])['new_cohort_pairwise']),1)
 def test_04_frame_order_adapter_reads_real_json_npz(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);z=t/'x.npz';np.savez(z,vertices=np.zeros((1,3)),cam_t=np.zeros(3),anchors=np.zeros((1,3)));[(t/f'{x}.json').write_text(json.dumps(sam_meta(x,'f',z))) for x in ('O','R')];self.assertEqual(analyze_paths([t/'O.json',t/'R.json'])['status'],'PASS_NO_FRAME_ORDER_DEPENDENCE')
 def test_05_frame_state_before_after_present(self):self.assertIn('model_state_before_frame',Path(ROOT/'repro_fix/sam_repro_runner.py').read_text());self.assertIn('model_state_after_frame',Path(ROOT/'repro_fix/sam_repro_runner.py').read_text())
 def test_06_parent_environment_fixed(self):
  _,settings=child_environment({'seed':7});self.assertEqual(settings['PYTHONHASHSEED'],'7');self.assertIn('CUBLAS_WORKSPACE_CONFIG',settings)
 def test_07_master_stage_order(self):self.assertEqual(STAGES[0],'model_load_unseeded');self.assertIn('sam_cohort_txyz',STAGES);self.assertEqual(STAGES[-1],'feature_stability')
 def test_08_master_runs_all_passed_stages(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);calls=[];items={}
   for stage in STAGES:
    out=t/f'{stage}.json';out.write_text(json.dumps({'status':next(iter(PASS[stage]))}));items[stage]=([stage],out)
   ledger=execute_stages(items,{},lambda cmd:calls.append(cmd[0]) or 0);self.assertEqual(len(ledger),len(STAGES));self.assertEqual(calls,list(STAGES))
 def test_09_master_stops_on_gate_failure(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);calls=[];items={}
   for stage in STAGES:
    out=t/f'{stage}.json';out.write_text(json.dumps({'status':'BAD' if stage=='pointcloud' else next(iter(PASS[stage]))}));items[stage]=([stage],out)
   ledger=execute_stages(items,{},lambda cmd:calls.append(cmd[0]) or 0);self.assertEqual(ledger[-1]['stage'],'pointcloud');self.assertNotIn('sam_controlled',calls)
 def test_10_asset_verifier_pass_and_mismatch(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);[(t/x).write_text(x) for x in ('ckpt','mhr','anchor','metric','manifest','txyz','cal')];repo=t/'repo';repo.mkdir();(repo/'a.py').write_text('x');helper=t/'helper';helper.mkdir();(helper/'behave_v2_io.py').write_text('h');repro=t/'repro';repro.mkdir();(repro/'x.py').write_text('x');paths={'official_checkpoint':t/'ckpt','mhr_model':t/'mhr','surface_anchors':t/'anchor','surface_metrics':t/'metric','sam3d_repo':repo,'v23_code':helper,'formal_manifest':t/'manifest','txyz_implementation':t/'txyz','calibration_root':t,'calibration_relative_files':['cal'],'repro_code_root':repro};obs={'official_checkpoint_sha256':file_sha(t/'ckpt'),'mhr_model_sha256':file_sha(t/'mhr'),'surface_anchors_sha256':file_sha(t/'anchor'),'surface_metrics_sha256':file_sha(t/'metric'),'sam3d_source_tree_sha256':tree_sha(repo),'v23_helper_code_sha256':file_sha(helper/'behave_v2_io.py')};gate={'formal_manifest_sha256':file_sha(t/'manifest'),'txyz_implementation_sha256':file_sha(t/'txyz'),'camera_calibration_bundle_sha256':bundle_sha(t,['cal']),'repro_code_tree_sha256':tree_sha(repro,('*.py',))};freeze={'assets':obs,'formal_runtime_gate':gate};self.assertEqual(verify_assets(paths,freeze)['status'],'PASS_RUNTIME_ASSET_FREEZE');freeze['assets']['mhr_model_sha256']='bad';self.assertEqual(verify_assets(paths,freeze)['status'],'ASSET_FREEZE_MISMATCH')
 def test_11_input_snapshot_hashes_rgb_mask(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);rows=[]
   for i in range(45):
    f=t/'seq'/str(i);f.mkdir(parents=True);cv2.imwrite(str(f/'k0.color.jpg'),np.zeros((2,2,3),np.uint8));cv2.imwrite(str(f/'k0.person_mask.jpg'),np.zeros((2,2),np.uint8));rows.append({'frame_id':f'f{i}','sequence':'seq','frame':str(i)})
   m=t/'m.json';m.write_text(json.dumps({'rows':rows}));self.assertIn('raw_rgb_file_sha256',build_snapshot(m,t)['rows'][0])
 def test_12_new_cohort_is_b_through_f(self):self.assertIn("'RUN_F'",(ROOT/'repro_fix/sam_repro_runner.py').read_text())
 def test_13_environment_embedded_in_sam(self):self.assertIn('environment_fingerprint',(ROOT/'repro_fix/sam_repro_runner.py').read_text())
 def test_14_model_auditor_requires_master_gate(self):self.assertIn('MASTER_ORCHESTRATOR_GO',(ROOT/'repro_fix/model_load_auditor.py').read_text())
 def test_15_unsaved_history_boundary_in_readme(self):self.assertIn('No code can recover data that was not saved',(ROOT/'README_PREEXECUTION_REPRO_FIX_V1_4_SCIENTIFIC_CHAIN_FINAL.md').read_text())
 def test_16_direct_formal_child_is_blocked(self):
  from unittest.mock import patch
  with patch.dict('os.environ',{},clear=True):
   with self.assertRaisesRegex(RuntimeError,'MASTER_ORCHESTRATOR'):require_master_authorization()
 def test_17_master_environment_authorizes_children(self):
  from unittest.mock import patch
  env,_=child_environment({'seed':7})
  with patch.dict('os.environ',env,clear=True):self.assertTrue(require_master_authorization())

if __name__=='__main__':unittest.main()
