"""Small CPU Camera-only self-supervised fit. No Camera B observations read.

TRAIN targets use frozen Official raw six-step A Txyz, including unapplied
>177.888 mm diagnostics. The baseline fallback rule is unchanged. Ridge strength
uses leave-one-TRAIN-identity-out target prediction. Training domain changes
from R4 synthetic to real A pseudo-supervision: this is a mechanism pilot,
not a matched-budget architecture superiority test.
"""
import argparse
import json
from pathlib import Path
import time
from camera_only_r42 import features, fit, np
from run_r41_txyz import sha


def main(a):
    start=time.monotonic();a.out.mkdir(parents=True,exist_ok=False)
    source=a.source;assets=source/'assets'
    frame_rows=json.loads((source/'FRAME_CONTRACT.json').read_text())['records']
    training_ids=sorted({r['identity'] for r in frame_rows if r['role']=='TRAIN'})
    old=json.loads((source/'PAIRED_RESULTS.json').read_text())
    refs=[r for r in old['records'] if r['cell']=='official' and r['identity'] in training_ids]
    assert len(refs)==192 and all(r['role']=='TRAIN' for r in refs)
    config=dict(stage='R4.2_CAMERA_ONLY_CPU_PILOT',train_ids=training_ids,train_frames=192,
        target='Official pred_cam_t + historical raw 6-step A Txyz (even when baseline fallback applied zero)',
        target_is_ground_truth=False,teacher_camera='A',camera_B_read_for_training=False,
        input='12 centered observed/body-anchor IQR geometry features; absolute median XYZ in explicit base',
        architecture='metric translation-equivariant base + 12-to-3 ridge affine surface/root offset',
        trainable_coefficients=39,body_frozen=True,regularization_candidates=[.1,1.,10.,100.],
        selection='leave-one-TRAIN-identity-out identity-equal teacher root L2; tie lower listed lambda',
        evaluation='original 232 frames after model frozen; B not used for model selection',
        training_domain_change='R4 synthetic supervised versus this real TRAIN A pseudo-supervised pilot',
        training_seed='not applicable: deterministic closed-form ridge, no random init or shuffle',
        trainable_network_decoding=False,test_read=False,head_sha256=sha(Path(__file__).parent/'camera_only_r42.py'),
        trainer_sha256=sha(Path(__file__)),source_paired_sha256=sha(source/'PAIRED_RESULTS.json'))
    (a.out/'TRAIN_CONFIG.json').write_text(json.dumps(config,indent=2))
    faces=np.load(assets/'original_assets/official/faces.npy')
    anchor=np.load(assets/'runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz')
    xx=[];yy=[];bases=[];identities=[];receipts=[]
    for r in refs:
        key=r['key'];zpath=assets/'original_assets/official'/(key+'.npz')
        assert sha(zpath)==r['input_sha256']
        z=np.load(zpath);p=np.load(assets/'original_assets/inputs'/(key+'.npz'))['points_camera_A']
        body=z['vertices_camera_A'].astype(np.float64)-z['pred_cam_t'].reshape(3)
        anchors=(body[faces[anchor['face_index']]]*anchor['barycentric'][:,:,None]).sum(1)
        base,x=features(p,anchors)
        teacher=z['pred_cam_t'].reshape(3)+np.asarray(r['raw_translation_m'])
        xx.append(x);yy.append(teacher-base);bases.append(base);identities.append(r['identity'])
        receipts.append(dict(key=key,identity=r['identity'],role='TRAIN',official_sha256=r['input_sha256'],
                             teacher_cam_m=teacher.tolist(),raw_txyz_m=r['raw_translation_m'],baseline_fallback=r['fallback']))
    x,y,bases=np.asarray(xx),np.asarray(yy),np.asarray(bases);identities=np.array(identities)
    candidates=[]
    for lam in config['regularization_candidates']:
        errors=[];folds=[]
        for heldout in training_ids:
            train=identities!=heldout;test=~train
            weights=np.array([1./np.sum(identities[train]==i) for i in identities[train]])
            state=fit(x[train],y[train],lam,weights)
            predicted=np.column_stack(((x[test]-state['mean'])/state['std'],np.ones(test.sum())))@state['coefficients']
            error=float(np.linalg.norm(predicted-y[test],axis=1).mean()*1000)
            errors.append(error);folds.append(dict(heldout_TRAIN_identity=heldout,teacher_root_mean_L2_mm=error))
        candidates.append(dict(regularization=lam,identity_equal_teacher_root_error_mm=float(np.mean(errors)),folds=folds))
    best=min(candidates,key=lambda r:r['identity_equal_teacher_root_error_mm'])
    weights=np.array([1./np.sum(identities==i) for i in identities])
    state=fit(x,y,best['regularization'],weights)
    np.savez(a.out/'camera_only_best.npz',**state)
    np.savez_compressed(a.out/'TRAIN_A_FEATURES_AND_TARGETS.npz',features=x,target_offset=y,base_camera=bases,identities=identities)
    (a.out/'TRAIN_TARGET_MANIFEST.json').write_text(json.dumps(receipts,indent=2))
    report=dict(status='TRAINED_FROZEN_FOR_EVALUATION',config=config,selected=best,candidates=candidates,
        model_sha256=sha(a.out/'camera_only_best.npz'),seconds=time.monotonic()-start,
        official_parameters_updated=False,camera_B_read=False,VAL_targets_used=False,
        feature_condition_number=float(np.linalg.cond(np.column_stack(((x-state['mean'])/state['std'],np.ones(len(x)))))))
    (a.out/'TRAINING_RESULT.json').write_text(json.dumps(report,indent=2))
    print('CAMERA_ONLY_TRAINED',best['regularization'],best['identity_equal_teacher_root_error_mm'],report['seconds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);main(p.parse_args())
