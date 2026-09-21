"""Aggregate frozen BEHAVE formal evaluation without changing raw results."""
from __future__ import annotations
import argparse, json, statistics
from pathlib import Path
import numpy as np

def med(v): return float(np.median(v)) if v else None
def pct(v,q): return float(np.percentile(v,q)) if v else None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--shards',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for p in sorted(a.shards.glob('Sub*/report/per_frame_results.json')): rows.extend(json.loads(p.read_text()))
    assert len(rows)==54, len(rows)
    methods=('Official','Txyz','T+Pose'); conds=('FULL','UPPER','LOCAL_TORSO')
    frame=[]
    for r in rows:
        for m in methods:
            hs=[r['methods'][m][f'K{k}']['sensor']['median_mm'] for k in (1,2,3)]
            hmean=[r['methods'][m][f'K{k}']['sensor']['mean_mm'] for k in (1,2,3)]
            hp95=[r['methods'][m][f'K{k}']['sensor']['p95_mm'] for k in (1,2,3)]
            cov=[r['methods'][m][f'K{k}']['sensor']['coverage_50mm'] for k in (1,2,3)]
            k0=r['methods'][m]['K0']['sensor']['median_mm']; frame.append({'subject':r['spec']['subject'],'sequence':r['spec']['sequence'],'frame':r['spec']['frame'],'condition':r['condition'],'method':m,'heldout_median_mm':med(hs),'heldout_mean_mm':med(hmean),'heldout_p95_mm':med(hp95),'coverage_50mm':med(cov),'k0_median_mm':k0,'reference_heldout_median_mm':med([r['methods'][m][f'K{k}']['reference']['median_mm'] for k in (1,2,3)]),'txyz_norm_mm':float(np.linalg.norm(r['txyz_m'])*1000),'txyz_fallback':r['txyz_fallback']})
    def subject_rows(c,m): return [x for x in frame if x['condition']==c and x['method']==m]
    subject=[]
    for c in conds:
        for m in methods:
            for s in ('Sub03','Sub04','Sub05'):
                q=[x for x in subject_rows(c,m) if x['subject']==s]; subject.append({'subject':s,'condition':c,'method':m,'heldout_median_mm':med([x['heldout_median_mm'] for x in q]),'heldout_p95_mm':med([x['heldout_p95_mm'] for x in q]),'heldout_mean_mm':med([x['heldout_mean_mm'] for x in q]),'coverage_50mm':med([x['coverage_50mm'] for x in q]),'k0_median_mm':med([x['k0_median_mm'] for x in q]),'reference_heldout_median_mm':med([x['reference_heldout_median_mm'] for x in q])})
    primary=[]
    for c in conds:
        for m in methods:
            q=[x for x in subject if x['condition']==c and x['method']==m]; primary.append({'condition':c,'method':m,'heldout_median_mm':med([x['heldout_median_mm'] for x in q]),'heldout_p90_mm':pct([x['heldout_median_mm'] for x in q],90),'heldout_p95_mm':pct([x['heldout_median_mm'] for x in q],95),'coverage_50mm':med([x['coverage_50mm'] for x in q]),'aligned_median_mm':None,'reference_support_median_mm':med([x['reference_heldout_median_mm'] for x in q]),'subjects':q})
    def lookup(c,m): return next(x for x in primary if x['condition']==c and x['method']==m)
    sensitivity=[]
    for m in methods:
        f=lookup('FULL',m)['heldout_median_mm']; sensitivity.append({'method':m,'UPPER_minus_FULL_mm':lookup('UPPER',m)['heldout_median_mm']-f,'LOCAL_TORSO_minus_FULL_mm':lookup('LOCAL_TORSO',m)['heldout_median_mm']-f})
    correction=[]
    for c in conds: correction.append({'condition':c,'Txyz_minus_Official_mm':lookup(c,'Txyz')['heldout_median_mm']-lookup(c,'Official')['heldout_median_mm'],'T+Pose_minus_Txyz_mm':lookup(c,'T+Pose')['heldout_median_mm']-lookup(c,'Txyz')['heldout_median_mm']})
    # Subject-direction checks, not a forced four-way label.
    consistency=[]
    for c in conds:
        for a1,a2 in (('Official','Txyz'),('Txyz','T+Pose')):
            q=[x for x in subject if x['condition']==c and x['method']==a1]; z=[x for x in subject if x['condition']==c and x['method']==a2]; by={x['subject']:x for x in z}; deltas=[by[x['subject']]['heldout_median_mm']-x['heldout_median_mm'] for x in q]; consistency.append({'condition':c,'comparison':a2+' vs '+a1,'subject_deltas_mm':dict(zip([x['subject'] for x in q],deltas)),'subjects_improved':sum(d<0 for d in deltas),'subjects_total':3})
    overfit=[]
    for x in frame:
        if x['method']=='T+Pose':
            t=next(y for y in frame if y['subject']==x['subject'] and y['sequence']==x['sequence'] and y['frame']==x['frame'] and y['condition']==x['condition'] and y['method']=='Txyz'); overfit.append({**x,'txyz_heldout_median_mm':t['heldout_median_mm'],'k0_delta_mm':x['k0_median_mm']-t['k0_median_mm'],'heldout_delta_mm':x['heldout_median_mm']-t['heldout_median_mm'],'pose_overfit':x['k0_median_mm']<t['k0_median_mm'] and x['heldout_median_mm']>t['heldout_median_mm']})
    out={'schema':'FORMAL_BACK_LOCAL_MODEL_EVALUATION_RESULTS_V1','status':'COMPLETE','primary_evidence':'K1/K2/K3 held-out sensor depth to predicted mesh; subject-aware aggregation','supporting_evidence':'BEHAVE fitted multi-view SMPL surface sampled to 2000 points per frame/camera','frame_count':18,'subject_count':3,'method_count':3,'condition_count':3,'primary_table':primary,'input_sensitivity':sensitivity,'correction_benefit':correction,'subject_consistency':consistency,'k0_overfit_audit':{'rows':overfit,'count':sum(x['pose_overfit'] for x in overfit)},'frame_rows':frame,'subject_rows':subject}
    (a.out/'FORMAL_RESULTS.json').write_text(json.dumps(out,indent=2)+'\n'); (a.out/'per_frame_results.json').write_text(json.dumps(frame,indent=2)+'\n'); (a.out/'per_subject_results.json').write_text(json.dumps(subject,indent=2)+'\n')
    print(json.dumps({'status':'COMPLETE','frames':len(rows),'rows':len(frame),'subjects':3}))
if __name__=='__main__':main()
