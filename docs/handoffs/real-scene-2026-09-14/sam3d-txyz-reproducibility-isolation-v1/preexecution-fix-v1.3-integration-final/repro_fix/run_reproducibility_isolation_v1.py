import argparse,json,os,subprocess,sys,time
from pathlib import Path
from .input_source_snapshot import build as build_input_snapshot
from .run_a_freeze import verify as verify_run_a
from .runtime_asset_verifier import verify_assets
from .execution_guard import GO_SHA256

GO_TOKEN='GO_SAM3D_TXYZ_REPRODUCIBILITY_ISOLATION_V1'
STAGES=('model_load_unseeded','model_load_controlled','pointcloud','txyz_same','txyz_fresh','sam_controlled','sam_analysis','frame_order','frame_order_analysis','feature_stability')
PASS={
 'model_load_unseeded':{'PASS_MODEL_LOAD_REPRODUCIBILITY'},'model_load_controlled':{'PASS_MODEL_LOAD_REPRODUCIBILITY'},'pointcloud':{'POINTCLOUD_REPRODUCIBILITY_PASS'},'txyz_same':{'PASS_TXYZ_EXACT_INPUT_DETERMINISM'},'txyz_fresh':{'PASS_TXYZ_EXACT_INPUT_DETERMINISM'},'sam_controlled':{'PASS_SAM_CONTROLLED_COHORT_EXECUTION'},'sam_analysis':{'PASS_SAM_REPRODUCIBILITY_ANALYSIS'},'frame_order':{'PASS_FRAME_ORDER_EXECUTION'},'frame_order_analysis':{'PASS_NO_FRAME_ORDER_DEPENDENCE'},'feature_stability':{'PASS_FEATURE_STABILITY_CHARACTERIZATION'}}
def child_environment(config):
 env=os.environ.copy();settings={'CUBLAS_WORKSPACE_CONFIG':':4096:8','PYTHONHASHSEED':str(config['seed']),'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','REPRO_ISOLATION_MASTER_ACTIVE':'1','REPRO_ISOLATION_GO_TOKEN_SHA256':GO_SHA256};settings.update(config.get('process_start_environment',{}));env.update(settings);return env,settings
def common_sam(config,input_snapshot):
 p=config['paths'];return ['--manifest',p['formal_manifest'],'--sequences',p['sequences'],'--calibs',p['calibs'],'--sam-repo',p['sam3d_repo'],'--checkpoint',p['official_checkpoint'],'--mhr',p['mhr_model'],'--anchor-asset',p['surface_anchors'],'--v23-code',p['v23_code'],'--input-snapshot',str(input_snapshot)]
def commands(config,out,input_snapshot):
 p=config['paths'];py=sys.executable;sam=common_sam(config,input_snapshot);cohort=[str(out/'sam'/f'RUN_{x}.json') for x in 'BCDEF'];frame=[str(out/'frame_order'/f'{x}.json') for x in ('ORDER_ORIGINAL','ORDER_REVERSED','ORDER_RANDOM_FIXED_SEED')]
 return {
 'model_load_unseeded':([py,'-m','repro_fix.model_load_auditor','--authorized-formal','--runs','5','--mode','UNSEEDED_DIAGNOSTIC','--sam-repo',p['sam3d_repo'],'--checkpoint',p['official_checkpoint'],'--mhr',p['mhr_model'],'--output',str(out/'model_unseeded.json')],out/'model_unseeded.json'),
 'model_load_controlled':([py,'-m','repro_fix.model_load_auditor','--authorized-formal','--runs','5','--mode','CONTROLLED','--seed',str(config['seed']),'--sam-repo',p['sam3d_repo'],'--checkpoint',p['official_checkpoint'],'--mhr',p['mhr_model'],'--output',str(out/'model_controlled.json')],out/'model_controlled.json'),
 'pointcloud':([py,'-m','repro_fix.pointcloud_repro_runner','--authorized-formal','--manifest',p['pointcloud_manifest'],'--runs','5','--output',str(out/'pointcloud.json')],out/'pointcloud.json'),
 'txyz_same':([py,'-m','repro_fix.txyz_batch_runner','--authorized-formal','--manifest',p['replay_manifest'],'--mode','same','--runs','20','--workers','-1','--output-root',str(out/'txyz_same'),'--output',str(out/'txyz_same.json')],out/'txyz_same.json'),
 'txyz_fresh':([py,'-m','repro_fix.txyz_batch_runner','--authorized-formal','--manifest',p['replay_manifest'],'--mode','fresh','--runs','20','--workers','-1','--output-root',str(out/'txyz_fresh'),'--output',str(out/'txyz_fresh.json')],out/'txyz_fresh.json'),
 'sam_controlled':([py,'-m','repro_fix.sam_repro_runner','--authorized-formal','--mode','CONTROLLED','--seed',str(config['seed']),'--arrays-dir',str(out/'sam'/'arrays'),'--output',str(out/'sam'/'coordinator.json'),*sam],out/'sam'/'coordinator.json'),
 'sam_analysis':([py,'-m','repro_fix.sam_repro_analyzer_v2','--run-a-freeze',p['run_a_freeze'],'--replay-manifest',p['replay_manifest'],'--cohort',*cohort,'--output',str(out/'sam'/'analysis.json')],out/'sam'/'analysis.json'),
 'frame_order':([py,'-m','repro_fix.frame_order_execution_runner','--authorized-formal','--spec',p['frame_order_spec'],'--source-manifest',p['formal_manifest'],'--output-dir',str(out/'frame_order'),'--seed',str(config['seed']),*sam[2:]],out/'frame_order'/'execution_summary.json'),
 'frame_order_analysis':([py,'-m','repro_fix.frame_order_analyzer','--runs',*frame,'--output',str(out/'frame_order'/'analysis.json')],out/'frame_order'/'analysis.json'),
 'feature_stability':([py,'-m','repro_fix.feature_stability_runner','--batch-summary',str(out/'txyz_fresh.json'),'--contract',p['feature_contract'],'--output',str(out/'feature_stability.json')],out/'feature_stability.json')}
def execute_stages(stage_commands,env,runner=None):
 ledger=[];runner=runner or (lambda cmd:subprocess.run(cmd,check=False,env=env).returncode)
 for stage in STAGES:
  cmd,output=stage_commands[stage];started=time.time();code=runner(cmd)
  if code!=0:ledger.append({'stage':stage,'status':'PROCESS_FAILED','returncode':code});return ledger
  result=json.loads(Path(output).read_text());status=result.get('status');ledger.append({'stage':stage,'status':status,'seconds':time.time()-started,'output':str(output)})
  if status not in PASS[stage]:return ledger
 return ledger
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--go-token',required=True);a=p.parse_args()
 if a.go_token!=GO_TOKEN:raise RuntimeError('FORMAL_GO_TOKEN_REQUIRED')
 config=json.loads(a.config.read_text());out=Path(config['output_root']);out.mkdir(parents=True,exist_ok=True);ledger=[]
 try:asset=verify_assets(config['paths'],json.loads(Path(config['paths']['asset_freeze']).read_text()))
 except Exception as error:asset={'status':'ASSET_FREEZE_VERIFICATION_ERROR','error':str(error)}
 (out/'runtime_asset_verification.json').write_text(json.dumps(asset,indent=2)+'\n');ledger.append({'stage':'runtime_assets','status':asset['status']})
 if asset['status']!='PASS_RUNTIME_ASSET_FREEZE':
  (out/'execution_ledger.json').write_text(json.dumps({'status':'STOPPED_BY_FAIL_CLOSED_GATE','ledger':ledger},indent=2)+'\n');return
 freeze=json.loads(Path(config['paths']['run_a_freeze']).read_text())
 try:verify_run_a(freeze,config['paths']['replay_manifest']);ledger.append({'stage':'run_a_freeze','status':'PASS_RUN_A_FREEZE'})
 except Exception as error:
  ledger.append({'stage':'run_a_freeze','status':'RUN_A_FREEZE_VIOLATION','error':str(error)});(out/'execution_ledger.json').write_text(json.dumps({'status':'STOPPED_BY_FAIL_CLOSED_GATE','ledger':ledger},indent=2)+'\n');return
 snapshot=out/'controlled_input_snapshot.json';snapshot.write_text(json.dumps(build_input_snapshot(config['paths']['formal_manifest'],config['paths']['sequences']),indent=2)+'\n');ledger.append({'stage':'input_snapshot','status':'PASS_INPUT_SNAPSHOT_CREATED'})
 env,settings=child_environment(config);ledger.extend(execute_stages(commands(config,out,snapshot),env));complete=len(ledger)==3+len(STAGES) and all(x['status'] in {'PASS_RUNTIME_ASSET_FREEZE','PASS_RUN_A_FREEZE','PASS_INPUT_SNAPSHOT_CREATED'}|set().union(*PASS.values()) for x in ledger);payload={'status':'PASS_REPRODUCIBILITY_ISOLATION_EXECUTION' if complete else 'STOPPED_BY_FAIL_CLOSED_GATE','process_start_environment':settings,'ledger':ledger};(out/'execution_ledger.json').write_text(json.dumps(payload,indent=2)+'\n')
if __name__=='__main__':main()
