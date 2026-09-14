import argparse,json,subprocess,sys
from pathlib import Path
from .frame_order_runner import validate,build_orders

def make_order_manifest(source_rows,order):
 by_id={x['frame_id']:x for x in source_rows};return {'rows':[by_id[x] for x in order]}
def command_for_order(a,name,manifest,output):
 cmd=[sys.executable,'-m','repro_fix.sam_repro_runner','--worker','--run-id',name,'--mode','CONTROLLED','--seed',str(a.seed),'--manifest',str(manifest),'--output',str(output),'--arrays-dir',str(a.output_dir/name)]
 for field in ('sequences','calibs','sam_repo','checkpoint','mhr','anchor_asset','v23_code'):cmd += ['--'+field.replace('_','-'),str(getattr(a,field))]
 return cmd
def execute(a):
 if not a.authorized_formal:raise RuntimeError('FORMAL_RUN_REQUIRES_POST_REVIEW_GO')
 spec=json.loads(a.spec.read_text());ids=validate(spec);orders=build_orders(ids,spec['seed']);source=json.loads(a.source_manifest.read_text())['rows'];a.output_dir.mkdir(parents=True,exist_ok=True);outputs=[]
 for name,order in orders.items():
  manifest=a.output_dir/f'{name}.manifest.json';output=a.output_dir/f'{name}.json';manifest.write_text(json.dumps(make_order_manifest(source,order),indent=2)+'\n');subprocess.run(command_for_order(a,name,manifest,output),check=True);outputs.append(str(output))
 return {'design':'three independent processes; seven frames sequentially within one loaded model per process','outputs':outputs}
def main():
 p=argparse.ArgumentParser();p.add_argument('--authorized-formal',action='store_true');p.add_argument('--spec',type=Path,required=True);p.add_argument('--source-manifest',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--seed',type=int,default=20260912)
 for n in ('sequences','calibs','sam-repo','checkpoint','mhr','anchor-asset','v23-code'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();(a.output_dir/'execution_summary.json').write_text(json.dumps(execute(a),indent=2)+'\n')
if __name__=='__main__':main()
