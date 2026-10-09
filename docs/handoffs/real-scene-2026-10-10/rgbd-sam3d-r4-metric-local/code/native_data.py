"""Simple-material native MHR geometry pilot, not photorealistic patient data."""
import os
os.environ.setdefault('MOMENTUM_ENABLED', '0')
os.environ.setdefault('PYOPENGL_PLATFORM', 'egl')
import json
from pathlib import Path
import hashlib
import numpy as np
import torch


def generate(head, out, seed=20261009, identities=32, views=8):
    import pyrender
    import trimesh
    from render_losses import MeshRenderer
    from sam_3d_body.models.modules.mhr_utils import mhr_param_hand_mask
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(seed)
    people = [dict(identity=f'native_{i:03d}', role='TRAIN' if i<24 else 'VAL' if i<28 else 'TEST',
                   shape=rng.normal(0,.6,45).tolist(), scale=rng.normal(0,.2,28).tolist())
              for i in range(identities)]
    assert identities == 32  # Fixed first pilot, not an implicit split formula.
    manifest = dict(seed=seed, people=people, views_per_identity=views,
        scope='SIMPLE_MATERIAL_SMALL_POSE_NATIVE_MHR_GEOMETRY_PILOT', samples=[],
        limitations='No clothes, bed, occlusion or clinical acupoint labels. Not a prone-domain dataset.')
    # Identity roles and continuous shape/scale fixed before rendering or inference.
    (out/'IDENTITY_SPLIT.json').write_text(json.dumps(manifest,indent=2))
    renderer = pyrender.OffscreenRenderer(640,480)
    faces = head.faces.detach().cpu().numpy()
    geometry_renderer=MeshRenderer(head.faces)
    np.save(out/'faces.npy',faces)
    camera_pose = np.diag([1.,-1.,-1.,1.])
    def tensor(x):
        return torch.as_tensor(x,device=head.scale_mean.device,dtype=torch.float32)[None]
    for person in people:
        for view in range(views):
            body = tensor(rng.normal(0,.08,133)); body[:,mhr_param_hand_mask]=0; body[:,-3:]=0
            rotation = tensor([rng.normal(0,.12), (0 if view%2==0 else np.pi)+rng.normal(0,.25), rng.normal(0,.12)])
            truth = dict(global_rot=rotation, body_pose=body, shape=tensor(person['shape']),
                         scale=tensor(person['scale']),hand=tensor(np.zeros(108)))
            with torch.no_grad():
                v,kp,joints = head.mhr_forward(global_trans=tensor(np.zeros(3)),
                    global_rot=rotation, body_pose_params=body, hand_pose_params=truth['hand'],
                    scale_params=truth['scale'], shape_params=truth['shape'],expr_params=tensor(np.zeros(72)),
                    return_keypoints=True,return_joint_coords=True)
                v,kp,joints = (x*x.new_tensor([1,-1,-1]) for x in (v,kp,joints))
            verts = v.cpu().numpy()[0]
            focal = float(rng.uniform(650,900))
            K=np.array([[focal,0,320.],[0,focal,240.],[0,0,1]],np.float32)
            center=(verts.max(0)+verts.min(0))/2
            span=np.ptp(verts,axis=0)
            z=max(focal*span[1]/(480*.75),focal*span[0]/(640*.75))+abs(verts[:,2]).max()+.25
            cam=tensor([-center[0]+rng.uniform(-.03,.03),-center[1]+rng.uniform(-.03,.03),z])
            scene=pyrender.Scene(bg_color=[*rng.uniform(.05,.25,3),1],ambient_light=[.5]*3)
            material=pyrender.MetallicRoughnessMaterial(baseColorFactor=[*rng.uniform(.25,.85,3),1],
                                                       metallicFactor=0,roughnessFactor=.9)
            scene.add(pyrender.Mesh.from_trimesh(trimesh.Trimesh(verts+cam.cpu().numpy()[0],faces,process=False),
                                               material=material,smooth=True))
            scene.add(pyrender.IntrinsicsCamera(focal,focal,320.5,240.5,znear=.05,zfar=20),pose=camera_pose)
            scene.add(pyrender.DirectionalLight(color=np.ones(3),intensity=float(rng.uniform(1,3))),pose=camera_pose)
            rgb,_=renderer.render(scene)
            with torch.no_grad():
                depth,_=geometry_renderer(v+cam[:,None],torch.from_numpy(K[None]).to(v))
            depth=depth.cpu().numpy()[0];mask=depth>0;yy,xx=np.nonzero(mask)
            assert len(xx)>1000 and xx.min()>2 and yy.min()>2 and xx.max()<638 and yy.max()<478, 'CAMERA_FRAME_CLIPPED'
            bbox=np.array([xx.min(),yy.min(),xx.max()+1,yy.max()+1],np.float32)
            truth.update(pred_vertices=v,pred_keypoints_3d=kp[:,:70],pred_joint_coords=joints,pred_cam_t=cam)
            name=f"{person['identity']}_{view:02d}.npz"
            np.savez_compressed(out/name,rgb=rgb,depth_m=depth,mask=mask,K=K,bbox=bbox,
                **{k:x.cpu().numpy() for k,x in truth.items()})
            digest=hashlib.sha256((out/name).read_bytes()).hexdigest()
            manifest['samples'].append(dict(file=name,identity=person['identity'],role=person['role'],sha256=digest,
                                           view=view,back_view=bool(view%2),visible_pixels=len(xx)))
        print('GENERATED',person['identity'],person['role'],flush=True)
    renderer.delete()
    (out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    return manifest
