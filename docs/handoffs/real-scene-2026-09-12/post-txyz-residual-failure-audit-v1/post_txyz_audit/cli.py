import argparse,json
from pathlib import Path
from .preflight import run
from .formal_audit import execute

GO_TOKEN='GO_POST_TXYZ_RESIDUAL_FAILURE_AUDIT_V1'
def authorize_execution(dry_run,execute_formal,approval):
    if dry_run and execute_formal:raise RuntimeError('DRY_RUN_FORBIDS_FORMAL_EXECUTION')
    if execute_formal and approval!=GO_TOKEN:raise RuntimeError('FORMAL_EXECUTION_APPROVAL_REQUIRED')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input-root',type=Path,required=True);parser.add_argument('--output-root',type=Path,required=True);parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--schema',type=Path,required=True);parser.add_argument('--back-region',type=Path);parser.add_argument('--sequence-root',type=Path);parser.add_argument('--replay-features',type=Path);parser.add_argument('--asset-requirements',type=Path);parser.add_argument('--txyz-source',type=Path);parser.add_argument('--anchors',type=Path);parser.add_argument('--calibs',type=Path);parser.add_argument('--dry-run',action='store_true');parser.add_argument('--execute-formal',action='store_true');parser.add_argument('--approval');parser.add_argument('--no-visuals',action='store_true');args=parser.parse_args();authorize_execution(args.dry_run,args.execute_formal,args.approval)
    preflight=run(args.input_root,args.schema,args.manifest,args.back_region);args.output_root.mkdir(parents=True,exist_ok=True);(args.output_root/'preflight_report.json').write_text(json.dumps(preflight,indent=2)+'\n',encoding='utf-8')
    if args.execute_formal:
        if not all((args.sequence_root,args.replay_features,args.asset_requirements,args.txyz_source,args.anchors,args.calibs)):raise RuntimeError('FORMAL_EXECUTION_REQUIRES_K0_REPLAY_AND_FROZEN_ASSETS')
        result=execute(args.input_root,args.output_root/'formal_audit',args.schema,args.manifest,args.sequence_root,args.replay_features,args.asset_requirements,args.txyz_source,args.anchors,args.calibs,args.back_region,args.no_visuals);print(result['status'])
    else:print(preflight['status'])
if __name__=='__main__':main()
