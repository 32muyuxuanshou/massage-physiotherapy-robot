"""Native-output interventions for the four matched pilots; no training or TEST."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json
from pathlib import Path
import numpy as np
import torch
from fusion_r31 import R31Adapter
from diagnose_r31 import depth_features
from r3_common import load_official,read_cache,combine,cached_forward,metrics,aggregate,output_change,sha
from render_losses import MeshRenderer


def intervention(d,valid,rays,condition,seed,donor):
    if condition=='missing':return d,torch.zeros_like(valid)
    changed=depth_features(d,valid,rays,condition,seed,donor)[:,0:1]
    assert torch.equal((changed>0)&torch.isfinite(changed),valid.bool())
    return changed,valid


def response_summary(records):
    result={}
    for role in sorted({r['role'] for r in records}):
        ids=sorted({r['identity'] for r in records if r['role']==role})
        result[role]={k:np.asarray(np.mean([np.mean([r['response'][k] for r in records if r['identity']==i],axis=0)
            for i in ids],axis=0)).tolist() for k in records[0]['response']}
    return result


def main():
    torch.set_num_threads(2)
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--pilot',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mode',required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    official,_=load_official(a.root);model=R31Adapter(official,a.mode).cuda()
    ck=a.pilot/a.mode/'run/best.pt';model.fusion.load_state_dict(torch.load(ck,map_location='cuda',weights_only=False)['fusion'])
    model.eval();renderer=MeshRenderer(official.head_pose.faces)
    architectural={'geometry_attention':['no_3d_attention_bias','no_global_metric_context'],
        'mhr_refinement':['no_local_correspondence','translation_only']}.get(a.mode,[])
    conditions=['correct','flat_center','lowpass_shape','local_shuffle_fixed_mask','cross_identity_fixed_mask',
        'offset_-0.2','offset_0.2','missing']+architectural
    report=dict(mode=a.mode,checkpoint_sha256=sha(ck),inference_code_sha256=sha(Path(__file__).parent/'fusion_r31.py'),
        conditions={},test_used=False,architectural_ablations='inference interventions, not independently retrained architectures',
        wrong_depth='synthetic donor: next VAL identity, SAME native pose and physical camera; original mask/rays retained',
        real_metrics='correct real geometry in pilot/real/HUMMAN_RESULTS.json; here real parameter response only')
    for domain,cache in [('synthetic_VAL',a.root/'datasets/cache/native_scale_v2'),
        ('real_TRAIN_VAL',a.root/'datasets/cache/humman_development_v1')]:
        rows=json.loads((cache/'CACHE_MANIFEST.json').read_text())['records']
        if domain=='synthetic_VAL':rows=[r for r in rows if r['role']=='VAL']
        assert all(r['role']!='TEST' for r in rows)
        identities=sorted({r['identity'] for r in rows});lookup={(r['identity'],r['pose_id'],r['camera_id']):r for r in rows} if domain=='synthetic_VAL' else {}
        refs={};results={}
        for condition in conditions:
            if domain=='real_TRAIN_VAL' and condition=='cross_identity_fixed_mask':continue
            if a.mode=='geometry_attention':
                model.fusion.disable_geometry_bias=condition=='no_3d_attention_bias'
                model.fusion.disable_metric_context=condition=='no_global_metric_context'
            if a.mode=='mhr_refinement':
                model.fusion.disable_correspondence=condition=='no_local_correspondence'
                model.fusion.translation_only=condition=='translation_only'
            records=[]
            for start in range(0,len(rows),16):
                chunk=rows[start:start+16];rec=[read_cache(str(cache/r['cache_file'])) for r in chunk]
                b,f,d,valid,rays,gt,target,mask,K=combine(rec);donor=None
                if condition=='cross_identity_fixed_mask':
                    donors=[read_cache(str(cache/lookup[identities[(identities.index(r['identity'])+1)%len(identities)],
                        r['pose_id'],r['camera_id']]['cache_file'])) for r in chunk]
                    donor=(torch.cat([x['depth'] for x in donors]).cuda(),torch.cat([x['valid'] for x in donors]).cuda())
                dd,vv=intervention(d,valid,rays,condition if condition not in architectural else 'correct',11*10000+start,donor)
                with torch.no_grad():o=cached_forward(model,b,f,dd,vv,rays)
                values=metrics(o,gt,target,mask,K,renderer) if gt else None
                for j,row in enumerate(chunk):
                    key=row['cache_file'];single={k:x[j:j+1] for k,x in o.items() if torch.is_tensor(x)}
                    if condition=='correct':refs[key]={k:x.cpu() for k,x in single.items()}
                    ref={k:x.cuda() for k,x in refs[key].items()};response=output_change(single,ref)
                    response['global_rotation_parameter_change_rad']=float((single['global_rot']-ref['global_rot']).norm())
                    records.append(dict(identity=row['identity'],file=key,role=row['role'],sequence=row.get('sequence'),
                        frame=row.get('frame'),metrics=values[j] if values else None,response=response))
            results[condition]=dict(responses=response_summary(records),synthetic=aggregate(records) if values else None,records=records)
            report['conditions'][domain]=results
            (a.out/'CANDIDATE_ABLATIONS.json').write_text(json.dumps(report,indent=2))
            print('CANDIDATE_ABLATION',a.mode,domain,condition,
                results[condition]['synthetic']['identity_equal_mean']['vertex_camera_mm'] if values else results[condition]['responses'],flush=True)
    model._hook.remove()
    (a.out/'ABLATIONS_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',mode=a.mode,test_used=False)))


if __name__=='__main__':main()
