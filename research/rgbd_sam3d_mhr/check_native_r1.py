"""Actual GPU SAM->Fusion->native MHR loss/backward/step verification.

This produces ONE simple-material native MHR geometry fixture. It is an R1
execution check, not an R2 training dataset or evidence of real-world accuracy.
Run only after R0 assets and GPU environment have been verified.
"""
import os
os.environ.setdefault('MOMENTUM_ENABLED', '0')
os.environ.setdefault('PYOPENGL_PLATFORM', 'egl')
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import torch
from fusion import RGBDBodyAdapter
from geometry import crop_registered_depth


def parameter_hashes(model):
    # Actual values, not requires_grad flags or claimed frozen module names.
    return {name: hashlib.sha256(p.detach().cpu().contiguous().flatten().view(torch.uint8)
                                 .numpy().tobytes()).hexdigest()
            for name, p in model.named_parameters()}


def native_fixture(head, out):
    import pyrender
    import trimesh
    def zeros(n):
        return torch.zeros(1, n, device=head.scale_mean.device)
    truth = dict(global_rot=zeros(3), body_pose=zeros(133), shape=zeros(45),
                 scale=zeros(28), hand=zeros(108))
    with torch.no_grad():
        v, kp, joints = head.mhr_forward(global_trans=zeros(3),
            global_rot=truth['global_rot'], body_pose_params=truth['body_pose'],
            hand_pose_params=truth['hand'], scale_params=truth['scale'],
            shape_params=truth['shape'], expr_params=zeros(72),
            return_keypoints=True, return_joint_coords=True)
        # Match official MHRHead.forward conversion, raw asset cm->m occurs
        # INSIDE mhr_forward. Do not apply the conversion a second time.
        v, kp, joints = (x * x.new_tensor([1, -1, -1]) for x in (v, kp, joints))
        kp = kp[:, :70]
        cam = v.new_tensor([[0, 0, 3.5]])
        cam[:, :2] = -v.mean(1)[:, :2]
    K = np.array([[800., 0, 320.], [0, 800., 240.], [0, 0, 1.]], np.float32)
    faces = head.faces.detach().cpu().numpy()
    vc = (v + cam[:, None]).cpu().numpy()[0]
    scene = pyrender.Scene(bg_color=[.12, .12, .12, 1], ambient_light=[.5]*3)
    material = pyrender.MetallicRoughnessMaterial(baseColorFactor=[.65,.55,.45,1],
                                                  metallicFactor=0, roughnessFactor=.9)
    scene.add(pyrender.Mesh.from_trimesh(trimesh.Trimesh(vc, faces, process=False),
                                       material=material, smooth=True))
    camera_pose = np.diag([1., -1., -1., 1.])  # OpenCV->OpenGL, no extra fit.
    scene.add(pyrender.IntrinsicsCamera(800, 800, 320, 240, znear=.05, zfar=10),
              pose=camera_pose)
    scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=2), pose=camera_pose)
    renderer = pyrender.OffscreenRenderer(640, 480)
    rgb, depth = renderer.render(scene)
    renderer.delete()
    mask = depth > 0
    yy, xx = np.nonzero(mask)
    assert len(xx) > 1000, 'NATIVE_FIXTURE_NOT_VISIBLE'
    bbox = np.array([xx.min(), yy.min(), xx.max()+1, yy.max()+1], np.float32)
    truth.update(pred_vertices=v, pred_keypoints_3d=kp, pred_joint_coords=joints,
                 pred_cam_t=cam)
    np.savez_compressed(out/'native_fixture.npz', rgb=rgb, depth_m=depth, mask=mask,
        K=K, bbox=bbox, faces=faces,
        **{k:x.detach().cpu().numpy() for k,x in truth.items()})
    return rgb, depth, mask, K, bbox, truth


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sam-source', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--mhr', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--mode', choices=['residual','cross_attention'], default='cross_attention')
    args = p.parse_args()
    assert torch.cuda.is_available(), 'R1_REQUIRES_GPU_MODE'
    torch.manual_seed(42); np.random.seed(42)
    args.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.sam_source))
    from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    start = time.monotonic()
    official, cfg = load_sam_3d_body(str(args.checkpoint), device='cuda', mhr_path=str(args.mhr))
    estimator = SAM3DBodyEstimator(official, cfg, human_detector=None,
                                   human_segmentor=None, fov_estimator=None)
    rgb, depth, mask, K, bbox, truth = native_fixture(official.head_pose, args.out)
    def batch():
        prepared = prepare_batch(rgb, estimator.transform, bbox[None],
            masks=mask.astype(np.uint8)[None], cam_int=torch.from_numpy(K[None]))
        return recursive_to(prepared, 'cuda')
    with torch.no_grad():
        baseline_batch = batch(); official._initialize_batch(baseline_batch)
        baseline = official.forward_step(baseline_batch, decoder_type='body')['mhr']
    model = RGBDBodyAdapter(official, mode=args.mode).cuda()
    before = parameter_hashes(official)
    optimizer = torch.optim.AdamW(model.fusion.parameters(), lr=1e-3, weight_decay=0)
    prepared = batch()
    cropped, valid, rays = crop_registered_depth(torch.from_numpy(depth[None,None]).cuda(), prepared)
    with torch.no_grad():
        initial = model(batch(), cropped, valid, rays)
    keys = ['pred_vertices','pred_keypoints_3d','pred_cam_t','global_rot','body_pose','shape','scale']
    initial_diff = {k: float((initial[k]-baseline[k]).abs().max()) for k in keys}
    assert max(initial_diff.values()) == 0, 'INITIAL_OFFICIAL_EQUIVALENCE_FAILED'
    steps = []
    for step in range(3):
        optimizer.zero_grad()
        output = model(batch(), cropped, valid, rays)
        components = {k: (output[k]-truth[k]).square().mean() for k in keys}
        loss = sum(components.values())
        loss.backward()
        gradients = {k: None if v.grad is None else float(v.grad.norm())
                     for k,v in model.fusion.named_parameters()}
        assert torch.isfinite(loss), 'NONFINITE_R1_LOSS'
        optimizer.step()
        steps.append(dict(step=step, loss=float(loss.detach()),
                          losses={k:float(x.detach()) for k,x in components.items()}, gradients=gradients))
    assert steps[-1]['gradients']['depth_encoder.0.weight'] > 0, 'DEPTH_GRADIENT_ZERO'
    after = parameter_hashes(official)
    assert before == after, 'FROZEN_OFFICIAL_PARAMETERS_CHANGED'
    with torch.no_grad():
        trained = model(batch(), cropped, valid, rays)
        changed = model(batch(), cropped+.2, valid, rays)
        missing = model(batch(), cropped, torch.zeros_like(valid), rays)
    depth_change = {k: float((trained[k]-changed[k]).abs().max()) for k in keys}
    missing_diff = {k: float((missing[k]-baseline[k]).abs().max()) for k in keys}
    assert max(missing_diff.values()) == 0, 'MISSING_DEPTH_OFFICIAL_EQUIVALENCE_FAILED'
    assert max(depth_change.values()) > 0, 'DEPTH_DOES_NOT_REACH_MHR_OUTPUT'
    np.savez_compressed(args.out/'prediction.npz',
        **{k:v.detach().cpu().numpy() for k,v in trained.items() if torch.is_tensor(v)})
    torch.save({'fusion':model.fusion.state_dict(), 'mode':args.mode}, args.out/'fusion_r1.pt')
    report = dict(status='PASS', scope='NATIVE_SAM_MHR_R1_ONLY_NOT_R2_OR_REAL_ACCURACY',
        fixture='Simple native MHR zero body pose, zero shape/scale, physical camera Z render',
        depth_m_range=[float(depth[mask].min()),float(depth.max())],
        rgb_feature_contract=[1280,32,24], initial_max_abs_diff=initial_diff,
        missing_depth_max_abs_diff=missing_diff, changed_depth_output_max_abs_diff=depth_change,
        train_steps=steps, frozen_parameter_count=len(before), frozen_values_unchanged=True,
        frozen_parameter_hashes_before=before, frozen_parameter_hashes_after=after,
        trainable_parameters=[k for k,v in model.named_parameters() if v.requires_grad],
        cuda=torch.version.cuda, torch=torch.__version__, gpu=torch.cuda.get_device_name(),
        peak_memory_bytes=torch.cuda.max_memory_allocated(), seconds=time.monotonic()-start,
        limitations='Single fixture; no rendered-depth/silhouette training loss yet. No identity generalization claimed.')
    (args.out/'R1_NATIVE_CHECK.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'status':report['status'],'scope':report['scope'],'seconds':report['seconds']}))


if __name__ == '__main__':
    main()
