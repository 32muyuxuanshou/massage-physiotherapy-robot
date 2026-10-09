"""Consistent multi-distance RGB/Depth probes, independent of training targets."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json
from pathlib import Path
import numpy as np
import torch
from fusion import RGBDBodyAdapter
from fusion_r4 import R4Adapter
from r3_common import load_official,read_cache,combine,cached_forward,metrics,sha
from render_losses import MeshRenderer


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--checkpoint',type=Path);p.add_argument('--r3',action='store_true');a=p.parse_args();torch.set_num_threads(2)
    cache=a.root/'runs/r4_geometry_v1/physical_camera_cache';rows=json.loads((cache/'CACHE_MANIFEST.json').read_text())['records']
    assert all(r['role']!='TEST' for r in rows);official,_=load_official(a.root)
    state=torch.load(a.checkpoint,weights_only=False) if a.checkpoint else None
    model=((RGBDBodyAdapter if a.r3 else R4Adapter)(official,state['mode']) if state else RGBDBodyAdapter(official)).cuda()
    if state:model.fusion.load_state_dict(state['fusion'])
    renderer=MeshRenderer(official.head_pose.faces);records=[]
    with torch.no_grad():
        for r in rows:
            rec=read_cache(str(cache/r['cache_file']));b,f,d,v,rays,gt,target,mask,K=combine([rec])
            o=cached_forward(model,b,f,d,v,rays)
            records.append(dict(identity=r['identity'],role=r['role'],factor=r['physical_camera_factor'],
                camera_gt_xyz_m=gt['pred_cam_t'][0].tolist(),camera_pred_xyz_m=o['pred_cam_t'][0].tolist(),
                metrics=metrics(o,gt,target,mask,K,renderer)[0]))
    per={}
    for identity in sorted({r['identity'] for r in records}):
        rr=[r for r in records if r['identity']==identity];z=np.array([r['camera_gt_xyz_m'][2] for r in rr]);p=np.array([r['camera_pred_xyz_m'][2] for r in rr])
        per[identity]=dict(role=rr[0]['role'],z_response_slope=float(np.polyfit(z,p,1)[0]),
            z_absolute_mae_mm=float(np.abs(z-p).mean()*1000),z_relative_change_mae_mm=float(np.abs((p-p[0])-(z-z[0])).mean()*1000),
            vertex_camera_mm=float(np.mean([r['metrics']['vertex_camera_mm'] for r in rr])),
            depth_valid_mean_z_m=[float(read_cache(str(cache/(identity+f"_distance{i}.pt")))['depth'].masked_select(read_cache(str(cache/(identity+f"_distance{i}.pt")))['valid']).mean()) for i in range(4)])
    report=dict(status='PHYSICAL_DISTANCE_PROBE_COMPLETE_NO_TEST',checkpoint=str(a.checkpoint),checkpoint_sha256=sha(a.checkpoint) if a.checkpoint else None,
        ideal_z_response_slope=1.,per_identity=per,records=records,
        identity_equal_mean={k:float(np.mean([x[k] for x in per.values()])) for k in ['z_response_slope','z_absolute_mae_mm','z_relative_change_mae_mm','vertex_camera_mm']},
        limitations='four already-used TRAIN/VAL identities; clean procedural scenes, out-of-range distance extension; mechanism diagnosis only')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2))
    if hasattr(model,'remove_hooks'):model.remove_hooks()
    else:model._hook.remove()
    print(json.dumps(report['identity_equal_mean']),flush=True)
