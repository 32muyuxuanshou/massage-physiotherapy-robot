"""Run all three models against all four actual cached 18-level TRAIN packs."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from fit_field_prior import fit, predict
from joint_surface_field import JointSurfaceField
from train_field import GlobalField, FieldDataset, compute_loss
from evaluate_field import prepare_case, model_prediction, scores

ROOT=Path(__file__).resolve().parents[1]


def main():
    torch.set_num_threads(4);torch.manual_seed(23)
    start=time.time();rows=json.loads((ROOT/'structure_check/CASE_MANIFEST.json').read_text())
    for row in rows:
        row['pack']=str(ROOT/'structure_check'/row['case']/'field_pack.npz')
    dataset=FieldDataset(rows,23,True)
    batch=next(iter(DataLoader(dataset,batch_size=4)))
    assert batch['observed'].shape==(4,1024,3) and batch['query'].shape==(4,256,3)
    assert int(batch['anatomy_valid'].sum())>0
    checks=[]
    prior=fit(rows)
    evaluation_input=prepare_case(rows[0],5.)
    common=np.array([p is not None for p in prior['coefficients']])
    for kind in ['GLOBAL_ANATOMY','LOCAL_ANATOMY','LOCAL_JOINT']:
        model=GlobalField() if kind=='GLOBAL_ANATOMY' else JointSurfaceField()
        optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
        pred=model(batch['observed'],batch['query'],batch['references'],batch['reference_present'])
        total,anatomy,surface=compute_loss(pred,batch,kind=='LOCAL_JOINT')
        assert torch.isfinite(total);total.backward()
        active=sum(p.numel() for p in model.parameters() if p.grad is not None)
        optimizer.step()
        model.eval()
        prediction=model_prediction(model,kind,evaluation_input,'cpu')
        result=scores(prediction,evaluation_input,common)
        assert prediction['field'].shape==(8192,2) and np.isfinite(prediction['level_xyz_mm']).all()
        assert np.isfinite(result['anatomy_case_mean_mm'])
        unprompted_input=dict(evaluation_input)
        unprompted_input['reference_present']=np.zeros(2,bool)
        unprompted=model_prediction(model,kind,unprompted_input,'cpu')
        assert np.isfinite(unprompted['level_xyz_mm']).all()
        checks.append(dict(model=kind,forward=True,backward=True,optimizer_step=True,
                           registered_parameters=sum(p.numel() for p in model.parameters()),
                           active_gradient_parameters=active,total=float(total.detach()),
                           anatomy=float(anatomy.detach()),surface=float(surface.detach()),
                           inference_scoring_normal_path=True,unprompted_inference=True,decoded_levels=18,
                           provided_references_excluded=3 not in result['scored_levels'] and 14 not in result['scored_levels']))
    assert prior['source_cases'] and all(n>0 for n in prior['per_level_training_counts'])
    with np.load(rows[0]['pack']) as data:
        xyz,_=predict(prior,data['points_ras_mm'],data['references_ras_mm'])
        assert xyz.shape==(18,3) and np.isfinite(xyz).all()
    report=dict(status='NORMAL_PATH_PASS_NOT_FORMAL_EVAL',torch_version=torch.__version__,device='CPU',
                train_cases=[r['case'] for r in rows],test_cases_used=0,models=checks,
                baseline_prior_fit_and_projection=True,prior_training_counts=prior['per_level_training_counts'],
                seconds=time.time()-start,clinical_GT=False,
                code_sha256={name:hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()
                             for name in ['train_field.py','joint_surface_field.py','fit_field_prior.py','evaluate_field.py','check_model_paths.py']})
    (ROOT/'MODEL_PATH_CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
