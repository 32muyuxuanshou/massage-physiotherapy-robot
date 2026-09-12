import argparse,json
from pathlib import Path
from .preflight import run
from .formal_audit import execute

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input-root',type=Path,required=True);parser.add_argument('--output-root',type=Path,required=True);parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--schema',type=Path,required=True);parser.add_argument('--back-region',type=Path);parser.add_argument('--dry-run',action='store_true');parser.add_argument('--execute-formal',action='store_true');parser.add_argument('--no-visuals',action='store_true');args=parser.parse_args()
    preflight=run(args.input_root,args.schema,args.manifest,args.back_region);args.output_root.mkdir(parents=True,exist_ok=True);(args.output_root/'preflight_report.json').write_text(json.dumps(preflight,indent=2)+'\n',encoding='utf-8')
    if args.execute_formal:
        result=execute(args.input_root,args.output_root/'formal_audit',args.schema,args.back_region);print(result['status'])
    else:print(preflight['status'])
if __name__=='__main__':main()
