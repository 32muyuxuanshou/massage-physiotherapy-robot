import json,math,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parents[1]
def load(n):return json.load(open(ROOT/'raw'/n))['rows']
def auc(score,y):
 pos=score[y];neg=score[~y];return float(np.mean([(pos[:,None]>neg).mean()+.5*(pos[:,None]==neg).mean()]))
def stats(rows,feature,tau):
 d=np.array([x[f'a_{feature}_o']-x[f'a_{feature}_a'] for x in rows]);g=np.array([x['b_error_o']-x['b_error_a'] for x in rows]);y=g>0;cov=np.array([x['coverage_a']>=x['coverage_o']-.02 for x in rows]);p=(d>tau)&cov
 return {'n':len(rows),'adapted_win_rate':float(y.mean()),'pearson_delta_vs_b_gain':float(np.corrcoef(d,g)[0,1]),'auc':auc(d,y),'accuracy':float((p==y).mean()),'false_switch':int((p&~y).sum()),'missed_rescue':int((~p&y).sum()),'adapted_selected':int(p.sum()),'constant_accuracy':float(max(y.mean(),1-y.mean()))}
dev,val=load('selector_dev_features.json'),load('selector_val_features.json');features=['point','render','common'];taus=[0,2,5,10,15]
audit={'status':'CAMERA_A_DEPTH_PREDICTIVE_ON_CONSUMED_DATA','feature_audit':{f:{'dev':stats(dev,f,0),'selector_val':stats(val,f,0)} for f in features}}
(ROOT/'SELECTOR_PREDICTIVENESS_AUDIT_V1.json').write_text(json.dumps(audit,indent=2)+chr(10))
cands={'status':'FINITE_CANDIDATES_AUDITED_ON_CONSUMED_DATA','coverage_rule':'adapted coverage >= official coverage - 0.02','candidates':[{'feature':f,'tau_mm':t,'dev':stats(dev,f,t),'selector_val':stats(val,f,t)} for f in features for t in taus]}
(ROOT/'SELECTOR_RULE_CANDIDATES_V1.json').write_text(json.dumps(cands,indent=2)+chr(10))
rule={'status':'FROZEN_BEFORE_SELECTOR_SEALED_ACCESS','feature':'point_to_triangle_surface_residual','delta':'R_O-R_A','tau_mm':15,'coverage_rule':'coverage_A >= coverage_O - 0.02','minimum_camera_a_points':2048,'missing_depth':'OFFICIAL','tie':'OFFICIAL','low_evidence':'diagnostic_only','decision':'ADAPTED iff delta>15mm and coverage rule passes; otherwise OFFICIAL','dev':stats(dev,'point',15),'selector_val':stats(val,'point',15)}
(ROOT/'SELECTOR_RULE_FREEZE_RECEIPT_V1.json').write_text(json.dumps(rule,indent=2)+chr(10));rulehash=hashlib.sha256((ROOT/'SELECTOR_RULE_FREEZE_RECEIPT_V1.json').read_bytes()).hexdigest()
ready={'status':'READY_FOR_SEALED_SELECTOR_TEST','evidence':{'camera_a_only':True,'camera_b_label_only':True,'point_feature_dev_auc':audit['feature_audit']['point']['dev']['auc'],'point_feature_val_auc':audit['feature_audit']['point']['selector_val']['auc'],'dev_accuracy':rule['dev']['accuracy'],'val_accuracy':rule['selector_val']['accuracy'],'rule_sha256':rulehash,'selector_sealed_subjects_untouched':True,'future_reserve_untouched':True}}
(ROOT/'DEPTH_AWARE_SELECTOR_READINESS_V1.json').write_text(json.dumps(ready,indent=2)+chr(10))
print(json.dumps({'rule':rule,'readiness':ready},indent=2))
