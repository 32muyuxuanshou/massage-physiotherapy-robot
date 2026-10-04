"""Independent CPU replay, including exact reuse of original full-input results."""
import json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'ct-anatomical-query-pilot-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=json.loads((ROOT/'PER_CASE_RESULTS.json').read_text());manifest={r['subject']:r for r in json.loads((BASE/'CASE_MANIFEST.json').read_text()) if r['eligible']}
loaded={};checks=0
for r in rows:
    s=r['subject']
    if s not in loaded:
        p=BASE/'inputs'/(s+'.npz');assert sha(p)==manifest[s]['input_sha256'];loaded[s]=dict(np.load(p))
    data=loaded[s];p=ROOT/'predictions'/r['role']/Path(r['path']).name;assert sha(p)==r['sha256'];z=dict(np.load(p))
    assert np.array_equal(z['target_uv'],data['target_uv']) and np.array_equal(z['target_valid'],data['target_valid'])
    scale=np.diff(data['xz_bounds_mm'].reshape(2,2),axis=1).ravel();error=np.linalg.norm((z['pred_uv']-data['target_uv'])*scale,axis=1)
    assert np.allclose(error,z['xz_error_mm'],rtol=0,atol=1e-6);assert abs(error[data['target_valid']].mean()-r['mean_xz_mm'])<1e-6
    if r['mode']=='FULL_SURFACE':
        old=BASE/'predictions'/r['role']/(s+'_'+r['method']+'_seed'+str(r['seed'])+'.npz');assert sha(old)==r['reused_full_prediction_sha256'];assert np.array_equal(np.load(old)['pred_uv'],z['pred_uv'])
    checks+=1
out={'status':'PASS','actual_cases':len(loaded),'actual_predictions':checks,'new_fit':False,'new_model_execution':False,'scope':'actual hash, target equality, X/Z recompute and frozen full-input prediction reuse'}
(ROOT/'DELIVERY_REPLAY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
