import argparse,json
from pathlib import Path
from .txyz_same_process_runner import run_same_process_repeats
from .txyz_fresh_process_runner import run_fresh
from .txyz_repro_analyzer import analyze_runs
from .execution_guard import require_master_authorization
def run_batch(manifest,output_root,mode,runs=20,workers=-1):
 rows=[];specs=json.loads(Path(manifest).read_text())['rows'];Path(output_root).mkdir(parents=True,exist_ok=True)
 for spec in specs:
  fid=spec['frame_id'];target=Path(output_root)/fid.replace('/','__');target.mkdir(parents=True,exist_ok=True)
  if mode=='same':payload=run_same_process_repeats(spec['points_npz'],spec['anchors_npz'],runs,workers,target)
  else:payload=run_fresh(spec['points_npz'],spec['anchors_npz'],runs,workers,target/'summary.json')
  analysis=analyze_runs(payload['runs']);rows.append({'frame_id':fid,**analysis,'summary':str(target/'summary.json')});(target/'summary.json').write_text(json.dumps(payload,indent=2)+'\n')
 first=next(({'frame_id':x['frame_id'],**x['first_divergence']} for x in rows if x['first_divergence']),None);return {'status':'PASS_TXYZ_EXACT_INPUT_DETERMINISM' if first is None else 'TXYZ_EXACT_INPUT_NONDETERMINISTIC','mode':mode,'frames':len(rows),'runs_per_frame':runs,'first_divergence':first,'rows':rows}
def main():
 p=argparse.ArgumentParser();p.add_argument('--authorized-formal',action='store_true');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);p.add_argument('--mode',choices=['same','fresh'],required=True);p.add_argument('--runs',type=int,default=20);p.add_argument('--workers',type=int,default=-1);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if not a.authorized_formal:raise RuntimeError('FORMAL_RUN_REQUIRES_MASTER_ORCHESTRATOR_GO')
 require_master_authorization()
 a.output.write_text(json.dumps(run_batch(a.manifest,a.output_root,a.mode,a.runs,a.workers),indent=2)+'\n')
if __name__=='__main__':main()
