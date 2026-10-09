"""Actual native MHR RGB/RGB-D geometry training, independently split identities."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import torch
import roma
from fusion import RGBDBodyAdapter
from geometry import crop_registered_depth
from native_data import generate
from render_losses import MeshRenderer,loss_components
from check_native_r1 import parameter_hashes


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--source-commit',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--data',type=Path,required=True)
    args=p.parse_args()
    config=json.loads(args.config.read_text())
    args.out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(args.root/'external/sam-3d-body'))
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    start=time.monotonic()
    official,cfg=load_sam_3d_body(str(args.root/'checkpoints/official/sam-3d-body-vith/model.ckpt'),
        device='cuda',mhr_path=str(args.root/'checkpoints/official/sam-3d-body-vith/assets/mhr_model.pt'))
    official.requires_grad_(False)
    estimator=SAM3DBodyEstimator(official,cfg,human_detector=None,human_segmentor=None,fov_estimator=None)
    manifest=(json.loads((args.data/'MANIFEST.json').read_text()) if args.data.exists()
              else generate(official.head_pose,args.data,config['dataset_seed'],config['identities'],config['views_per_identity']))
    assert manifest['seed']==config['dataset_seed']
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    identity=dict(source_commit=args.source_commit,config_sha256=sha(args.config),
                  manifest_sha256=sha(args.data/'MANIFEST.json'),config=config)
    (args.out/'EXECUTION_IDENTITY.json').write_text(json.dumps(identity,indent=2))
    # Synthetic arrays fit in CPU RAM; no final-test pixels are loaded here.
    samples={}
    for row in manifest['samples']:
        if row['role']=='TEST':continue
        path=args.data/row['file'];assert sha(path)==row['sha256']
        with np.load(path) as npz: samples[row['file']]={k:npz[k] for k in npz.files}
    train=[r for r in manifest['samples'] if r['role']=='TRAIN']
    val=[r for r in manifest['samples'] if r['role']=='VAL']
    renderer=MeshRenderer(official.head_pose.faces)
    # Preprocess once with the exact official affine. Original K and metric depth
    # remain available for rendering, and prepared tensors are cloned per forward.
    cache={}
    for row in train+val:
        d=samples[row['file']]
        b=prepare_batch(d['rgb'],estimator.transform,d['bbox'][None],masks=d['mask'].astype(np.uint8)[None],
                        cam_int=torch.from_numpy(d['K'][None]))
        depth=torch.from_numpy(d['depth_m'][None,None])
        cropped,valid,rays=crop_registered_depth(depth,b)
        truth={k:torch.from_numpy(v).cuda() for k,v in d.items()
               if k in ['pred_vertices','pred_keypoints_3d','pred_joint_coords','pred_cam_t',
                         'body_pose','global_rot','shape','scale','hand']}
        cache[row['file']]=(recursive_to(b,'cuda'),cropped.cuda(),valid.cuda(),rays.cuda(),truth,
                            depth[:,0].cuda(),torch.from_numpy(d['mask'][None]).float().cuda(),
                            torch.from_numpy(d['K'][None]).cuda())
    def predict(model,row,ablation='correct'):
        b,d,v,r,gt,dep,mask,K=cache[row['file']]
        if ablation=='missing':v=torch.zeros_like(v)
        if ablation=='offset_0.2m':d=d+.2
        if ablation=='shuffled':
            other=val[(val.index(row)+1)%len(val)]
            d,v=cache[other['file']][1:3]  # Keep the actual RGB camera rays fixed.
        return model(copy.deepcopy(b),d,v,r),gt,dep,mask,K
    def metrics(o,gt,dep,mask,K):
        v=o['pred_vertices'];tv=gt['pred_vertices'];cam=o['pred_cam_t'];tc=gt['pred_cam_t']
        rd,sil=renderer(v+cam[:,None],K)
        common=mask.bool() & (rd>0)
        residual=(rd[common]-dep[common]).abs()*1000
        rotation=roma.euler_to_rotmat('ZYX',o['global_rot'])
        target_rotation=roma.euler_to_rotmat('ZYX',gt['global_rot'])
        cosine=((rotation.transpose(-1,-2)@target_rotation).diagonal(dim1=-2,dim2=-1).sum(-1)-1)/2
        return dict(vertex_body_mm=float((v-tv).norm(dim=-1).mean()*1000),
            vertex_camera_mm=float((v+cam[:,None]-tv-tc[:,None]).norm(dim=-1).mean()*1000),
            vertex_translation_removed_mm=float(((v-v.mean(1,keepdim=True))-(tv-tv.mean(1,keepdim=True))).norm(dim=-1).mean()*1000),
            joint_mm=float((o['pred_joint_coords']-gt['pred_joint_coords']).norm(dim=-1).mean()*1000),
            camera_mm=float((cam-tc).norm(dim=-1).mean()*1000),
            shape_rmse=float((o['shape']-gt['shape']).square().mean().sqrt()),
            scale_rmse=float((o['scale']-gt['scale']).square().mean().sqrt()),
            global_rotation_deg=float(torch.acos(cosine.clamp(-1,1)).mean()*180/np.pi),
            body_pose_periodic_mean_deg=float(torch.atan2(torch.sin(o['body_pose']-gt['body_pose']),
                torch.cos(o['body_pose']-gt['body_pose'])).abs().mean()*180/np.pi),
            depth_common_median_mm=float(residual.median()) if len(residual) else None,
            depth_common_p95_mm=float(torch.quantile(residual,.95)) if len(residual) else None,
            depth_hit_rate=float(common.sum()/mask.sum()),
            silhouette_iou=float(((sil>.5)&mask.bool()).sum()/((sil>.5)|mask.bool()).sum()))
    def evaluate(model,method,epoch,ablation='correct',save=False):
        records=[]
        with torch.no_grad():
            for row in val:
                o,gt,dep,mask,K=predict(model,row,ablation)
                records.append(dict(identity=row['identity'],file=row['file'],method=method,epoch=epoch,
                                    ablation=ablation,metrics=metrics(o,gt,dep,mask,K)))
                if save:
                    directory=args.out/'predictions'/method/ablation;directory.mkdir(parents=True,exist_ok=True)
                    np.savez_compressed(directory/row['file'],**{k:t.cpu().numpy() for k,t in o.items() if torch.is_tensor(t)})
        # Each identity contributes equally, after averaging its eight fixed views.
        groups={i:[r for r in records if r['identity']==i] for i in sorted({r['identity'] for r in records})}
        means={i:{k:float(np.mean([r['metrics'][k] for r in rs if r['metrics'][k] is not None]))
                  for k in records[0]['metrics']} for i,rs in groups.items()}
        summary={k:float(np.mean([m[k] for m in means.values()])) for k in records[0]['metrics']}
        return dict(method=method,epoch=epoch,ablation=ablation,subject_equal_mean=summary,per_identity=means,records=records)
    before=parameter_hashes(official)
    results=[];curves=[]
    # Gate=0 is the same Official model, with precisely the same prepared inputs.
    baseline=RGBDBodyAdapter(official,mode='residual').cuda()
    results.append(evaluate(baseline,'official',0,save=True))
    baseline._hook.remove();del baseline
    for mode in config['methods']:
        torch.manual_seed(config['train_seed']);rng=np.random.default_rng(config['train_seed'])
        model=RGBDBodyAdapter(official,mode=mode).cuda()
        parameters=[x for x in model.fusion.parameters() if x.requires_grad]
        optimizer=torch.optim.AdamW(parameters,lr=config['lr'],weight_decay=config['weight_decay'])
        mode_out=args.out/mode;mode_out.mkdir()
        log=(mode_out/'training.jsonl').open('w')
        for epoch in range(1,config['epochs']+1):
            losses=[];epoch_start=time.monotonic()
            for step,index in enumerate(rng.permutation(len(train))):
                row=train[index];optimizer.zero_grad(set_to_none=True)
                o,gt,dep,mask,K=predict(model,row)
                c=loss_components(o,gt,dep,mask,K,renderer)
                loss=sum(config['loss_weights'][k]*x for k,x in c.items())
                assert torch.isfinite(loss),'NONFINITE_TRAINING_LOSS'
                loss.backward();torch.nn.utils.clip_grad_norm_(parameters,config['gradient_clip_norm'])
                grads={k:None if p.grad is None else float(p.grad.norm()) for k,p in model.fusion.named_parameters()}
                optimizer.step();losses.append(float(loss.detach()))
                log.write(json.dumps(dict(epoch=epoch,step=step,file=row['file'],loss=losses[-1],
                    components={k:float(x.detach()) for k,x in c.items()},gradients=grads))+'\n')
            log.flush()
            validation=evaluate(model,mode,epoch)
            curve=dict(method=mode,epoch=epoch,train_mean_loss=float(np.mean(losses)),
                       seconds=time.monotonic()-epoch_start,val=validation['subject_equal_mean'])
            curves.append(curve);print(json.dumps(curve),flush=True)
            (args.out/'CURVES.json').write_text(json.dumps(curves,indent=2))
            torch.save(dict(fusion=model.fusion.state_dict(),optimizer=optimizer.state_dict(),mode=mode,
                epoch=epoch,execution_identity=identity,trainable_parameters=sum(p.numel() for p in parameters)),
                mode_out/'last.pt')
        log.close()
        results.append(evaluate(model,mode,config['epochs'],save=True))
        if mode!='rgb_only':
            for ablation in ['missing','shuffled','offset_0.2m']:
                results.append(evaluate(model,mode,config['epochs'],ablation,save=True))
        assert before==parameter_hashes(official),'OFFICIAL_PARAMETER_VALUES_CHANGED'
        model._hook.remove();del model,optimizer
    report=dict(status='TRAINING_AND_SYNTHETIC_VALIDATION_COMPLETED_NOT_REAL_VALIDATION',
        execution_identity=identity,train_samples=len(train),val_samples=len(val),test_evaluated=False,
        final_results=results,curves=curves,frozen_official_values_unchanged=True,
        frozen_parameter_count=len(before),peak_memory_bytes=torch.cuda.max_memory_allocated(),
        seconds=time.monotonic()-start,limitations=config['limitations'])
    (args.out/'R2_PILOT_RESULTS.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(status=report['status'],seconds=report['seconds'])),flush=True)


if __name__=='__main__':main()
