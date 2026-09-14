import argparse,json
from pathlib import Path
import numpy as np
from .txyz_fresh_process_runner import fit

def run_same_process_repeats(points_npz,anchors_npz,runs=20,workers=-1,output_dir=None):
 points=np.load(points_npz)['points'];anchors=np.load(anchors_npz)['anchors'];rows=[]
 if output_dir:Path(output_dir).mkdir(parents=True,exist_ok=True)
 for index in range(runs):
  result=fit(points,anchors,workers);result['run_index']=index+1;rows.append(result)
  if output_dir:(Path(output_dir)/f'run_{index+1:03d}.json').write_text(json.dumps(result,indent=2)+'\n')
 return {'mode':'SAME_PROCESS','runs_requested':runs,'assets_loaded_once':True,'algorithm_state_recreated_each_run':True,'runs':rows}
def main():
 p=argparse.ArgumentParser();p.add_argument('--points',type=Path,required=True);p.add_argument('--anchors',type=Path,required=True);p.add_argument('--runs',type=int,default=20);p.add_argument('--workers',type=int,default=-1);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--authorized-formal',action='store_true');a=p.parse_args()
 if a.runs>=20 and not a.authorized_formal:raise RuntimeError('FORMAL_RUN_REQUIRES_POST_REVIEW_GO')
 payload=run_same_process_repeats(a.points,a.anchors,a.runs,a.workers,a.output_dir);(a.output_dir/'summary.json').write_text(json.dumps(payload,indent=2)+'\n')
if __name__=='__main__':main()
