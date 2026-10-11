"""Fixed metadata-only subsets; hold RGB/K/rays/mask for value ablations."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0');os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json
from pathlib import Path
import numpy as np
import torch
from data import rows,batch,read
from engine import Engine
from evaluate import BODY_KEYS,native_group
from r3_common import metrics,output_change,sha

VARIANTS=['correct','cross_identity','other_pose_or_frame','local_value_shuffle','absolute_Z_only',
 'relative_Z_at_TRAIN_median','mask_rays_only_Z1m','missing_depth','Z_minus_100mm','Z_plus_100mm','density_stride3']

def selection(records,domain):
    if domain=='native':return [r for r in records if r['role']=='VAL' and r['identity'] in sorted({v['identity'] for v in records if v['role']=='VAL'})[:8]]
    chosen=[]
    for identity in sorted({r['identity'] for r in records}):
        rr=sorted([r for r in records if r['identity']==identity],key=lambda r:r['cache_file'])
        chosen.extend([rr[0],rr[-1]])
    return chosen

def donor(row,pool,domain,other_identity):
    candidates=[r for r in pool if r['role']==row['role'] and (r['identity']!=row['identity'] if other_identity else r['identity']==row['identity'] and r['cache_file']!=row['cache_file'])]
    if domain=='native':
        candidates=[r for r in candidates if r['camera_id']==row['camera_id'] and (r['pose_id']==row['pose_id'] if other_identity else r['pose_id']!=row['pose_id'])]
    return sorted(candidates,key=lambda r:r['cache_file'])[0]

def perturb(x,variant,records,pool,domain,mean_z):
    out=dict(x);d=x['depth'].clone();v=x['valid'].clone();info=[]
    for i,row in enumerate(records):
        mask=v[i];original=d[i][mask];median=original.median();record={}
        if variant in ['cross_identity','other_pose_or_frame']:
            source=donor(row,pool,domain,variant=='cross_identity');z=read(source['path']);other=z['depth'].to(d.device)
            other_valid=z['valid'].to(d.device);fill=other[other_valid].median()
            transplant=torch.where(other_valid,other,fill)
            d[i]=torch.where(mask,transplant[0],0)
            record=dict(donor=source['cache_file'],donor_identity=source['identity'],operation='Z transplanted in normalized person crop; target valid/rays/K unchanged')
        elif variant=='local_value_shuffle':
            # Shuffle values within 32x32 blocks, retaining spatial support.
            g=torch.Generator(device=d.device).manual_seed(20261011+i)
            for yy in range(0,d.shape[-2],32):
                for xx in range(0,d.shape[-1],32):
                    region=d[i,:,yy:yy+32,xx:xx+32];mv=mask[:,yy:yy+32,xx:xx+32];values=region[mv]
                    region[mv]=values[torch.randperm(len(values),generator=g,device=d.device)]
        elif variant=='absolute_Z_only':d[i]=torch.where(mask,median,0)
        elif variant=='relative_Z_at_TRAIN_median':d[i]=torch.where(mask,d[i]-median+mean_z,0)
        elif variant=='mask_rays_only_Z1m':d[i]=mask.float()
        elif variant=='missing_depth':d[i].zero_();v[i].zero_()
        elif variant.startswith('Z_'):d[i]=torch.where(mask,d[i]+(-.1 if 'minus' in variant else .1),0)
        elif variant=='density_stride3':
            K=x['K'][i];ray=x['rays'][i];u=(ray[0]*K[0,0]+K[0,2]).round().long();yy=(ray[1]*K[1,1]+K[1,2]).round().long()
            v[i]&=((u%3)==0)&((yy%3)==0);d[i]=torch.where(v[i],d[i],0)
        info.append(record)
    out.update(depth=d,valid=v);return out,info

def run(a):
    torch.set_num_threads(2);paths=json.loads(a.paths.read_text());state=torch.load(a.checkpoint,map_location='cpu',weights_only=False)
    assert state['identity']['mode']==a.mode and state['identity']['seed']==a.seed
    engine=Engine(a.mode,paths);engine.load_checkpoint_state(state['model']);engine.eval()
    mean_z=json.loads(Path(paths['normalizer']).read_text())['mean'][2];a.out.mkdir(parents=True,exist_ok=True)
    result=[];spec={}
    variants=VARIANTS+(['fine_disabled','direction_filter_disabled'] if a.mode=='full' else [])
    with torch.no_grad():
        for domain in ['native','real']:
            pool=rows(paths[domain+'_cache'],domain);chosen=selection(pool,domain)
            assert len(chosen)==(64 if domain=='native' else 44)
            spec[domain]=[r['cache_file'] for r in chosen]
            for offset in range(0,len(chosen),8):
                rr=chosen[offset:offset+8];x=batch(rr);reference,_=engine(x)
                for variant in variants:
                    xx,donors=perturb(x,variant,rr,pool,domain,mean_z)
                    if a.mode=='full':engine.model.gating=variant!='direction_filter_disabled'
                    o,tr=engine(xx,enable_fine=variant!='fine_disabled')
                    values=metrics(o,x['truth'],x['target_depth'],x['target_mask'],x['K'],engine.renderer) if domain=='native' else [{} for _ in rr]
                    for i,row in enumerate(rr):
                        change=output_change({k:o[k][i:i+1] for k in BODY_KEYS+['pred_cam_t']},
                                             {k:reference[k][i:i+1] for k in BODY_KEYS+['pred_cam_t']})
                        world=o['pred_vertices'][i]+o['pred_cam_t'][i]
                        reference_world=reference['pred_vertices'][i]+reference['pred_cam_t'][i]
                        change['vertex_camera_change_mm']=float((world-reference_world).norm(dim=-1).mean()*1000)
                        if a.mode=='rgb_only':assert change['camera_change_mm']<.005 and change['vertex_camera_change_mm']<.005,('RGB_ONLY_READS_DEPTH',domain,variant,row['cache_file'],change,
                            {k:float((o[k][i].float()-reference[k][i].float()).abs().max()) for k in ['pred_vertices','pred_cam_t','body_pose','shape','scale']})
                        if a.mode in ['pooled_mlp','coarse','full']:assert all(torch.equal(o[k][i],x['official'][k][i]) for k in BODY_KEYS)
                        item=dict(dataset=domain,variant=variant,identity=row['identity'],role=row['role'],cache_file=row['cache_file'],
                            metrics=values[i],response=change,depth_donor=donors[i],camera_xyz_m=o['pred_cam_t'][i].tolist(),
                            fine_delta_m=tr['fine_delta'][i].tolist())
                        result.append(item)
                    if a.mode=='full':engine.model.gating=True
            print('DEPTH_ABLATION_COMPLETE',a.mode,a.seed,domain,len(chosen),len(variants),flush=True)
    aggregates={v:native_group([dict(r,metrics=r['metrics']) for r in result if r['dataset']=='native' and r['variant']==v]) for v in variants}
    (a.out/'RESULTS.json').write_text(json.dumps(dict(status='COMPLETE',mode=a.mode,seed=a.seed,records=result,native_aggregated=aggregates,
        selection=spec,selection_policy='native first8 VAL identities/all8 views; real first/last available frame per identity; metadata only',
        checkpoint_sha256=sha(a.checkpoint),frozen_TRAIN_median_reference_m=mean_z,TEST_read=False,camera_B_read=False,
        RGB_only_numeric_repeat_tolerance_mm=.005,
        RGB_only_numeric_note='correct-input repeat itself can differ by sub-micrometre GPU floating-point rounding; retain actual responses, do not call this Depth use',
        interpretation='native GT measures actual geometric value; real subset reports output sensitivity only, not Camera-B accuracy; raw main real evaluation is separate',
        fixed_fields='RGB, K, rays, bbox, frozen Body; valid held fixed for value tests; missing/density explicitly change valid',
        fine_inference_toggle='supporting intervention on same trained weights; not separately retrained architecture ablation'),indent=2))
    engine.close()
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['paths','checkpoint','out']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--mode',required=True);p.add_argument('--seed',type=int,required=True);run(p.parse_args())
