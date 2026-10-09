"""R3 shared exact-cache forward and per-sample native geometry metrics."""
import copy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import roma
import torch
from fusion import RGBDBodyAdapter


TRUTH_KEYS = ['pred_vertices','pred_keypoints_3d','pred_joint_coords','pred_cam_t',
              'body_pose','global_rot','shape','scale','hand']


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def load_official(root):
    sys.path.insert(0,str(root/'external/sam-3d-body'))
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    model,cfg=load_sam_3d_body(str(root/'checkpoints/official/sam-3d-body-vith/model.ckpt'),device='cuda',
        mhr_path=str(root/'checkpoints/official/sam-3d-body-vith/assets/mhr_model.pt'))
    model.requires_grad_(False);model.eval()
    return model,SAM3DBodyEstimator(model,cfg,human_detector=None,human_segmentor=None,fov_estimator=None)


@lru_cache(maxsize=1024)
def read_cache(path):
    return torch.load(path,map_location='cpu',weights_only=False)


def combine(records):
    batch={k:torch.cat([r['batch'][k] for r in records],0).cuda() for k in records[0]['batch']}
    feature=torch.cat([r['backbone'] for r in records],0).cuda()
    depth=torch.cat([r['depth'] for r in records],0).cuda()
    valid=torch.cat([r['valid'] for r in records],0).cuda()
    rays=torch.cat([r['rays'] for r in records],0).cuda()
    gt={k:torch.cat([r['truth'][k] for r in records],0).cuda() for k in records[0].get('truth',{})}
    if gt:
        target=torch.cat([r['target_depth'] for r in records],0).cuda()
        mask=torch.cat([r['target_mask'] for r in records],0).cuda()
        K=torch.cat([r['K'] for r in records],0).cuda()
    else:target=mask=K=None
    return batch,feature,depth,valid,rays,gt,target,mask,K


def cached_forward(adapter,batch,feature,depth,valid,rays):
    # Same Module.__call__ and existing feature-fusion hook; only the frozen
    # backbone computation is replaced with its exact saved native-dtype output.
    backbone=adapter.official.backbone
    original=backbone.forward
    backbone.forward=lambda x,**kwargs:feature
    try:return adapter(copy.deepcopy(batch),depth,valid,rays)
    finally:backbone.forward=original


def aggregate(rows):
    ids=sorted({r['identity'] for r in rows})
    per={}
    for identity in ids:
        rr=[r for r in rows if r['identity']==identity]
        per[identity]={k:float(np.mean([r['metrics'][k] for r in rr if r['metrics'][k] is not None]))
                       if any(r['metrics'][k] is not None for r in rr) else None for k in rr[0]['metrics']}
    summary={k:float(np.mean([m[k] for m in per.values() if m[k] is not None]))
             if any(m[k] is not None for m in per.values()) else None for k in rows[0]['metrics']}
    return dict(identity_equal_mean=summary,per_identity=per,records=rows)


def metrics(output,gt,depth,mask,K,renderer):
    v,tv=output['pred_vertices'],gt['pred_vertices'];cam,tc=output['pred_cam_t'],gt['pred_cam_t']
    rd,sil=renderer(v+cam[:,None],K)
    # Physical root rotation convention independently measured on the native asset.
    R=roma.euler_to_rotmat('xyz',output['global_rot']);T=roma.euler_to_rotmat('xyz',gt['global_rot'])
    cosine=((R.transpose(-1,-2)@T).diagonal(dim1=-2,dim2=-1).sum(-1)-1)/2
    angle_indices=[i for i in range(133) if i not in range(124,130)]
    values=dict(vertex_body_mm=(v-tv).norm(dim=-1).mean(-1)*1000,
        vertex_camera_mm=(v+cam[:,None]-tv-tc[:,None]).norm(dim=-1).mean(-1)*1000,
        vertex_translation_removed_mm=((v-v.mean(1,keepdim=True))-(tv-tv.mean(1,keepdim=True))).norm(dim=-1).mean(-1)*1000,
        joint_mm=(output['pred_joint_coords']-gt['pred_joint_coords']).norm(dim=-1).mean(-1)*1000,
        joint_camera_mm=(output['pred_joint_coords']+cam[:,None]-gt['pred_joint_coords']-tc[:,None]).norm(dim=-1).mean(-1)*1000,
        camera_mm=(cam-tc).norm(dim=-1)*1000,
        shape_rmse=(output['shape']-gt['shape']).square().mean(-1).sqrt(),
        scale_rmse=(output['scale']-gt['scale']).square().mean(-1).sqrt(),
        global_rotation_deg=torch.acos(cosine.clamp(-1,1))*180/np.pi,
        body_pose_periodic_mean_deg=torch.atan2(torch.sin(output['body_pose'][:,angle_indices]-gt['body_pose'][:,angle_indices]),
            torch.cos(output['body_pose'][:,angle_indices]-gt['body_pose'][:,angle_indices])).abs().mean(-1)*180/np.pi)
    rows=[]
    for i in range(len(v)):
        common=mask[i].bool()&(rd[i]>0);res=(rd[i][common]-depth[i][common]).abs()*1000
        rows.append(dict(**{k:float(x[i]) for k,x in values.items()},
            depth_common_median_mm=float(res.median()) if len(res) else None,
            depth_common_p95_mm=float(torch.quantile(res,.95)) if len(res) else None,
            depth_hit_rate=float(common.sum()/mask[i].sum()),
            silhouette_iou=float(((sil[i]>.5)&mask[i].bool()).sum()/((sil[i]>.5)|mask[i].bool()).sum())))
    return rows


def output_change(output,reference):
    angles=[i for i in range(133) if i not in range(124,130)]
    return dict(vertex_camera_change_mm=float((output['pred_vertices']+output['pred_cam_t'][:,None]-reference['pred_vertices']-reference['pred_cam_t'][:,None]).norm(dim=-1).mean()*1000),
        camera_change_mm=float((output['pred_cam_t']-reference['pred_cam_t']).norm(dim=-1).mean()*1000),
        camera_change_xyz_mm=((output['pred_cam_t']-reference['pred_cam_t']).mean(0)*1000).tolist(),
        body_pose_change_periodic_deg=float(torch.atan2(torch.sin(output['body_pose'][:,angles]-reference['body_pose'][:,angles]),torch.cos(output['body_pose'][:,angles]-reference['body_pose'][:,angles])).abs().mean()*180/np.pi),
        shape_change_rmse=float((output['shape']-reference['shape']).square().mean().sqrt()),
        scale_change_rmse=float((output['scale']-reference['scale']).square().mean().sqrt()))
