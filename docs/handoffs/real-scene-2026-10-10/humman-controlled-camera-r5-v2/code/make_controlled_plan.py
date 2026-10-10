"""Freeze 64 explicit camera configurations per unchanged photographed scan."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def build(old):
    plan = dict(old)
    plan['version'] = 'R5_HUMMAN_CONTROLLED_CAMERA_V2'
    plan['dataset_seed'] = 20261011
    cameras = []

    def add(group, distance, yaw=180, elevation=10, roll=0, focal=400, x=0, y=0):
        cameras.append(dict(camera_id=len(cameras), group=group, distance_m=distance,
                            yaw_deg=yaw, elevation_deg=elevation, roll_deg=roll,
                            focal_px=focal, offset_x_fraction=x, offset_y_fraction=y))

    for d in [.8, 1.2, 1.8, 2.5, 3.2, 4.0]:
        add('distance', d, yaw=30)
    for yaw in [0, 60, 120, 180, 240, 300]:
        for d in [1.2, 1.8, 2.5, 3.2]:
            add('multiview_distance', d, yaw=yaw)
    for elevation in [0, 25, 45, 65, 85]:
        for d in [1.8, 3.2]:
            add('elevation', d, elevation=elevation)
    for roll in [-90, -45, -15, 15, 45, 90]:
        for d in [1.8, 3.2]:
            add('roll', d, roll=roll)
    for x, y in [(-.25, 0), (.25, 0), (0, -.2), (0, .2)]:
        add('offcentre', 2.5, x=x, y=y)
    for focal in [300, 500, 650, 850]:
        add('focal', 2.5, focal=focal)
    for d, focal in [(1.2, 200), (1.8, 300), (3, 500), (4, 2000/3)]:
        add('matched_angular_size', d, focal=focal)
    assert len(cameras) == 64
    plan['cameras'] = cameras
    plan['lighting'] = [old['lighting'][0]]
    plan['render_config'] = dict(old['render_config'], samples=16, cpu_threads=4,
                                 view_transform='Filmic', fixed_world_lighting=True,
                                 allow_image_truncation=True, blender_depth_definition='axial_z')
    plan['camera_contract'] = {
        'distance': 'Z of scan bounding-box midpoint in camera coordinates; NOT MHR root Z',
        'focal': 'fixed 400 px for main factorial groups; separate focal/size diagnostic groups',
        'offcentre': 'reference pixel shift as fraction of image width/height; orientation and Z unchanged',
        'roll': 'physical camera rotation about its optical axis, RGB/depth/K/extrinsics generated together',
        'truncation': 'intentional near/zoomed/offcentre views retained and individually flagged',
        'body': 'unchanged source vertices/pose/texture, only rigid floor placement',
        'lighting': 'same lights in world coordinates for every camera, not attached to camera',
    }
    plan['expected_samples'] = len(plan['assets'])*len(cameras)*len(plan['lighting'])
    plan['camera_group_counts_per_asset'] = dict(Counter(c['group'] for c in cameras))
    plan['parent_plan_sha256'] = hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
    return plan


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    plan = build(json.loads(a.parent.read_text(encoding='utf8')))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(plan, indent=2), encoding='utf8')
    print(json.dumps(dict(samples=plan['expected_samples'], groups=plan['camera_group_counts_per_asset'])))
