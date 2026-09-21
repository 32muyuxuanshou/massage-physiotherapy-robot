import argparse,json
from pathlib import Path
import numpy as np
def med(x): return float(np.median(x))
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);rows=[]
 files=sorted(a.root.glob('Sub*/ATTRIBUTION_RESULTS.json')) or sorted(a.root.glob('Sub*_ATTRIBUTION_RESULTS.json'))
 for f in files: rows+=json.loads(f.read_text())['rows']
 assert len(rows)==54 and len({(r['spec']['subject'],r['spec']['sequence'],r['spec']['frame'],r['condition']) for r in rows})==54
 methods=['Official','Txyz','T_only','T_globalrot','T_bodypose','T+Pose'];conds=['FULL','UPPER','LOCAL_TORSO'];frame=[]
 for r in rows:
  for m in methods:
   h=[r['methods'][m][f'K{k}']['sensor']['median_mm'] for k in (1,2,3)];frame.append({'subject':r['spec']['subject'],'sequence':r['spec']['sequence'],'frame':r['spec']['frame'],'condition':r['condition'],'method':m,'heldout_median_mm':med(h)})
 sequence=[]
 for c in conds:
  for m in methods:
   for s,seq in sorted({(x['subject'],x['sequence']) for x in frame}):
    q=[x for x in frame if x['condition']==c and x['method']==m and x['subject']==s and x['sequence']==seq];sequence.append({'subject':s,'sequence':seq,'condition':c,'method':m,'heldout_median_mm':med([x['heldout_median_mm'] for x in q])})
 subject=[]
 for c in conds:
  for m in methods:
   for s in sorted({x['subject'] for x in frame}):
    q=[x for x in sequence if x['condition']==c and x['method']==m and x['subject']==s];subject.append({'subject':s,'condition':c,'method':m,'heldout_median_mm':med([x['heldout_median_mm'] for x in q])})
 primary=[]
 for c in conds:
  for m in methods:
   q=[x for x in subject if x['condition']==c and x['method']==m];primary.append({'condition':c,'method':m,'heldout_median_mm':med([x['heldout_median_mm'] for x in q]),'subjects':q})
 out={'schema':'ATTRIBUTION_BENCHMARK_V1_1','status':'COMPLETE','aggregation':'median(K1/K2/K3) -> median(frames within sequence) -> median(sequences within subject) -> median(subjects)','frame_count':18,'conditions':conds,'methods':methods,'primary':primary,'sequence_rows':sequence,'subject_rows':subject,'frame_rows':frame}
 (a.out/'ATTRIBUTION_AGGREGATED.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['primary'],indent=2))
if __name__=='__main__':main()
