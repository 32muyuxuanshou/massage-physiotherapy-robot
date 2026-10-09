"""Fixed-mask numerical Depth and trained-mechanism interventions, no TEST."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json
from pathlib import Path
import torch
from fusion_r4 import R4Adapter
from ablate_r31_candidates import intervention,response_summary
from r3_common import load_official,read_cache,combine,cached_forward,metrics,aggregate,output_change,sha
from render_losses import MeshRenderer


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--checkpoint',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);torch.set_num_threads(2)
    state=torch.load(a.checkpoint,weights_only=False);mode=state['mode'];official,_=load_official(a.root)
    model=R4Adapter(official,mode).cuda();model.fusion.load_state_dict(state['fusion']);renderer=MeshRenderer(official.head_pose.faces)
    conditions=['correct','flat_center','lowpass_shape','cross_identity_fixed_mask','local_shuffle_fixed_mask','offset_-0.2','offset_0.2','missing']
    if mode in ['g1','g3']:conditions.append('no_metric_camera')
    if mode in ['g2','g3']:conditions.append('no_xyz_bias')
    report=dict(mode=mode,checkpoint_sha256=sha(a.checkpoint),test_read=False,conditions={},
        wrong_depth='next VAL identity, same pose/camera label, original valid mask/rays unchanged',
        mechanism_interventions='inference flags, not independently retrained models; B surface scores are in real evaluator')
    for domain,cache in [('synthetic_VAL',a.root/'datasets/cache/native_scale_v2'),('real_TRAIN_VAL',a.root/'datasets/cache/humman_development_v1')]:
        rows=json.loads((cache/'CACHE_MANIFEST.json').read_text())['records']
        if domain=='synthetic_VAL':rows=[r for r in rows if r['role']=='VAL']
        assert all(r['role']!='TEST' for r in rows);ids=sorted({r['identity'] for r in rows})
        lookup={(r['identity'],r['pose_id'],r['camera_id']):r for r in rows} if domain=='synthetic_VAL' else {}
        refs={};results={}
        for condition in conditions:
            if condition=='cross_identity_fixed_mask' and domain!='synthetic_VAL':continue
            if model.fusion.camera is not None:model.fusion.camera.disabled=condition=='no_metric_camera'
            if mode in ['g2','g3']:model.fusion.spatial.disable_geometry=condition=='no_xyz_bias'
            records=[]
            for start in range(0,len(rows),16):
                chunk=rows[start:start+16];rec=[read_cache(str(cache/r['cache_file'])) for r in chunk]
                b,f,d,v,rays,gt,target,mask,K=combine(rec);donor=None
                if condition=='cross_identity_fixed_mask':
                    donor_rows=[lookup[ids[(ids.index(r['identity'])+1)%len(ids)],r['pose_id'],r['camera_id']] for r in chunk]
                    donor_rec=[read_cache(str(cache/r['cache_file'])) for r in donor_rows]
                    donor=(torch.cat([r['depth'] for r in donor_rec]).cuda(),torch.cat([r['valid'] for r in donor_rec]).cuda())
                dd,vv=intervention(d,v,rays,condition if not condition.startswith('no_') else 'correct',110000+start,donor)
                with torch.no_grad():o=cached_forward(model,b,f,dd,vv,rays)
                values=metrics(o,gt,target,mask,K,renderer) if gt else None
                for j,r in enumerate(chunk):
                    single={k:x[j:j+1] for k,x in o.items() if torch.is_tensor(x)};key=r['cache_file']
                    if condition=='correct':refs[key]={k:x.cpu() for k,x in single.items()}
                    response=output_change(single,{k:x.cuda() for k,x in refs[key].items()})
                    records.append(dict(identity=r['identity'],role=r['role'],file=key,sequence=r.get('sequence'),frame=r.get('frame'),metrics=values[j] if values else None,response=response))
            results[condition]=dict(responses=response_summary(records),synthetic=aggregate(records) if values else None,records=records)
            report['conditions'][domain]=results;(a.out/'DEPTH_ABLATIONS.json').write_text(json.dumps(report,indent=2))
            print('ABLATION',mode,domain,condition,flush=True)
    model.remove_hooks();(a.out/'ABLATIONS_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',test_read=False)))
