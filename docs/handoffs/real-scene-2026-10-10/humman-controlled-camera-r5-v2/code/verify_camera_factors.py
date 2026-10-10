"""Verify actual cached transforms, not just requested camera labels."""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    a=p.parse_args()
    rows=json.loads((a.root/'MANIFEST.json').read_text())['samples']
    checks=[]
    for asset_id in sorted({r['asset_id'] for r in rows}):
        samples=[r for r in rows if r['asset_id']==asset_id]
        errors=[]
        for group in ['distance','multiview_distance','elevation','roll','offcentre','focal','matched_angular_size']:
            selected=[r for r in samples if r['view']['group']==group]
            for r in selected:
                R=np.array(r['R_world_to_camera']);t=np.array(r['T_world_to_camera'])
                target=np.array(r['reference_point_scene_m']);actual=R@target+t
                requested=np.array([r['view']['offset_x_fraction']*640*r['view']['distance_m']/r['view']['focal_px'],
                                    r['view']['offset_y_fraction']*480*r['view']['distance_m']/r['view']['focal_px'],
                                    r['view']['distance_m']])
                errors.append(float(np.max(np.abs(actual-requested))))
            if group in ['distance','offcentre','focal','matched_angular_size']:
                for r in selected:
                    assert np.allclose(r['R_world_to_camera'],selected[0]['R_world_to_camera'],atol=1e-6)
            if group in ['distance','multiview_distance','roll','offcentre']:
                assert len({json.dumps(r['K']) for r in selected})==1
            if group=='multiview_distance':
                for yaw in {r['view']['yaw_deg'] for r in selected}:
                    same=[r for r in selected if r['view']['yaw_deg']==yaw]
                    assert all(np.allclose(r['R_world_to_camera'],same[0]['R_world_to_camera'],atol=1e-6) for r in same)
            if group=='matched_angular_size':
                ratio=[r['view']['focal_px']/r['view']['distance_m'] for r in selected]
                assert np.ptp(ratio)<1e-9
        # Blender mathutils matrices are float32: allow eight epsilon at scene distance.
        tolerance=8*np.finfo(np.float32).eps*max(r['view']['distance_m'] for r in samples)
        assert max(errors)<tolerance
        assert len({r['geometry_file'] for r in samples})==1
        assert len({json.dumps(r['lighting']) for r in samples})==1
        checks.append(dict(asset_id=asset_id,reference_camera_max_error_m=max(errors),numerical_tolerance_m=float(tolerance),
                           cameras=len(samples),reference_checks=len(errors),shared_geometry=True))
    report=dict(status='CAMERA_FACTOR_QA_PASS',assets=len(checks),samples=len(rows),checks=checks,
                groups=dict(Counter(r['view']['group'] for r in rows)),
                fixed_distance_group_K_and_R=True,fixed_world_body_and_lighting=True,
                tolerance_basis='8 * float32 epsilon * maximum camera reference Z; numerical QA only',
                source_root_label_available=False,TEST_read=False)
    (a.root/'CAMERA_FACTOR_QA.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='checks'}))


if __name__=='__main__':
    main()
