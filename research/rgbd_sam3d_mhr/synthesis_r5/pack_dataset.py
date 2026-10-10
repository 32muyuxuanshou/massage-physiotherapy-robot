"""Package rendered RGB, exact scan-surface Z, noisy depth and camera labels."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
import cv2
import numpy as np
from PIL import Image
from raster import render_z, exact_ray_qa


def build(root, plan, limit=None):
    config, noise = plan['render_config'], plan['depth_config']
    H, W = config['height'], config['width']
    records, qa = [], []
    folder = root/'samples'
    folder.mkdir(exist_ok=True)
    metas = sorted((root/'renders').glob('*.json'))
    if limit:
        metas = metas[:limit]
    last_asset, vertices, faces = None, None, None
    for path in metas:
        row = json.loads(path.read_text())
        sid = row['sample_id']
        if row['asset_id'] != last_asset:
            g = np.load(root/row['geometry_file'])
            vertices, faces = g['vertices_scene_m'], g['faces']
            last_asset = row['asset_id']
        R, t, K = map(np.array, (row['R_world_to_camera'], row['T_world_to_camera'], row['K']))
        camera_vertices = (vertices @ R.T+t).astype(np.float64)
        depth, face_id = render_z(camera_vertices, faces, K, H, W)
        mask = depth > 0
        yy, xx = np.nonzero(mask)
        assert len(xx)>500 and xx.min()>1 and yy.min()>1 and xx.max()<W-2 and yy.max()<H-2
        rendered_mask = np.load(root/'renders'/(sid+'_mask.npy')) > .5
        union = (mask|rendered_mask).sum()
        iou = float((mask&rendered_mask).sum()/union)
        interior = cv2.erode((mask&rendered_mask).astype(np.uint8), np.ones((5,5), np.uint8))>0
        raw_z = np.load(root/'renders'/(sid+'_zpass.npy'))
        ygrid, xgrid = np.indices((H, W))
        ray_length = np.sqrt(((xgrid-K[0,2])/K[0,0])**2+((ygrid-K[1,2])/K[1,1])**2+1)
        # Blender 4.5 Cycles Depth is axial camera Z, verified against ray/triangle intersections.
        difference = np.abs(raw_z[interior]-depth[interior])*1000
        ray = exact_ray_qa(camera_vertices, faces, K, depth, face_id)
        ray.update(sample_id=sid, rgb_object_mask_iou=iou,
                   independent_cycles_z_to_camera_z_p95_mm=float(np.quantile(difference,.95)),
                   independent_cycles_z_to_camera_z_median_mm=float(np.median(difference)),
                   cycles_ray_distance_candidate_p95_mm=float(np.quantile(np.abs(raw_z[interior]/ray_length[interior]-depth[interior])*1000,.95)))
        qa.append(ray)
        assert ray['max_z_error_mm'] < .02 and ray['min_barycentric'] > -1e-5, ray
        assert iou > .985, ray
        assert ray['independent_cycles_z_to_camera_z_p95_mm'] < .5, ray
        # Floor is an explicit plane in the render scene; environment dome has no finite depth.
        rays = np.stack(((xgrid-K[0,2])/K[0,0], (ygrid-K[1,2])/K[1,1], np.ones((H,W))), -1)
        world_directions = rays @ R
        C = -R.T @ t
        dz = world_directions[...,2]
        with np.errstate(divide='ignore', invalid='ignore'):
            floor_z = (-.015-C[2])/dz
        floor_valid = (floor_z>.02)&(floor_z<100)
        scene_depth = np.where(floor_valid, floor_z, 0).astype(np.float32)
        visible = mask & ((~floor_valid)|(depth<=scene_depth))
        assert np.array_equal(visible, mask), 'Unexpected floor occlusion'
        scene_depth[mask] = depth[mask]
        floor_check = (~mask) & floor_valid & (scene_depth < 20)
        ray['scene_floor_under_20m_depth_p95_mm'] = float(np.quantile(
            np.abs(scene_depth[floor_check]-raw_z[floor_check])*1000,.95))
        # Independent deterministic sensor noise; clean target remains unchanged.
        seed = int(hashlib.sha256(('r5-depth:'+sid).encode()).hexdigest()[:8],16)
        rng = np.random.default_rng(seed)
        sigma = noise['base_sigma_m']+noise['range_sigma_per_m']*depth
        noisy = np.round((depth+rng.normal(0,sigma))/noise['quantization_m'])*noise['quantization_m']
        edge = mask & ~(cv2.erode(mask.astype(np.uint8),np.ones((3,3),np.uint8))>0)
        holes = rng.random((H,W))<noise['iid_dropout_probability']
        holes |= edge & (rng.random((H,W))<noise['edge_dropout_probability'])
        noisy[~mask|holes] = 0
        rgba = np.array(Image.open(root/'renders'/(sid+'.png')).convert('RGBA'))
        # The rendered floor fills most pixels; only the infinite transparent sky gets a neutral studio backdrop.
        backdrop = np.array([.12,.15,.19])*255
        alpha = rgba[...,3:4]/255
        rgb = np.clip(rgba[...,:3]*alpha+backdrop*(1-alpha),0,255).astype(np.uint8)
        sample = folder/(sid+'.npz')
        np.savez_compressed(sample, rgb=rgb, depth_m=noisy.astype(np.float32), depth_clean_m=depth,
                            depth_scene_clean_m=scene_depth, mask=mask, K=K.astype(np.float32),
                            bbox=np.array([xx.min(),yy.min(),xx.max()+1,yy.max()+1],np.float32),
                            R_world_to_camera=R,T_world_to_camera=t,
                            source_asset_id=np.array(row['asset_id']))
        row.update(file='samples/'+sample.name, sha256=hashlib.sha256(sample.read_bytes()).hexdigest(),
                   bytes=sample.stat().st_size, surface_geometry_file=row['geometry_file'],
                   labels='Reconstructed clothed scan in virtual scene; no MHR body parameter GT',
                   depth_seed=seed, depth_valid_fraction=float((noisy[mask]>0).mean()))
        records.append(row)
        if len(records)%24==0:
            print('PACKED',len(records),len(metas),flush=True)
    report=dict(status='GEOMETRY_QA_PASS',records=qa,samples=len(records),
                max_ray_error_mm=max(x['max_z_error_mm'] for x in qa),
                min_rgb_depth_mask_iou=min(x['rgb_object_mask_iou'] for x in qa),
                max_independent_cycles_depth_p95_mm=max(x['independent_cycles_z_to_camera_z_p95_mm'] for x in qa),
                max_scene_floor_under_20m_depth_p95_mm=max(x['scene_floor_under_20m_depth_p95_mm'] for x in qa),
                depth_definition='camera +Z metres, integer pixel centres; Blender 4.5 Cycles Depth is axial Z (independently verified)',
                scope='Simulator RGB/depth/camera consistency, not accuracy of source human reconstruction')
    manifest=dict(version=plan['version'],roles=dict(Counter(x['role'] for x in records)),
                  source_revision=plan['source_revision'],identity_split=plan['identities'],
                  source_plan_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest(),
                  samples=records, TEST_read=False, native_mhr_supervision_available=False)
    (root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    (root/'GEOMETRY_QA.json').write_text(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--limit',type=int)
    a=p.parse_args();report=build(a.root,json.loads(a.plan.read_text()),a.limit)
    print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)
