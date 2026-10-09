"""R3: fixed identity x fixed posed mesh x physical camera views."""
import os
os.environ.setdefault('MOMENTUM_ENABLED', '0')
os.environ.setdefault('PYOPENGL_PLATFORM', 'egl')
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import cv2
import numpy as np
import roma
import torch
from render_losses import MeshRenderer


def generate(head, output, config, limit=None):
    import pyrender
    import trimesh
    from sam_3d_body.models.modules.mhr_utils import mhr_param_hand_mask
    metric_root=Path(__file__).parents[2]/'docs/handoffs/real-scene-2026-09-09/public-rgbd-surface-finetuning-pilot-v1/code'
    sys.path.insert(0,str(metric_root))
    from surface_metrics import point_to_triangle_distances
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    rng = np.random.default_rng(config['dataset_seed'])
    people = []
    for i in range(config['identities']):
        role = 'TRAIN' if i < config['train_identities'] else 'VAL' if i < config['train_identities'] + config['val_identities'] else 'TEST'
        people.append(dict(identity=f'mhr3_{i:04d}', role=role,
            shape=np.clip(rng.normal(0, config['shape_std'], 45), -2.5, 2.5).tolist(),
            scale=np.clip(rng.normal(0, config['scale_std'], 28), -.8, .8).tolist()))
    (output / 'IDENTITY_SPLIT.json').write_text(json.dumps(dict(seed=config['dataset_seed'], people=people), indent=2))
    faces = head.faces.cpu().numpy(); np.save(output / 'faces.npy', faces)
    gpu_renderer = MeshRenderer(head.faces)
    rgb_renderer = pyrender.OffscreenRenderer(640, 480)
    S = np.diag([1., -1., -1.]).astype(np.float32)
    flip = head.scale_mean.new_tensor([1., -1., -1.])
    tensor = lambda x: torch.as_tensor(x, device=head.scale_mean.device, dtype=torch.float32)[None]
    def body(global_rot, pose, shape, scale):
        with torch.no_grad():
            result = head.mhr_forward(global_trans=tensor(np.zeros(3)), global_rot=global_rot,
                body_pose_params=pose, hand_pose_params=tensor(np.zeros(108)), scale_params=scale,
                shape_params=shape, expr_params=tensor(np.zeros(72)), return_keypoints=True, return_joint_coords=True)
        return tuple(x * flip for x in result)
    manifest = dict(seed=config['dataset_seed'], config=config, people=people, samples=[],
        scope='NATIVE_MHR_FIXED_POSE_MULTIVIEW_PROCEDURAL_TEXTURE_NOISY_DEPTH',
        coordinate_contract='X_camera = R_world_to_camera @ X_fixed_pose + T_world_to_camera; m; original K')
    qa = []; camera_pose = np.diag([1., -1., -1., 1.])
    for person in people[:limit] if limit else people:
        shape, scale = tensor(person['shape']), tensor(person['scale'])
        posed = []
        for pose_id, std in enumerate(config['pose_stds']):
            pose_array = np.clip(rng.normal(0, std, 133), -.65, .65)
            pose_array[mhr_param_hand_mask.cpu().numpy()] = 0
            # These are translations, not angles; do not randomise in radians.
            pose_array[124:] = 0
            pose = tensor(pose_array)
            base_v, base_k, base_j = body(tensor(np.zeros(3)), pose, shape, scale)
            base = base_v.cpu().numpy()[0]
            posed.append((pose_array, pose, base))
        union = np.concatenate([p[2] for p in posed])
        center = (union.min(0)+union.max(0))/2
        camera_plans = []
        for camera_id in range(config['cameras_per_pose']):
            yaw = camera_id*np.pi/2 + rng.uniform(-.20,.20)
            pitch, roll = rng.uniform(-.40,.40), rng.uniform(-.12,.12)
            Rcv = roma.euler_to_rotmat('ZYX',tensor([roll,yaw,pitch]))[0].cpu().numpy()
            focal = float(rng.uniform(*config['focal_range_px'])); rotated = union @ Rcv.T; span = np.ptp(rotated,axis=0)
            distance = max(focal*span[1]/(480*.70),focal*span[0]/(640*.70))+np.abs(rotated[:,2]).max()+rng.uniform(.2,.7)
            T = -Rcv @ center+np.array([rng.uniform(-.08,.08),rng.uniform(-.05,.05),distance])
            camera_plans.append((Rcv,focal,T))
        colour = rng.uniform(.25,.85,3);phase = rng.uniform(0,2*np.pi)
        texture_base = posed[0][2]
        pattern = .10*np.sin(texture_base[:,1]*rng.uniform(8,22)+texture_base[:,0]*rng.uniform(5,16)+phase)
        colours = np.c_[np.clip(colour[None]+pattern[:,None],0,1),np.ones(len(texture_base))]
        for pose_id, (pose_array, pose, base) in enumerate(posed):
            base_sha = hashlib.sha256(base.tobytes()).hexdigest()
            pose_folder = output / 'fixed_poses'; pose_folder.mkdir(exist_ok=True)
            np.savez_compressed(pose_folder / f"{person['identity']}_p{pose_id}.npz", vertices_world=base,
                                body_pose=pose_array, shape=person['shape'], scale=person['scale'])
            for camera_id in range(config['cameras_per_pose']):
                Rcv, focal, T = camera_plans[camera_id]
                Rnative = S @ Rcv @ S
                # Native MHR consumes xyz Euler angles and rotates about its
                # skeleton root, not the origin of the returned vertex array.
                rotation = roma.rotmat_to_euler('xyz', tensor(Rnative))
                v, k, j = body(rotation, pose, shape, scale)
                verts = v.cpu().numpy()[0]
                root_pivot_shift = verts.mean(0,dtype=np.float64) - base.mean(0,dtype=np.float64) @ Rcv.T
                rigid_error = float(np.max(np.abs(verts - base @ Rcv.T - root_pivot_shift)))
                assert rigid_error < 1e-5, f'FIXED_POSE_CAMERA_ROTATION_MISMATCH {rigid_error}'
                K = np.array([[focal,0,320.], [0,focal,240.], [0,0,1]], np.float32)
                cam = tensor(T-root_pivot_shift)
                mesh = trimesh.Trimesh(verts+cam.cpu().numpy()[0], faces, vertex_colors=(colours*255).astype(np.uint8), process=False)
                scene = pyrender.Scene(bg_color=[*rng.uniform(.04,.30,3),1], ambient_light=[.4]*3)
                scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=True))
                scene.add(pyrender.IntrinsicsCamera(focal, focal, 320.5, 240.5, znear=.05, zfar=20), pose=camera_pose)
                scene.add(pyrender.DirectionalLight(color=rng.uniform(.8,1.2,3), intensity=float(rng.uniform(1,3))), pose=camera_pose)
                rgb, gl_depth = rgb_renderer.render(scene)
                with torch.no_grad():
                    depth, _ = gpu_renderer(v+cam[:,None], tensor(K))
                clean = depth[0].cpu().numpy(); mask = clean > 0
                yy, xx = np.nonzero(mask)
                assert len(xx)>1000 and xx.min()>2 and yy.min()>2 and xx.max()<638 and yy.max()<478, 'CAMERA_CLIPPED'
                if len(qa) < 24:
                    interior = cv2.erode(mask.astype(np.uint8), np.ones((5,5), np.uint8)).astype(bool) & (gl_depth>0)
                    diff = np.abs(gl_depth[interior]-clean[interior])*1000
                    p95 = float(np.quantile(diff,.95))
                    # OpenGL/MSAA resolves subpixel depth differently. It is a
                    # reported diagnostic, not a physical Z ground-truth oracle.
                    vi,ui=np.nonzero(interior)
                    indices=np.linspace(0,len(ui)-1,64).astype(int)
                    u0,v0=ui[indices],vi[indices];z0=clean[v0,u0]
                    points=np.c_[(u0-K[0,2])*z0/focal,(v0-K[1,2])*z0/focal,z0]
                    exact=point_to_triangle_distances(points,verts+cam.cpu().numpy()[0],faces)*1000
                    print('RAY_QA',person['identity'],pose_id,camera_id,'median_mm',float(np.median(exact)),'max_mm',float(exact.max()),flush=True)
                    if len(qa)==0:np.savez_compressed(output/'QA_RAY_PROBE.npz',points=points,vertices=verts+cam.cpu().numpy()[0],faces=faces,K=K,depth=clean,pixels=np.c_[u0,v0])
                    assert float(np.median(exact))<.01 and float(np.quantile(exact,.95))<.1,'INDEPENDENT_METRIC_RAY_SURFACE_QA_FAILED'
                    qa.append(dict(identity=person['identity'],pose_id=pose_id,camera_id=camera_id,
                        rigid_rotation_max_abs_m=rigid_error,independent_depth_median_mm=float(np.median(diff)),
                        independent_depth_p95_mm=p95,independent_exact_ray_surface_max_mm=float(exact.max()),
                        independent_exact_ray_surface_p95_mm=float(np.quantile(exact,.95)),
                        depth_valid_range_m=[float(clean[mask].min()),float(clean[mask].max())]))
                sigma = float(rng.uniform(.002,.006)); holes = rng.random(clean.shape)<rng.uniform(.01,.03)
                noisy = np.round((clean+rng.normal(0,sigma,clean.shape))*1000)/1000
                noisy[~mask | holes] = 0; noisy = noisy.astype(np.float32)
                name = f"{person['identity']}_p{pose_id}_c{camera_id}.npz"
                np.savez_compressed(output/name, rgb=rgb, depth_m=noisy, depth_clean_m=clean, mask=mask, K=K,
                    bbox=np.array([xx.min(), yy.min(), xx.max()+1, yy.max()+1], np.float32),
                    global_rot=rotation.cpu().numpy(),body_pose=pose.cpu().numpy(),shape=shape.cpu().numpy(),
                    scale=scale.cpu().numpy(),hand=np.zeros((1,108),np.float32),pred_vertices=v.cpu().numpy(),
                    pred_keypoints_3d=k[:,:70].cpu().numpy(),pred_joint_coords=j.cpu().numpy(),pred_cam_t=cam.cpu().numpy(),
                    R_world_to_camera=Rcv,T_world_to_camera=T,root_pivot_shift_m=root_pivot_shift,fixed_pose_sha256=np.array(base_sha))
                manifest['samples'].append(dict(file=name,identity=person['identity'],role=person['role'],pose_id=pose_id,
                    camera_id=camera_id,back_view=bool(camera_id==2),fixed_pose_sha256=base_sha,depth_noise_sigma_m=sigma,
                    sha256=hashlib.sha256((output/name).read_bytes()).hexdigest()))
        (output/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
        print('GENERATED',person['identity'],person['role'],len(manifest['samples']),flush=True)
    rgb_renderer.delete()
    report=dict(status='GEOMETRY_QA_PASS',independent_renderer='interior physical K/Z unprojection -> frozen CPU exact triangle surface median <0.01 mm, P95 <0.1 mm; max and pyrender MSAA difference separately reported',
                fixed_pose_rigid_multiview=True,records=qa,samples=len(manifest['samples']),seconds=time.monotonic()-start,
                depth_input='noisy metric camera Z with quantisation/holes',depth_target='clean metric camera Z',
                limitations=config['limitations'])
    (output/'GEOMETRY_QA.json').write_text(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--qa-identities',type=int)
    a=p.parse_args();sys.path.insert(0,str(a.root/'external/sam-3d-body'))
    from sam_3d_body import load_sam_3d_body
    official,_=load_sam_3d_body(str(a.root/'checkpoints/official/sam-3d-body-vith/model.ckpt'), device='cuda',
        mhr_path=str(a.root/'checkpoints/official/sam-3d-body-vith/assets/mhr_model.pt'))
    print(json.dumps(generate(official.head_pose,a.out,json.loads(a.config.read_text()),a.qa_identities)),flush=True)
