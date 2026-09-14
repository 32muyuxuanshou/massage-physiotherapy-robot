import argparse,json
from pathlib import Path
from .frame_order_runner import validate
from .feature_stability_runner import extractor_map
from .run_a_freeze import verify_manifest_contract
from .reviewed_delivery_integrity import REVIEWED_TAG
from .runtime_asset_verifier import tree_sha

REQUIRED_ENV={'python','numpy','scipy','pytorch','torch_cuda','cuda_runtime','cudnn','gpu','gpu_compute_capability','driver','opencv','timm','torch_deterministic','cudnn_benchmark','cudnn_deterministic','matmul_allow_tf32','cudnn_allow_tf32','float32_matmul_precision','cublas_workspace_config','cuda_visible_devices','omp_threads','mkl_threads','pythonhashseed','random_seed','numpy_seed','torch_seed','cuda_seed','scipy_workers'}
def check(root,run_a_manifest):
 root=Path(root);sent=json.loads((root/'FRAME_ORDER_TEST_SPEC_V1_2.json').read_text());assert len(validate(sent))==7
 freeze=json.loads((root/'RUN_A_ASSET_FREEZE_V1.json').read_text());verify_manifest_contract(freeze,run_a_manifest)
 env=json.loads((root/'ENVIRONMENT_FINGERPRINT_SCHEMA_V1_2.json').read_text());missing=REQUIRED_ENV-set(env['required']);assert not missing,missing;assert {'mode','requested_seed','seed_applied'}<=set(env['required'])
 contract=json.loads((root/'FEATURE_STABILITY_CONTRACT_V1_4.json').read_text());assert contract['types']['VECTOR_MM']['aggregation_rule']=='WORST_COMPONENT';assert set(contract['features'])==set(extractor_map())
 boundary=json.loads((root/'SAM_REPRODUCIBILITY_EVIDENCE_BOUNDARY_V1_4.json').read_text());assert boundary['historical_run_a']['permitted_comparison']=='anchors_only_and_reconstructed_txyz_reference';assert 'full_vertices' in boundary['historical_run_a']['unavailable']
 master=json.loads((root/'MASTER_ORCHESTRATION_SPEC_V1_4.json').read_text());assert master['fail_closed'] and not master['formal_execution_authorized_in_this_delivery'];assert master['ordered_stages'][:5]==['reviewed_delivery_integrity_pre','runtime_assets','run_a_actual_assets','input_snapshot','pointcloud_manifest_freeze'];assert 'sam_cohort_txyz' in master['ordered_stages'];assert master['ordered_stages'][-1]=='post_execution_integrity_including_reviewed_delivery';assert REVIEWED_TAG=='sam3d-txyz-repro-v1.4.2'
 config=json.loads((root/'EXECUTION_CONFIG_TEMPLATE_V1_4.json').read_text());assert len(config['paths']['calibration_relative_files'])==20;assert 'pointcloud_manifest' not in config['paths'];assert config['paths']['feature_contract']=='FEATURE_STABILITY_CONTRACT_V1_4.json'
 runtime=json.loads((root/'RUNTIME_ASSET_FREEZE_V1_4.json').read_text());assert runtime['formal_runtime_gate']['repro_code_tree_sha256']==tree_sha(root/'repro_fix',('*.py',))
 return {'status':'PASS_REVIEWED_DELIVERY_GATE_PREFLIGHT_V1_4_2','reviewed_tag':REVIEWED_TAG,'sentinel_unique':'7/7','run_a_frames':freeze['expected_frame_count'],'run_a_actual_hash_gate':'FORMAL_RUNTIME_REQUIRED_45_POINTS_PLUS_45_ANCHORS','pointcloud_manifest_source':'DERIVED_FROM_FORMAL_45','sam_to_txyz_chain':'RUN_B_TO_F_ANCHORS','feature_contract_coverage':f'{len(contract["features"])}/{len(contract["features"])}','master_fail_closed':True,'reviewed_delivery_pre_and_post':True,'post_execution_integrity':True,'calibration_files_frozen':20,'formal_experiment_executed':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--run-a-manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(check(a.root,a.run_a_manifest),indent=2)+'\n')
if __name__=='__main__':main()
