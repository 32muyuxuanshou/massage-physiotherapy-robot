"""Tiny metric Camera-only head after the frozen Official body decode.

Root position = measured median XYZ - body-anchor median XYZ + learned offset.
The offset uses centred geometry only. A uniform XYZ translation of observed
points therefore translates the predicted root by exactly the same vector.
No pose/shape/scale/global rotation or per-vertex displacement is predicted.
"""
import numpy as np


def features(points, body_anchors):
    observed = np.quantile(points, [.25, .5, .75], axis=0)
    body = np.quantile(body_anchors, [.25, .5, .75], axis=0)
    x = np.concatenate([(observed[[0,2]]-observed[1]).reshape(-1),
                        (body[[0,2]]-body[1]).reshape(-1)])
    return observed[1]-body[1], x


def fit(x, target_offset, regularization, sample_weights):
    weight = sample_weights/sample_weights.sum()
    mean = (x*weight[:,None]).sum(0)
    std = np.sqrt(((x-mean)**2*weight[:,None]).sum(0)).clip(1e-6)
    design = np.column_stack(((x-mean)/std, np.ones(len(x))))
    penalty = np.eye(design.shape[1])*regularization
    penalty[-1,-1] = 0  # intercept is not penalized
    # Normalized identity-equal weights, scaled to n samples for ridge strength.
    w = weight*len(x)
    coef = np.linalg.solve(design.T@(design*w[:,None])+penalty,
                           design.T@(target_offset*w[:,None]))
    return dict(mean=mean, std=std, coefficients=coef)


def predict(points, body_anchors, original_camera, state):
    if len(points)==0:
        return np.asarray(original_camera,np.float64).reshape(3).copy()
    base, x = features(points, body_anchors)
    offset = np.r_[(x-state['mean'])/state['std'],1.]@state['coefficients']
    return base+offset


def camera_only_output(official, output, batch, points_camera_A, state, face_index, barycentric, faces):
    """Inference adapter for a single native MHR output (Torch tensors, no hooks).

    Invoke only AFTER Official completes its body decode. The original native
    output remains untouched. All body/hand fields and MHR vertices are retained;
    the Camera and projected 2D fields are recomputed together in the same K.
    Training this head never backpropagates through Official or its decoder.
    """
    import torch
    result = dict(output)
    if len(points_camera_A)==0:
        return result
    body = output['pred_vertices'][0].detach().cpu().double().numpy()
    anchors = (body[np.asarray(faces)[face_index]]*barycentric[:,:,None]).sum(1)
    cam = predict(points_camera_A, anchors, output['pred_cam_t'][0].detach().cpu().numpy(), state)
    camera = torch.as_tensor(cam,device=output['pred_cam_t'].device,dtype=output['pred_cam_t'].dtype)[None]
    index = official.body_batch_idx
    flat = official._flatten_person
    K = flat(batch['cam_int'].unsqueeze(1))[index].to(camera)
    center = flat(batch['bbox_center'])[index].to(camera)
    box = flat(batch['bbox_scale'])[index,0].to(camera)
    size = flat(batch['ori_img_size'])[index].to(camera)
    origin = K[:,:2,2] if official.cfg.MODEL.DECODER.get('USE_INTRIN_CENTER',False) else size/2
    offset = (center-origin)*camera[:,2:]/K[:,0,0,None]
    scale = -2*K[:,0,0]/(camera[:,2]*box*official.head_camera.default_scale_factor)
    result['pred_cam'] = torch.stack((scale,camera[:,0]-offset[:,0],-camera[:,1]+offset[:,1]),1)
    result = official.camera_project(result,batch)
    result['pred_keypoints_2d_cropped'] = official._full_to_crop(batch,result['pred_keypoints_2d'],index)
    result['vertices_camera_A'] = output['pred_vertices']+result['pred_cam_t'][:,None]
    assert torch.max(torch.abs(result['pred_cam_t']-camera))<2e-6
    return result
