"""Audit V1 trainable tensors and fixed-input MHR output changes; no training."""
from __future__ import annotations
import argparse, hashlib, json, os, platform, subprocess, sys
from pathlib import Path
import numpy as np
import torch

def sha_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()
def sha_tensor(x): return hashlib.sha256(x.detach().cpu().contiguous().numpy().tobytes()).hexdigest()
def stats(x):
    a=x.detach().cpu().double().reshape(-1)
    return {"l1_sum":float(a.abs().sum()),"l2_norm":float(a.norm()),"max_abs":float(a.abs().max())}
def summary(v):
    a=np.asarray(v,float)
    return {"mean":float(a.mean()),"median":float(np.median(a)),"p90":float(np.quantile(a,.9)),"max":float(a.max())}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--sam-repo',type=Path,required=True); ap.add_argument('--official',type=Path,required=True)
    ap.add_argument('--mhr',type=Path,required=True); ap.add_argument('--e1',type=Path,required=True); ap.add_argument('--e10',type=Path,required=True)
    ap.add_argument('--dev-cache',type=Path,required=True); ap.add_argument('--server-trainer',type=Path,required=True); ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    official=torch.load(a.official,map_location='cpu'); e1=torch.load(a.e1,map_location='cpu'); e10=torch.load(a.e10,map_location='cpu')
    entries=[]
    prefixes={'pose':'head_pose.proj.','camera':'head_camera.proj.'}
    for group,prefix in prefixes.items():
        for name,t1 in e1['heads'][group].items():
            key=prefix+name; t0=official[key]; t10=e10['heads'][group][name]
            entries.append({'parameter_name':key,'module':prefix[:-1],'shape':list(t0.shape),'numel':t0.numel(),
                'initial_sha256':sha_tensor(t0),'e1_sha256':sha_tensor(t1),'e10_sha256':sha_tensor(t10),
                'official_to_e1':stats(t1-t0),'official_to_e10':stats(t10-t0)})
    audit={'status':'AUDITED','actual_trainable_scope':['head_pose.proj','head_camera.proj'],
           'total_trainable_numel':sum(x['numel'] for x in entries),'parameters':entries,
           'conclusion':'The entire 519-output pose projection FFN and 3-output camera projection FFN were trainable. Output-block freezing was not implemented.'}
    (a.out/'TRAINABLE_PARAMETER_AUDIT_V1.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')

    sys.path.insert(0,str(a.sam_repo)); from sam_3d_body import SAM3DBodyEstimator,load_sam_3d_body
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    model,cfg=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr)); model.eval(); est=SAM3DBodyEstimator(model,cfg)
    files=sorted(a.dev_cache.glob('*.npz'))
    # One deterministic frame per exposed DEV subject.
    chosen=[]; seen=set()
    for p in files:
        sid=p.name.split('_')[0]
        if sid not in seen: chosen.append(p); seen.add(sid)
    fields=['pred_cam_t','global_rot','body_pose','shape','scale','derived_mhr_scales','hand','face','pred_vertices']
    outputs={k:{} for k in ['official','e1','e10']}
    def load_heads(cp):
        if cp is None:
            sd=official
            model.head_pose.proj.load_state_dict({k[len(prefixes['pose']):]:v for k,v in sd.items() if k.startswith(prefixes['pose'])})
            model.head_camera.proj.load_state_dict({k[len(prefixes['camera']):]:v for k,v in sd.items() if k.startswith(prefixes['camera'])})
        else:
            d=torch.load(cp,map_location='cpu'); model.head_pose.proj.load_state_dict(d['heads']['pose']); model.head_camera.proj.load_state_dict(d['heads']['camera'])
    for label,cp in [('official',None),('e1',a.e1),('e10',a.e10)]:
        load_heads(cp)
        with torch.no_grad():
            for p in chosen:
                with np.load(p) as z: rgb=z['rgb_a'].copy(); bbox=z['bbox_a'][None].astype(np.float32); K=z['K_a'][None].copy()
                batch=prepare_batch(rgb,est.transform,bbox,None,None); batch=recursive_to(batch,'cuda'); batch['cam_int']=torch.as_tensor(K,device='cuda').to(batch['img'])
                model._initialize_batch(batch); o=model.forward_step(batch,decoder_type='body')['mhr']
                values={f:o[f].detach().cpu().numpy() for f in fields if f != 'derived_mhr_scales'}
                values['derived_mhr_scales']=(model.head_pose.scale_mean[None,:]
                    + o['scale'] @ model.head_pose.scale_comps).detach().cpu().numpy()
                outputs[label][p.stem]=values
    rows=[]
    for target in ['e1','e10']:
        for f in fields:
            vals=[]
            for sid in outputs['official']:
                d=outputs[target][sid][f]-outputs['official'][sid][f]
                if f == 'global_rot': d=np.arctan2(np.sin(d),np.cos(d))
                vals.append(float(np.linalg.norm(d.reshape(-1))/np.sqrt(d.size)))
            rows.append({'comparison':f'official_to_{target}','field':f,'delta_rms_per_observation':summary(vals),'nonzero':bool(max(vals)>0)})
    out={'status':'FIXED_INPUT_FORWARD_AUDITED','inputs':[p.stem for p in chosen],
         'fixed_contract':['same RGB','same dataset bbox','same K','same preprocessing','deterministic eval mode'],
         'delta_unit_notes':{'pred_cam_t':'meters','global_rot':'wrapped Euler radians','body_pose':'Euler radians','shape/scale/hand/face':'native coefficient units','derived_mhr_scales':'MHR native scale values','pred_vertices':'meters'},
         'field_results':rows,
         'conclusion':'Because head_pose.proj emits every MHR parameter block, pose, shape, scale and hand outputs can all change. face is explicitly multiplied by zero in MHRHead.forward.'}
    (a.out/'MHR_OUTPUT_CHANGE_AUDIT_V1.json').write_text(json.dumps(out,indent=2),encoding='utf-8')

    source_files=[a.server_trainer,a.sam_repo/'sam_3d_body/models/heads/mhr_head.py',a.sam_repo/'sam_3d_body/models/meta_arch/sam3d_body.py']
    prov={'status':'RUNTIME_PROVENANCE_CAPTURED','host':platform.node(),'python':sys.version,'torch':torch.__version__,'cuda':torch.version.cuda,
      'git_commit_server_sam3d':subprocess.run(['git','-C',str(a.sam_repo),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip(),
      'files':{str(p):sha_file(p) for p in source_files+[a.official,a.mhr,a.e1,a.e10]},
      'note':'Server trainer hash is the preserved runtime copy and differs from the later Git handoff copy; this distinction is explicit.'}
    (a.out/'RUNTIME_IMPLEMENTATION_PROVENANCE_V1.json').write_text(json.dumps(prov,indent=2),encoding='utf-8')
if __name__=='__main__': main()
