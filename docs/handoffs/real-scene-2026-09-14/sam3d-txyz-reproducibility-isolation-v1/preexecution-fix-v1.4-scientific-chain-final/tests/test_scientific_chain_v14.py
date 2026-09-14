import copy,json,tempfile,unittest
from pathlib import Path
import cv2,numpy as np
from repro_fix.feature_stability_runner import characterize,extractor_map
from repro_fix.hashing import array_record,file_sha
from repro_fix.pointcloud_manifest import build as build_pointcloud,verify as verify_pointcloud
from repro_fix.run_a_freeze import build as build_run_a,verify as verify_run_a
from repro_fix.run_reproducibility_isolation_v1 import require_clean_output_root
from repro_fix.sam_cohort_txyz_runner import execute as execute_cohort_txyz
from repro_fix.sam_repro_analyzer_v2 import analyze as analyze_sam
from repro_fix.txyz_fresh_process_runner import fit

ROOT=Path(__file__).parents[1]

def make_replay(root):
 points=root/'points.npz';anchors=root/'anchors.npz';np.savez(points,points=np.array([[0.,0.,1.],[.1,0,1.],[0,.1,1.]]));np.savez(anchors,anchors=np.array([[0.,0.,1.],[.1,0,1.],[0,.1,1.]]));rows=[{'frame_id':f'f{i:02d}','points_npz':str(points),'anchors_npz':str(anchors),'points_sha256':file_sha(points),'anchors_sha256':file_sha(anchors)} for i in range(45)];manifest=root/'replay.json';manifest.write_text(json.dumps({'rows':rows}));return manifest,points,anchors

class ScientificChainV14(unittest.TestCase):
 def test_01_run_a_actual_npz_mutation_stops(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);manifest,points,_=make_replay(root);freeze=build_run_a(manifest);self.assertEqual(verify_run_a(freeze,manifest)['points_verified'],45);np.savez(points,points=np.ones((1,3)))
   with self.assertRaisesRegex(RuntimeError,'RUN_A_ACTUAL_ASSET_HASH_MISMATCH'):verify_run_a(freeze,manifest)

 def test_02_pointcloud_manifest_is_derived_and_bound(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);sequences=root/'sequences';calibs=root/'calibs';(calibs/'intrinsics'/'0').mkdir(parents=True);np.save(calibs/'intrinsics'/'0'/'pointcloud_table.npy',np.zeros((2,2,2),np.float32));(calibs/'intrinsics'/'0'/'calibration.json').write_text('{}');rows=[]
   for i in range(45):
    frame=sequences/'seq'/f't{i:04d}';frame.mkdir(parents=True);cv2.imwrite(str(frame/'k0.depth.png'),np.full((2,2),1000,np.uint16));cv2.imwrite(str(frame/'k0.person_mask.jpg'),np.full((2,2),255,np.uint8));rows.append({'frame_id':f'f{i:02d}','sequence':'seq','frame':frame.name})
   formal=root/'formal.json';formal.write_text(json.dumps({'rows':rows}));snapshot=build_pointcloud(formal,sequences,calibs);self.assertEqual(verify_pointcloud(snapshot,formal,sequences,calibs)['frame_count'],45);self.assertEqual({x['frame_id'] for x in snapshot['rows']},{x['frame_id'] for x in rows});cv2.imwrite(snapshot['rows'][0]['depth'],np.full((2,2),999,np.uint16))
   with self.assertRaisesRegex(RuntimeError,'POINTCLOUD_FORMAL_BINDING_MISMATCH'):verify_pointcloud(snapshot,formal,sequences,calibs)

 def test_03_txyz_trace_has_all_numeric_diagnostics(self):
  result=fit(np.array([[0.,0.,1.],[.1,0,1.]]),np.array([[0.,0.,1.],[.1,0,1.]]),1);self.assertEqual(set(result['features']),{'convergence_ratio','direction_consistency','oscillation','raw_residual_median_mm','residual_mad_mm','residual_p90_mm','residual_p95_mm'});self.assertIn('retained_residual_median_m',result['trace'][-1])

 def test_04_sam_bf_anchor_chain_and_contract_coverage(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);replay,points,anchors=make_replay(root);formal=root/'formal.json';formal.write_text(json.dumps({'rows':[{'frame_id':f'f{i:02d}','sequence':'seq','frame':f't{i:04d}'} for i in range(45)]}));depth=root/'depth.png';mask=root/'mask.jpg';cv2.imwrite(str(depth),np.full((2,2),1000,np.uint16));cv2.imwrite(str(mask),np.full((2,2),255,np.uint8));pointcloud=root/'pointcloud.json';pointcloud.write_text(json.dumps({'rows':[{'frame_id':f'f{i:02d}','depth':str(depth),'mask':str(mask),'depth_sha256':file_sha(depth),'mask_sha256':file_sha(mask)} for i in range(45)]}));arrays=root/'sam.npz';np.savez(arrays,vertices=np.zeros((3,3)),cam_t=np.zeros(3),anchors=np.load(anchors)['anchors']);sam_paths=[]
   for run in 'BCDEF':
    path=root/f'RUN_{run}.json';rows=[{'frame_id':f'f{i:02d}','arrays_npz':str(arrays),'arrays_npz_sha256':file_sha(arrays),'anchors':array_record(np.load(arrays)['anchors']),'model_state_before_frame':{'model_state_sha256':'model'},'model_state_after_frame':{'model_state_sha256':'model'}} for i in range(45)];path.write_text(json.dumps({'run_id':f'RUN_{run}','model_state_sha256':'model','rows':rows}));sam_paths.append(path)
   result=execute_cohort_txyz(replay,sam_paths,formal,pointcloud,1);self.assertEqual(result['status'],'PASS_SAM_COHORT_TXYZ_EXECUTION');self.assertEqual(result['frame_count'],45);cohort=root/'cohort.json';cohort.write_text(json.dumps(result));characterized=characterize(cohort,ROOT/'FEATURE_STABILITY_CONTRACT_V1_4.json');self.assertEqual(characterized['status'],'PASS_FEATURE_STABILITY_CHARACTERIZATION');self.assertTrue(characterized['coverage']['exact']);self.assertEqual(characterized['coverage']['required_count'],len(extractor_map()))

 def test_05_contract_coverage_fails_closed(self):
  contract=json.loads((ROOT/'FEATURE_STABILITY_CONTRACT_V1_4.json').read_text());contract['features']['unimplemented_feature']={'type':'COUNT','stable':{'max_abs_range':0,'max_noise_ratio':0,'min_icc_a1':1},'caution':{'max_abs_range':1,'max_noise_ratio':.01,'min_icc_a1':.99}}
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);payload=fit([[0,0,0]],[[0,0,0]],1);payload.update({'run_id':'RUN_B','pointcloud_hash':'p','anchor_hash':'a','model_state_hash':'m','data_features':{'valid_depth_pixels':1,'depth_support_fraction':1.,'depth_hole_ratio':0.,'support_left_right_balance':1.,'support_top_bottom_balance':1.}});rows=[]
   for frame in ('f1','f2'):rows.append({'frame_id':frame,'runs':[{**copy.deepcopy(payload),'run_id':f'RUN_{run}'} for run in 'BCDEF']})
   cohort=root/'cohort.json';cohort.write_text(json.dumps({'status':'PASS_SAM_COHORT_TXYZ_EXECUTION','primary_runs':[f'RUN_{run}' for run in 'BCDEF'],'rows':rows}));contract_path=root/'contract.json';contract_path.write_text(json.dumps(contract));self.assertEqual(characterize(cohort,contract_path)['status'],'FEATURE_STABILITY_CONTRACT_COVERAGE_FAILED')

 def test_06_sam_complete_input_identity_catches_raw_mask(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);hist=root/'hist.npz';new=root/'new.npz';np.savez(hist,anchors=np.zeros((2,3)));np.savez(new,vertices=np.zeros((2,3)),cam_t=np.zeros(3),anchors=np.zeros((2,3)));fid='f';freeze=root/'freeze.json';replay=root/'replay.json';freeze.write_text(json.dumps({'rows':[{'frame_id':fid,'anchors_sha256':file_sha(hist)}]}));replay.write_text(json.dumps({'rows':[{'frame_id':fid,'anchors_npz':str(hist)}]}))
   def row(mask):return {'frame_id':fid,'arrays_npz':str(new),'pred_vertices':array_record(np.zeros((2,3))),'anchors':array_record(np.zeros((2,3))),'raw_rgb_file_sha256':'rgb','decoded_rgb':array_record(np.zeros((1,1,3),np.uint8)),'raw_mask_file_sha256':mask,'decoded_mask':array_record(np.ones((1,1),np.uint8)),'bbox':array_record(np.zeros((1,4),np.float32)),'prepared_tensor':array_record(np.zeros(1)),'cam_int':array_record(np.eye(3)),'model_state_before_frame':{'model_state_sha256':'m'},'model_state_after_frame':{'model_state_sha256':'m'}}
   paths=[]
   for run,mask_value in (('B','mask-a'),('C','mask-b')):
    path=root/f'{run}.json';path.write_text(json.dumps({'run_id':f'RUN_{run}','model_state_sha256':'m','environment_fingerprint':{},'rows':[row(mask_value)]}));paths.append(path)
   self.assertEqual(analyze_sam(freeze,replay,paths)['status'],'SAM_INPUT_IDENTITY_MISMATCH')

 def test_07_output_root_must_be_clean(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'output';root.mkdir();(root/'old.json').write_text('{}')
   with self.assertRaisesRegex(RuntimeError,'OUTPUT_ROOT_MUST_BE_NEW_OR_EMPTY'):require_clean_output_root(root)

 def test_08_output_root_must_be_outside_reviewed_delivery(self):
  with self.assertRaisesRegex(RuntimeError,'OUTPUT_ROOT_MUST_BE_OUTSIDE_REVIEWED_DELIVERY'):require_clean_output_root(ROOT/'formal-output-must-not-be-created')

if __name__=='__main__':unittest.main()
