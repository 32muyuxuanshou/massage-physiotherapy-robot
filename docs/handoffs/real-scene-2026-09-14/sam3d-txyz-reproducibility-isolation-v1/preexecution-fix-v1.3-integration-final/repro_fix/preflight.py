import argparse,json
from pathlib import Path
from .frame_order_runner import validate
from .run_a_freeze import verify

REQUIRED_ENV={'python','numpy','scipy','pytorch','torch_cuda','cuda_runtime','cudnn','gpu','gpu_compute_capability','driver','opencv','timm','torch_deterministic','cudnn_benchmark','cudnn_deterministic','matmul_allow_tf32','cudnn_allow_tf32','float32_matmul_precision','cublas_workspace_config','cuda_visible_devices','omp_threads','mkl_threads','pythonhashseed','random_seed','numpy_seed','torch_seed','cuda_seed','scipy_workers'}
def check(root,run_a_manifest):
 root=Path(root);sent=json.loads((root/'FRAME_ORDER_TEST_SPEC_V1_2.json').read_text());assert len(validate(sent))==7
 freeze=json.loads((root/'RUN_A_ASSET_FREEZE_V1.json').read_text());verify(freeze,run_a_manifest)
 env=json.loads((root/'ENVIRONMENT_FINGERPRINT_SCHEMA_V1_2.json').read_text());missing=REQUIRED_ENV-set(env['required']);assert not missing,missing;assert {'mode','requested_seed','seed_applied'}<=set(env['required'])
 contract=json.loads((root/'FEATURE_STABILITY_CONTRACT_V1_2.json').read_text());assert contract['types']['VECTOR_MM']['aggregation_rule']=='WORST_COMPONENT'
 boundary=json.loads((root/'SAM_REPRODUCIBILITY_EVIDENCE_BOUNDARY_V1_3.json').read_text());assert boundary['historical_run_a']['permitted_comparison']=='anchors_only';assert 'full_vertices' in boundary['historical_run_a']['unavailable']
 master=json.loads((root/'MASTER_ORCHESTRATION_SPEC_V1_3.json').read_text());assert master['fail_closed'] and not master['formal_execution_authorized_in_this_delivery'];assert master['ordered_stages'][:3]==['runtime_assets','run_a_freeze','input_snapshot']
 config=json.loads((root/'EXECUTION_CONFIG_TEMPLATE_V1_3.json').read_text());assert len(config['paths']['calibration_relative_files'])==20
 return {'status':'PASS_INTEGRATION_PREFLIGHT_V1_3','sentinel_unique':'7/7','run_a_frames':freeze['expected_frame_count'],'historical_run_a_scope':'ANCHORS_ONLY','master_fail_closed':True,'calibration_files_frozen':20,'formal_experiment_executed':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--run-a-manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(check(a.root,a.run_a_manifest),indent=2)+'\n')
if __name__=='__main__':main()
