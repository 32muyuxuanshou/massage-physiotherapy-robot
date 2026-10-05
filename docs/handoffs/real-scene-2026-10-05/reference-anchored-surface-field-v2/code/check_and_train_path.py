"""One fixed four-TRAIN structural run; never a source/test accuracy experiment."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from anchored_field import AnchoredField
from reference_frame import make_frame, to_local, from_local, serializable
from source_batch import sample_pack, stack

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent/'anatomical-surface-method-foundation-v1/structure_check'
PRIVATE = Path(__file__).resolve().parents[5]/'output/reference_anchored_surface_field_v2'


def losses(pred, batch, joint):
    anatomy = F.smooth_l1_loss(pred['anatomical_coordinates'], batch['anatomical_coordinates'], beta=.05)
    geometry = F.smooth_l1_loss(pred['ray_delta'], batch['ray_target'], beta=.02)
    return anatomy + .25*geometry if joint else anatomy, anatomy, geometry


def main():
    torch.set_num_threads(4); start=time.time()
    PRIVATE.mkdir(parents=True,exist_ok=True)
    rows=json.loads((SOURCE/'CASE_MANIFEST.json').read_text())
    examples=[];identities=[]
    for i,row in enumerate(rows):
        item,identity=sample_pack(SOURCE/row['case']/'field_pack.npz',1700+i,256,128)
        assert len(np.intersect1d(identity['observed_indices'],identity['query_indices']))==0
        examples.append(item);identities.append(identity)
    batch=stack(examples); checks=[];checkpoint=None
    for mode in ['SOFT_ANATOMY','HARD_ANATOMY','HARD_JOINT']:
        torch.manual_seed(17);model=AnchoredField()
        optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
        trace=[]
        for step in range(40):
            pred=model(batch['observed'],batch['query'],batch['references'],batch['reference_present'],batch['query_rays'],hard=mode!='SOFT_ANATOMY')
            total,anatomy,geometry=losses(pred,batch,mode=='HARD_JOINT')
            assert torch.isfinite(total);optimizer.zero_grad();total.backward();optimizer.step()
            trace.append(dict(step=step,total=float(total.detach()),anatomy=float(anatomy.detach()),geometry=float(geometry.detach())))
        model.eval()
        with torch.no_grad():
            pred=model(batch['observed'],batch['query'],batch['references'],batch['reference_present'],batch['query_rays'],hard=mode!='SOFT_ANATOMY')
            rays=torch.zeros_like(batch['references']);rays[...,1]=1
            anchors=model(batch['observed'],batch['references'],batch['references'],batch['reference_present'],rays,hard=mode!='SOFT_ANATOMY')
        expected=torch.tensor([[[0.,0.],[1.,0.]]]).expand(4,-1,-1)
        anchor_error=float((anchors['anatomical_coordinates']-expected).abs().max())
        if mode!='SOFT_ANATOMY':assert anchor_error<1e-6
        cache=ROOT/'checks'/(mode+'.npz')
        np.savez_compressed(cache,**{k:v.numpy() for k,v in batch.items()},
                            predicted_anatomy=pred['anatomical_coordinates'].numpy(),predicted_ray_delta=pred['ray_delta'].numpy(),
                            endpoint_coordinates=anchors['anatomical_coordinates'].numpy())
        record=dict(mode=mode,steps=40,normal_path='PASS',train_only=True,
                    trace=trace,max_anchor_coordinate_error=anchor_error,
                    surface_head_trained=mode=='HARD_JOINT',
                    geometry_applied=mode=='HARD_JOINT',
                    raw_head_ray_absolute_error_mm=float((pred['ray_delta']-batch['ray_target']).abs().median()*500),
                    applied_ray_absolute_error_mm=float(((pred['ray_delta'] if mode=='HARD_JOINT' else 0)-batch['ray_target']).abs().median()*500),
                    zero_correction_ray_absolute_error_mm=float(batch['ray_target'].abs().median()*500),
                    cache_sha256=hashlib.sha256(cache.read_bytes()).hexdigest())
        checks.append(record)
        if mode=='HARD_JOINT':
            checkpoint=PRIVATE/'STRUCTURE_ONLY_HARD_JOINT.pt';torch.save(model.state_dict(),checkpoint)
    # Same explicit input frame under a rigid coordinate change and mm/m conversion.
    f=identities[0]['frame'];references=batch['references'][0].numpy()
    original=from_local(batch['query'][0].numpy(),f)
    rng=np.random.default_rng(707);rotation,_=np.linalg.qr(rng.normal(size=(3,3)))
    if np.linalg.det(rotation)<0:rotation[:,0]*=-1
    translation=np.array([430.,-110.,270.])
    world_refs=from_local(references,f)
    moved_refs=(world_refs@rotation.T+translation)/1000.
    moved_posterior=f['basis'][:,1]@rotation.T
    moved_frame=make_frame(moved_refs,moved_posterior,1000.)
    moved=(original@rotation.T+translation)/1000.
    difference=float(np.max(abs(to_local(moved,moved_frame)-batch['query'][0].numpy())))
    assert difference<1e-6
    identities_json=[dict(case=rows[i]['case'],source_pack_sha256=hashlib.sha256((SOURCE/rows[i]['case']/'field_pack.npz').read_bytes()).hexdigest(),
                         observed_indices=d['observed_indices'].tolist(),query_indices=d['query_indices'].tolist(),
                         camera_ras_mm=d['camera_ras_mm'].tolist(),frame=serializable(d['frame'])) for i,d in enumerate(identities)]
    (ROOT/'checks/SOURCE_INPUT_IDENTITY.json').write_text(json.dumps(identities_json,indent=2)+'\n')
    report=dict(status='STRUCTURAL_TRAINING_AND_FRAME_PASS_NOT_ACCURACY_VALIDATION',source_TRAIN_cases=[r['case'] for r in rows],
                test_cases_used=0,device='CPU',torch_version=torch.__version__,seconds=time.time()-start,
                models=checks,rigid_and_unit_transform_max_difference=difference,
                checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),checkpoint_private_path=str(checkpoint),
                full_training=False,clinical_validation=False)
    (ROOT/'checks/MODEL_PATH_RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='models'}),flush=True)
    print(json.dumps([{k:v for k,v in r.items() if k!='trace'} for r in checks]),flush=True)


if __name__=='__main__':main()
