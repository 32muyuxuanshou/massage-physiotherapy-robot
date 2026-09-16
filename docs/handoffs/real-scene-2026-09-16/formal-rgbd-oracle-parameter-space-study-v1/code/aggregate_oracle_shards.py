import argparse,csv,json
from pathlib import Path
import numpy as np
METHODS=('O0','O1','O2','O3','O4')
def med(v):return float(np.median(list(v)))
def write(path,data):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def main():
 p=argparse.ArgumentParser();p.add_argument('--shards',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);rows=[]
 for path in sorted(a.shards.glob('Sub*/per_frame_camera_metrics.csv')):
  with path.open() as f:
   for x in csv.DictReader(f):
    for k in list(x):
     if k not in ('subject','sequence','frame','frame_id','camera','role','method'):x[k]=float(x[k])
    rows.append(x)
 write(a.out/'per_frame_camera_metrics.csv',rows);idx={(x['frame_id'],x['camera'],x['method']):x for x in rows};fs=[]
 for fid in sorted({x['frame_id'] for x in rows if x['role']=='HELD_OUT'}):
  subject,sequence,_=fid.split('/',2)
  for m in METHODS:
   z=[idx[(fid,f'K{k}',m)] for k in (1,2,3)];fs.append({'subject':subject,'sequence':sequence,'frame_id':fid,'method':m,**{q:med(x[q] for x in z) for q in ('absolute_median_mm','absolute_mean_mm','absolute_p90_mm','absolute_p95_mm','absolute_coverage_50mm','aligned_median_mm')}})
 write(a.out/'per_frame_summary.csv',fs)
 def agg(level):
  out=[]
  for key in sorted({tuple(x[k] for k in level) for x in fs}):
   z0=[x for x in fs if tuple(x[k] for k in level)==key]
   for m in METHODS:
    z=[x for x in z0 if x['method']==m];out.append({**dict(zip(level,key)),'method':m,'frames':len(z),**{q:med(x[q] for x in z) for q in ('absolute_median_mm','absolute_p90_mm','absolute_p95_mm','absolute_coverage_50mm','aligned_median_mm')}})
  return out
 seq,sub=agg(('subject','sequence')),agg(('subject',));write(a.out/'per_sequence_summary.csv',seq);write(a.out/'per_subject_summary.csv',sub);overall=[]
 for m in METHODS:
  z=[x for x in sub if x['method']==m];overall.append({'method':m,'subjects':len(z),**{q:med(x[q] for x in z) for q in ('absolute_median_mm','absolute_p90_mm','absolute_p95_mm','absolute_coverage_50mm','aligned_median_mm')}})
 write(a.out/'overall_summary.csv',overall);ov={x['method']:x for x in overall};comparisons={}
 for m in ('O2','O3','O4'):
  wins=sum(next(x for x in sub if x['subject']==s and x['method']==m)['absolute_median_mm']<next(x for x in sub if x['subject']==s and x['method']=='O1')['absolute_median_mm'] for s in sorted({x['subject'] for x in sub}));comparisons[m]={'vs_O1_absolute_relative_improvement_pct':(ov['O1']['absolute_median_mm']-ov[m]['absolute_median_mm'])/ov['O1']['absolute_median_mm']*100,'vs_O1_absolute_delta_mm':ov[m]['absolute_median_mm']-ov['O1']['absolute_median_mm'],'vs_O1_aligned_relative_improvement_pct':(ov['O1']['aligned_median_mm']-ov[m]['aligned_median_mm'])/ov['O1']['aligned_median_mm']*100,'subjects_improved':wins}
 go=[m for m,x in comparisons.items() if x['vs_O1_absolute_relative_improvement_pct']>=5 and x['vs_O1_aligned_relative_improvement_pct']>=3 and x['subjects_improved']>=4];amb=[m for m,x in comparisons.items() if x['vs_O1_absolute_relative_improvement_pct']>=1];decision='STRONG_GO' if go else 'AMBIGUOUS' if amb else 'NO_GO';deltas=[]
 for x in fs:
  if x['method']=='O1':continue
  b=next(y for y in fs if y['frame_id']==x['frame_id'] and y['method']=='O1');k0=idx[(x['frame_id'],'K0',x['method'])];k0b=idx[(x['frame_id'],'K0','O1')];deltas.append({**x,'heldout_delta_mm':x['absolute_median_mm']-b['absolute_median_mm'],'aligned_delta_mm':x['aligned_median_mm']-b['aligned_median_mm'],'k0_delta_mm':k0['absolute_median_mm']-k0b['absolute_median_mm']})
 for name,data in [('top_improvements',sorted(deltas,key=lambda x:x['heldout_delta_mm'])[:10]),('top_degradations',sorted(deltas,key=lambda x:x['heldout_delta_mm'],reverse=True)[:10]),('k0_overfit_cases',sorted([x for x in deltas if x['k0_delta_mm']<0<x['heldout_delta_mm']],key=lambda x:x['heldout_delta_mm'],reverse=True)[:10])]: (a.out/f'{name}.json').write_text(json.dumps(data,indent=2)+'\n')
 final={'status':'PASS_STAGE_B_HELDOUT_EVALUATION','decision':decision,'strong_go_methods':go,'overall':overall,'comparisons':comparisons,'scope':'dataset-mask-assisted BEHAVE; K1/K2/K3 read only after Stage A manifest existed','regional_metrics':'NOT_YET_AVAILABLE'};(a.out/'FINAL_CHARACTERIZATION.json').write_text(json.dumps(final,indent=2)+'\n');print(json.dumps(final,indent=2))
if __name__=='__main__':main()
