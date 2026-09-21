"""Aggregate v3 with explicit K -> frame -> sequence -> subject nesting."""
import argparse,json
from pathlib import Path
import numpy as np

def med(x): return float(np.median(x)) if x else None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--shards',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for p in sorted(a.shards.glob('Sub*/report/per_frame_results.json')): rows.extend(json.loads(p.read_text()))
    assert len(rows)==54,len(rows)
    methods=['Official','Txyz','T+Pose']; conds=['FULL','UPPER','LOCAL_TORSO']
    frame=[]
    for r in rows:
        for m in methods:
            hs=[r['methods'][m][f'K{k}']['sensor']['median_mm'] for k in (1,2,3)]
            cov=[r['methods'][m][f'K{k}']['sensor']['coverage_50mm'] for k in (1,2,3)]
            frame.append({'subject':r['spec']['subject'],'sequence':r['spec']['sequence'],'frame':r['spec']['frame'],'condition':r['condition'],'method':m,'heldout_median_mm':med(hs),'coverage_50mm':med(cov),'k0_median_mm':r['methods'][m]['K0']['sensor']['median_mm'],'txyz_norm_mm':float(np.linalg.norm(r['txyz_m'])*1000),'txyz_fallback':r['txyz_fallback'],'o2_translation_delta_m':r.get('o2_translation_delta_m')})
    sequence=[]
    for c in conds:
      for m in methods:
       for s in sorted({x['subject'] for x in frame}):
        for qseq in sorted({x['sequence'] for x in frame if x['subject']==s}):
         q=[x for x in frame if x['condition']==c and x['method']==m and x['subject']==s and x['sequence']==qseq]
         sequence.append({'subject':s,'sequence':qseq,'condition':c,'method':m,'heldout_median_mm':med([x['heldout_median_mm'] for x in q]),'coverage_50mm':med([x['coverage_50mm'] for x in q]),'k0_median_mm':med([x['k0_median_mm'] for x in q])})
    subject=[]
    for c in conds:
      for m in methods:
       for s in sorted({x['subject'] for x in sequence}):
        q=[x for x in sequence if x['condition']==c and x['method']==m and x['subject']==s]
        subject.append({'subject':s,'condition':c,'method':m,'heldout_median_mm':med([x['heldout_median_mm'] for x in q]),'coverage_50mm':med([x['coverage_50mm'] for x in q]),'k0_median_mm':med([x['k0_median_mm'] for x in q])})
    primary=[]
    for c in conds:
      for m in methods:
       q=[x for x in subject if x['condition']==c and x['method']==m]
       primary.append({'condition':c,'method':m,'heldout_median_mm':med([x['heldout_median_mm'] for x in q]),'coverage_50mm':med([x['coverage_50mm'] for x in q]),'subjects':q})
    fallback_rows=[x for x in frame if x['method']=='Official']
    out={'schema':'FORMAL_BACK_LOCAL_MODEL_EVALUATION_V3','status':'COMPLETE','aggregation':'K1/K2/K3 -> frame -> sequence -> subject','frame_count':18,'sequence_count':9,'subject_count':3,'primary_table':primary,'frame_rows':frame,'sequence_rows':sequence,'subject_rows':subject,'txyz_fallback_count':sum(x['txyz_fallback'] for x in fallback_rows),'txyz_total_count':len(fallback_rows)}
    (a.out/'FORMAL_RESULTS_V3.json').write_text(json.dumps(out,indent=2)+'\n'); (a.out/'FRAME_RESULTS_V3.json').write_text(json.dumps(frame,indent=2)+'\n'); (a.out/'SEQUENCE_RESULTS_V3.json').write_text(json.dumps(sequence,indent=2)+'\n'); (a.out/'SUBJECT_RESULTS_V3.json').write_text(json.dumps(subject,indent=2)+'\n'); print(json.dumps({'status':'COMPLETE','frames':len(rows),'sequence_rows':len(sequence),'subject_rows':len(subject)}))
if __name__=='__main__': main()
