"""Repair TRAIN-constant normalization without re-fitting or changing native output.

Original experiments are retained. The mask is determined by TRAIN min==max;
neither scan VAL nor real B selects the mask. This is an explicit input bug fix.
"""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
import torch
from train_camera import load_table,sha


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    torch.set_num_threads(2)
    rows,data,target=load_table(a.root/'assets/compact_native')
    index=np.asarray([i for i,r in enumerate(rows) if r['role']=='TRAIN'])
    x=data['metric'][index]
    constant=x.min(0).values==x.max(0).values
    channels=torch.nonzero(constant).flatten().tolist()
    assert channels==[15,16]  # audited normalized principal-point constants, both exactly .5
    old=a.root/'native_v1_unmasked'
    (a.root/'native').rename(old)
    shutil.copytree(old,a.root/'native')
    receipts=[]
    for cell in sorted((a.root/'native').glob('*')):
        if not cell.is_dir():continue
        for name in ['best.pt','last.pt']:
            parent=old/cell.name/name
            state=torch.load(parent,map_location='cpu',weights_only=False)
            # g was exactly zero for every native sample. Masking is exact on native.
            old_g=(data['metric']-state['head']['metric_mean'])/state['head']['metric_std']
            assert torch.equal(old_g[:,constant],torch.zeros_like(old_g[:,constant]))
            state['head']['metric_active']=~constant
            state['execution_identity']['normalization_repair']=dict(
                parent_sha256=sha(parent),constant_TRAIN_channels=channels,
                native_predictions_exactly_unchanged=True,policy='TRAIN min==max -> normalized channel fixed zero',
                B_used_to_select_mask=False,TEST_read=False)
            torch.save(state,cell/name)
            receipts.append(dict(cell=cell.name,file=name,parent_sha256=sha(parent),repaired_sha256=sha(cell/name)))
    report=dict(status='PASS',channels=channels,constant_value=[float(x[0,c]) for c in channels],
                rationale='Previously unseen real principal point produced normalized magnitudes24/118 through std floor1e-4; untrained channel weights caused metre-scale false Camera changes',
                native_outputs_exact_equal=True,retraining=False,weight_tuning=False,
                historical_results_preserved=str(old),receipts=receipts,TEST_read=False)
    (a.root/'CONSTANT_FEATURE_REPAIR.json').write_text(json.dumps(report,indent=2))
    print('CONSTANT_FEATURE_REPAIR_PASS',channels,flush=True)
