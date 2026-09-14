import json,tempfile,unittest
from pathlib import Path
import cv2,numpy as np
from repro_fix.hashing import array_record
from repro_fix.feature_stability import icc_a1,continuous_stats,classify
from repro_fix.frame_order_runner import validate,build_orders
from repro_fix.model_load_auditor import audit_model,fingerprints_equal
from repro_fix.pointcloud_repro_runner import reconstruct,coordinator
from repro_fix.run_a_freeze import build,verify
from repro_fix.sam_repro_runner import prepared_tensor_record,output_records
from repro_fix.txyz_fresh_process_runner import fit,run_fresh
from repro_fix.txyz_same_process_runner import run_same_process_repeats
from repro_fix.txyz_repro_analyzer import analyze_runs
from repro_fix.sam_repro_analyzer import compare_arrays,distribution,analyze as analyze_sam
from repro_fix.sam_repro_runner import coordinator as sam_coordinator
from repro_fix.frame_order_execution_runner import make_order_manifest
from repro_fix.frame_order_analyzer import compare_order_runs
from repro_fix.pointcloud_repro_analyzer import analyze as analyze_pointcloud
from repro_fix.environment_fingerprint import apply_reproducibility_environment

ROOT=Path(__file__).parents[1]
DIST={'type':'DISTANCE_MM','stable':{'max_abs_range':.001,'max_noise_ratio':.01,'min_icc_a1':.99},'caution':{'max_abs_range':.02,'max_noise_ratio':.2,'min_icc_a1':.8}}

class FakeTensor:
 def __init__(self,a,requires_grad=False,device='cpu'):self.a=np.asarray(a);self.requires_grad=requires_grad;self.dtype=self.a.dtype;self.shape=self.a.shape;self.device=device
 def detach(self):return self
 def cpu(self):return self
 def contiguous(self):return self
 def numpy(self):return self.a
class Tiny:
 def __init__(self):self.weight=FakeTensor(np.ones(2),True);self.scale=FakeTensor(np.ones(1))
 def named_parameters(self):return [('weight',self.weight)]
 def named_buffers(self):return [('scale',self.scale)]
 def state_dict(self):return {'weight':self.weight,'scale':self.scale}

class Tests(unittest.TestCase):
 def test_01_hash_actual_bytes(self):self.assertNotEqual(array_record(np.array([1],np.float32))['sha256'],array_record(np.array([2],np.float32))['sha256'])
 def test_02_hash_dtype(self):self.assertNotEqual(array_record(np.array([1],np.float32))['sha256'],array_record(np.array([1],np.float64))['sha256'])
 def test_03_hash_layout_metadata(self):self.assertIn('strides',array_record(np.arange(6).reshape(2,3).T))
 def test_04_icc_perfect(self):self.assertAlmostEqual(icc_a1([[1,1,1],[2,2,2],[3,3,3]]),1)
 def test_05_icc_is_computed(self):self.assertTrue(np.isfinite(icc_a1([[1,1.1],[2,1.9],[4,4.2]])))
 def test_06_between_variation(self):self.assertGreater(continuous_stats([[1,1],[5,5]])['between_frame_sd'],0)
 def test_07_noise_ratio(self):self.assertIn('within_between_noise_ratio',continuous_stats([[1,1.1],[5,4.9]]))
 def test_08_stable(self):self.assertEqual(classify([[1,1],[2,2]],DIST)['status'],'STABLE')
 def test_09_caution(self):self.assertEqual(classify([[1,1.01],[2,2.01]],DIST)['status'],'CAUTION')
 def test_10_unstable(self):self.assertEqual(classify([[1,2],[2,4]],DIST)['status'],'UNSTABLE')
 def test_11_boolean_flip(self):self.assertEqual(classify([[True,False]],{'type':'BOOLEAN','stable':{'max_flip_rate':0}})['status'],'UNSTABLE')
 def test_12_hash_identity(self):self.assertEqual(classify([['a','a'],['b','b']],{'type':'HASH_IDENTITY','stable':{'identity_rate':1}})['status'],'STABLE')
 def test_13_outcome_leakage_block(self):
  with self.assertRaisesRegex(RuntimeError,'LEAKAGE'):classify([[1,1],[2,2]],DIST,outcomes=[0,1])
 def test_14_unit_contracts_differ(self):
  c=json.loads((ROOT/'FEATURE_STABILITY_CONTRACT_V1_2.json').read_text())['types'];self.assertNotEqual(c['DISTANCE_MM'],c['RATIO_0_1'])
 def test_15_txyz_trace_hashes(self):
  r=fit(np.array([[0.,0,0],[1,0,0]]),np.array([[0.,0,0],[1,0,0]]),1);self.assertIn('sha256',r['trace'][0]['nearest']);self.assertIn('sha256',r['trace'][0]['keep'])
 def test_16_workers_branches(self):self.assertEqual(fit([[0,0,0]],[[0,0,0]],1)['workers'],1);self.assertEqual(fit([[0,0,0]],[[0,0,0]],-1)['workers'],-1)
 def test_17_txyz_fresh_process(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);np.savez(t/'p.npz',points=np.array([[0.,0,0],[1,0,0]]));np.savez(t/'a.npz',anchors=np.array([[0.,0,0],[1,0,0]]));r=run_fresh(t/'p.npz',t/'a.npz',2,1,t/'o.json');self.assertEqual(len(r['runs']),2)
 def test_18_model_object_classification(self):
  r=audit_model(Tiny(),['weight','scale','ghost'],[]);self.assertEqual([x['classification'] for x in r['missing_keys']],['TRAINABLE_PARAMETER','BUFFER','UNRESOLVED'])
 def test_19_trainable_hard_block(self):self.assertEqual(audit_model(Tiny(),['weight'],[])['status'],'MODEL_LOAD_REPRODUCIBILITY_HARD_BLOCK')
 def test_20_model_fingerprint(self):
  a=audit_model(Tiny(),[],[]);b=audit_model(Tiny(),[],[]);self.assertTrue(fingerprints_equal([a,b]));self.assertIn('model_state_aggregate_sha256',a)
 def test_21_pointcloud_decoded_hashes(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);cv2.imwrite(str(t/'d.png'),np.array([[1000]],np.uint16));cv2.imwrite(str(t/'m.png'),np.array([[255]],np.uint8));np.save(t/'q.npy',np.array([[[0.,0.]]],np.float32));r=reconstruct(t/'d.png',t/'m.png',t/'q.npy');self.assertIn('sha256',r['decoded_depth']);self.assertIn('sha256',r['decoded_mask'])
 def test_22_pointcloud_fresh_process(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);cv2.imwrite(str(t/'d.png'),np.array([[1000]],np.uint16));cv2.imwrite(str(t/'m.png'),np.array([[255]],np.uint8));np.save(t/'q.npy',np.array([[[0.,0.]]],np.float32));(t/'x.json').write_text('{}');(t/'manifest.json').write_text(json.dumps({'rows':[{'frame_id':'f','depth':str(t/'d.png'),'mask':str(t/'m.png'),'pointcloud_table':str(t/'q.npy'),'calibration':str(t/'x.json')}]}));r=coordinator(t/'manifest.json',t/'out.json',2);self.assertEqual(r['status'],'POINTCLOUD_REPRODUCIBILITY_PASS')
 def test_23_sam_tensor_data_hash(self):
  a=prepared_tensor_record(FakeTensor(np.zeros(1)));b=prepared_tensor_record(FakeTensor(np.ones(1)));self.assertNotEqual(a['sha256'],b['sha256'])
 def test_24_sam_output_schema(self):self.assertEqual(set(output_records(np.zeros((2,3)),np.zeros(3),np.zeros((2,3)))),{'pred_vertices','pred_cam_t','anchors'})
 def test_25_sentinel_unique(self):self.assertEqual(len(validate(json.loads((ROOT/'FRAME_ORDER_TEST_SPEC_V1_2.json').read_text()))),7)
 def test_26_orders(self):self.assertEqual(set(build_orders(list('abcdefg'),7)),{'ORDER_ORIGINAL','ORDER_REVERSED','ORDER_RANDOM_FIXED_SEED'})
 def test_27_run_a_freeze(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'m.json';p.write_text(json.dumps({'rows':[{'frame_id':str(i),'points_sha256':'p'+str(i),'anchors_sha256':'a'+str(i)} for i in range(45)]}));f=build(p);self.assertTrue(verify(f,p));self.assertEqual(f['expected_frame_count'],45)
 def test_28_run_a_mutation_detected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'m.json';rows=[{'frame_id':str(i),'points_sha256':'p','anchors_sha256':'a'} for i in range(45)];p.write_text(json.dumps({'rows':rows}));f=build(p);rows[0]['points_sha256']='changed';p.write_text(json.dumps({'rows':rows}));
   with self.assertRaisesRegex(RuntimeError,'VIOLATION'):verify(f,p)
 def test_29_dataset_mask_boundary_retained(self):self.assertIn('dataset-mask-assisted', (ROOT/'README_PREEXECUTION_REPRO_FIX_V1_2_FINAL.md').read_text())
 def test_30_back_fail_closed(self):self.assertIn('BLOCKED_PENDING_BACK_REGION_DEFINITION',(ROOT/'README_PREEXECUTION_REPRO_FIX_V1_2_FINAL.md').read_text())
 def test_31_vector_component_path(self):
  x=np.zeros((2,3,2,3));r=classify(x,{**DIST,'type':'VECTOR_MM'});self.assertIn('iter1_x',r['details'])
 def test_32_vector_norm_path(self):
  x=np.zeros((2,3,1,3));r=classify(x,{**DIST,'type':'VECTOR_MM'});self.assertIn('iter1_norm',r['details'])
 def test_33_vector_worst_component(self):
  x=np.zeros((2,3,1,3));x[0,:,0,0]=[0,1,2];self.assertEqual(classify(x,{**DIST,'type':'VECTOR_MM'})['status'],'UNSTABLE')
 def test_34_same_process_twenty(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);np.savez(t/'p.npz',points=np.array([[0.,0,0.]]));np.savez(t/'a.npz',anchors=np.array([[0.,0,0.]]));self.assertEqual(len(run_same_process_repeats(t/'p.npz',t/'a.npz',20,1)['runs']),20)
 def test_35_same_process_loaded_once(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);np.savez(t/'p.npz',points=np.array([[0.,0,0.]]));np.savez(t/'a.npz',anchors=np.array([[0.,0,0.]]));self.assertTrue(run_same_process_repeats(t/'p.npz',t/'a.npz',2,1)['assets_loaded_once'])
 def test_36_first_divergence_none(self):
  r=fit([[0,0,0]],[[0,0,0]],1);self.assertTrue(analyze_runs([r,r])['all_equal'])
 def test_37_first_divergence_found(self):
  import copy;r=fit([[0,0,0]],[[0,0,0]],1);b=copy.deepcopy(r);b['trace'][0]['nearest']['sha256']='x';self.assertEqual(analyze_runs([r,b])['first_divergence']['object'],'iteration_1.nearest')
 def test_38_vertex_drift(self):
  a={'vertices':np.zeros((2,3)),'cam_t':np.zeros(3),'anchors':np.zeros((2,3))};b={k:v.copy() for k,v in a.items()};b['vertices'][0,0]=.001;self.assertEqual(compare_arrays(a,b)['vertices']['max_mm'],1)
 def test_39_anchor_drift(self):
  a={'vertices':np.zeros((2,3)),'cam_t':np.zeros(3),'anchors':np.zeros((2,3))};b={k:v.copy() for k,v in a.items()};b['anchors'][0,0]=.002;self.assertEqual(compare_arrays(a,b)['anchors']['max_mm'],2)
 def test_40_camt_drift(self):
  a={'vertices':np.zeros((2,3)),'cam_t':np.zeros(3),'anchors':np.zeros((2,3))};b={k:v.copy() for k,v in a.items()};b['cam_t'][2]=.003;self.assertEqual(compare_arrays(a,b)['cam_t']['norm_mm'],3)
 def test_41_frame_order_manifest_preserves_order(self):
  rows=[{'frame_id':x} for x in 'abc'];self.assertEqual([x['frame_id'] for x in make_order_manifest(rows,['c','a','b'])['rows']],['c','a','b'])
 def test_42_frame_order_same_process_design(self):self.assertIn('one loaded model',json.loads((ROOT/'FRAME_ORDER_TEST_SPEC_V1_2.json').read_text())['execution_design'])
 def test_43_frame_order_dependence(self):
  arr={'vertices':np.zeros((1,3)),'cam_t':np.zeros(3),'anchors':np.zeros((1,3))};row=lambda a:{'prepared_tensor_hash':'i','cam_int_hash':'k','model_state_hash':'m','arrays':a};changed={k:v.copy() for k,v in arr.items()};changed['vertices'][0,0]=.001;r=compare_order_runs({'A':{'f':row(arr)},'B':{'f':row(changed)}});self.assertEqual(r['status'],'FRAME_ORDER_DEPENDENCE')
 def test_44_model_state_mutation(self):
  arr={'vertices':np.zeros((1,3)),'cam_t':np.zeros(3),'anchors':np.zeros((1,3))};a={'prepared_tensor_hash':'i','cam_int_hash':'k','model_state_hash':'m1','arrays':arr};b={**a,'model_state_hash':'m2'};self.assertEqual(compare_order_runs({'A':{'f':a},'B':{'f':b}})['status'],'MODEL_STATE_MUTATION')
 def test_45_seed_applied(self):self.assertTrue(apply_reproducibility_environment(7)['seed_applied'])
 def test_46_seed_repeats_numpy(self):
  apply_reproducibility_environment(7);a=np.random.random();apply_reproducibility_environment(7);self.assertEqual(a,np.random.random())
 def test_47_seed_modes_separate(self):
  s=json.loads((ROOT/'MODEL_LOAD_AUDIT_SPEC_V1_2.json').read_text())['modes'];self.assertNotEqual(s['UNSEEDED_DIAGNOSTIC']['seed_applied'],s['CONTROLLED']['seed_applied'])
 def test_48_cam_int_hash(self):self.assertNotEqual(array_record(np.eye(3))['sha256'],array_record(np.eye(3)*2)['sha256'])
 def test_49_complete_sam_input(self):self.assertEqual(set(json.loads((ROOT/'SAM3D_REPRODUCIBILITY_SPEC_V1_2.json').read_text())['complete_input_identity']),{'raw_rgb','decoded_rgb','mask','bbox','prepared_tensor','cam_int'})
 def test_50_sam_model_fingerprints(self):self.assertEqual(len(json.loads((ROOT/'SAM3D_REPRODUCIBILITY_SPEC_V1_2.json').read_text())['model_fingerprints']),3)
 def test_51_pointcloud_full_gate_pass(self):
  row={'frame_id':'f','raw_depth_sha256':'d','decoded_depth':{'sha256':'dd','dtype':'u','shape':[1]},'raw_mask_sha256':'m','decoded_mask':{'sha256':'dm','dtype':'u','shape':[1]},'pointcloud_table_file_sha256':'t','pointcloud_table':{'sha256':'tt','dtype':'f','shape':[1]},'points':{'sha256':'p','dtype':'f','shape':[1],'order':'C'}};self.assertEqual(analyze_pointcloud([{'rows':[row]},{'rows':[row]}])['status'],'POINTCLOUD_REPRODUCIBILITY_PASS')
 def test_52_pointcloud_depth_gate(self):self._assert_pc_mismatch('decoded_depth','sha256')
 def test_53_pointcloud_mask_gate(self):self._assert_pc_mismatch('decoded_mask','sha256')
 def test_54_pointcloud_table_gate(self):self._assert_pc_mismatch('pointcloud_table','sha256')
 def test_55_pointcloud_points_gate(self):self._assert_pc_mismatch('points','sha256')
 def test_56_formal_authorization_frozen_false(self):self.assertFalse(json.loads((ROOT/'SAM3D_REPRODUCIBILITY_SPEC_V1_2.json').read_text())['formal_execution_authorized'])
 def test_57_sam_a_vs_b_analyzer(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);arr=t/'a.npz';np.savez(arr,vertices=np.zeros((2,3)),cam_t=np.zeros(3),anchors=np.zeros((2,3)));record={'frame_id':'f','arrays_npz':str(arr),'pred_vertices':array_record(np.zeros((2,3))),'anchors':array_record(np.zeros((2,3))),'prepared_tensor':array_record(np.zeros(1)),'cam_int':array_record(np.eye(3))};meta={'run_id':'A','mode':'CONTROLLED','model_state_sha256':'m','rows':[record]};(t/'a.json').write_text(json.dumps(meta));meta['run_id']='B';(t/'b.json').write_text(json.dumps(meta));self.assertEqual(analyze_sam(t/'a.json',[t/'b.json'])['summary']['exact_hash_matches']['vertices']['matches'],1)
 def test_58_preexecution_blocks_formal_runner(self):
  from types import SimpleNamespace
  with self.assertRaisesRegex(RuntimeError,'POST_REVIEW_GO'):sam_coordinator(SimpleNamespace(authorized_formal=False))
 def _assert_pc_mismatch(self,group,field):
  import copy;row={'frame_id':'f','raw_depth_sha256':'d','decoded_depth':{'sha256':'dd','dtype':'u','shape':[1]},'raw_mask_sha256':'m','decoded_mask':{'sha256':'dm','dtype':'u','shape':[1]},'pointcloud_table_file_sha256':'t','pointcloud_table':{'sha256':'tt','dtype':'f','shape':[1]},'points':{'sha256':'p','dtype':'f','shape':[1],'order':'C'}};other=copy.deepcopy(row);other[group][field]='changed';r=analyze_pointcloud([{'rows':[row]},{'rows':[other]}]);self.assertEqual(r['status'],'POINTCLOUD_RECONSTRUCTION_NONDETERMINISTIC');self.assertIn(group,r['first_mismatch']['field'])

if __name__=='__main__':unittest.main()
