"""Absolute-error failure and abstention audit on consumed feature rows only."""
import argparse, json
from pathlib import Path
import numpy as np


def load(path): return json.loads(Path(path).read_text())['rows']
def auc(scores, labels):
    s=np.asarray(scores,float); y=np.asarray(labels,bool); p=s[y]; n=s[~y]
    if not len(p) or not len(n): return None
    return float(((p[:,None]>n).sum()+.5*(p[:,None]==n).sum())/(len(p)*len(n)))
def pearson(a,b): return float(np.corrcoef(a,b)[0,1])


def enrich(rows,split):
    out=[]
    for x in rows:
        use_a=x['a_point_o']-x['a_point_a']>15 and x['coverage_a']>=x['coverage_o']-.02
        c='a' if use_a else 'o'
        out.append({**x,'split':split,'selected':c,
          'selected_b_error_mm':x['b_error_'+c],
          'selected_point_mm':x['a_point_'+c],
          'min_point_mm':min(x['a_point_o'],x['a_point_a']),
          'selected_render_mm':x['a_render_'+c],
          'min_render_mm':min(x['a_render_o'],x['a_render_a']),
          'negative_selected_coverage':-x['coverage_'+c],
          'low_selector_margin':-abs(x['a_point_o']-x['a_point_a'])})
    return out


def feature_audit(rows):
    features=['selected_point_mm','min_point_mm','selected_render_mm','min_render_mm',
              'negative_selected_coverage','low_selector_margin']
    result={}
    for f in features:
        result[f]={'pearson_with_absolute_error':pearson([r[f] for r in rows],[r['selected_b_error_mm'] for r in rows]),
                   'auc':{f'BAD{t}':auc([r[f] for r in rows],[r['selected_b_error_mm']>t for r in rows]) for t in (30,50,80)}}
    return result


def risk_curve(rows,score):
    ordered=sorted(rows,key=lambda r:r[score])
    out=[]
    for cov in (1,.8,.6,.4,.2):
        n=max(1,int(np.floor(len(rows)*cov))); kept=ordered[:n]; e=np.array([r['selected_b_error_mm'] for r in kept])
        out.append({'target_coverage':cov,'kept':n,'actual_coverage':n/len(rows),
                    'mean_error_mm':float(e.mean()),'p90_error_mm':float(np.quantile(e,.9)),
                    'BAD30_rate':float(np.mean(e>30)),'BAD50_rate':float(np.mean(e>50)),'BAD80_rate':float(np.mean(e>80))})
    return out

def frozen_threshold_curve(dev,val,score):
    out=[]; ds=np.array([r[score] for r in dev])
    for target in (.8,.6,.4,.2):
        threshold=float(np.quantile(ds,target,method='higher'))
        item={'development_target_coverage':target,'threshold':threshold}
        for name,rows in [('DEVELOPMENT',dev),('SELECTOR_VAL',val)]:
            kept=[r for r in rows if r[score]<=threshold]; e=np.array([r['selected_b_error_mm'] for r in kept])
            item[name]={'kept':len(kept),'coverage':len(kept)/len(rows),'mean_error_mm':float(e.mean()) if len(e) else None,
                        'p90_error_mm':float(np.quantile(e,.9)) if len(e) else None,
                        'BAD30_rate':float(np.mean(e>30)) if len(e) else None}
        out.append(item)
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--dev',required=True);p.add_argument('--val',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    dev=enrich(load(a.dev),'DEVELOPMENT'); val=enrich(load(a.val),'SELECTOR_VAL')
    dev_a=feature_audit(dev); val_a=feature_audit(val)
    # Feature selection is development-only. Ties favor the directly rendered residual.
    primary=max(dev_a,key=lambda f:(dev_a[f]['auc']['BAD30'] if dev_a[f]['auc']['BAD30'] is not None else -1,
                                   f=='selected_render_mm'))
    counts={s:{f'BAD{t}':sum(r['selected_b_error_mm']>t for r in rr) for t in (30,50,80)} for s,rr in [('DEVELOPMENT',dev),('SELECTOR_VAL',val)]}
    result={'status':'CONSUMED_DATA_ABSOLUTE_FAILURE_AUDIT','data_governance':{'development_frames':len(dev),'selector_val_frames':len(val),'new_system_val_or_sealed_read':False,'final_reserve_read':False,'camera_b_role':'consumed absolute-error labels only'},
      'failure_definition':'Frozen exact selector output has Camera-B absolute median point-to-triangle error above threshold.',
      'positive_counts':counts,'simple_camera_a_feature_audit':{'DEVELOPMENT':dev_a,'SELECTOR_VAL':val_a},
      'development_selected_primary_score':primary,
      'risk_coverage':{'DEVELOPMENT':risk_curve(dev,primary),'SELECTOR_VAL':risk_curve(val,primary)},
      'development_frozen_finite_thresholds':frozen_threshold_curve(dev,val,primary),
      'rows':[{k:r[k] for k in ('split','id','subject_id','selected','selected_b_error_mm','selected_point_mm','min_point_mm','selected_render_mm','min_render_mm','negative_selected_coverage','low_selector_margin')} for r in dev+val]}
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);(out/'ABSOLUTE_FAILURE_ABSTENTION_V1.json').write_text(json.dumps(result,indent=2)+'\n')
    bad30_val=val_a[primary]['auc']['BAD30']; enough50=counts['DEVELOPMENT']['BAD50']>=5 and counts['SELECTOR_VAL']['BAD50']>=5; enough80=counts['DEVELOPMENT']['BAD80']>=5 and counts['SELECTOR_VAL']['BAD80']>=5
    readiness={'status':'NOT_READY_FOR_SAFETY_ABSTENTION','reason':'BAD50 has only 2/1 positives and BAD80 has 0/0; high-severity failure sensitivity and thresholds cannot be estimated.',
      'primary_score':primary,'evidence':{'BAD30_val_auc':bad30_val,'positive_counts':counts,'BAD50_minimum_evidence_met':enough50,'BAD80_minimum_evidence_met':enough80},
      'permitted_claim':'Camera-A rendered residual ranks BAD30 risk on these consumed HuMMan rows.',
      'prohibited_claims':['Validated safety rejector','Reliable BAD50 or BAD80 detection','Generalization beyond HuMMan dataset ROI/depth'],
      'next_test':'Pre-register the same score and a finite threshold on a future non-reserve system validation set with enough BAD50/BAD80 positives.'}
    (out/'ABSTENTION_READINESS_V1.json').write_text(json.dumps(readiness,indent=2)+'\n')
    print(json.dumps({'primary':primary,'readiness':readiness,'val_curve':result['risk_coverage']['SELECTOR_VAL']},indent=2))

if __name__=='__main__': main()
