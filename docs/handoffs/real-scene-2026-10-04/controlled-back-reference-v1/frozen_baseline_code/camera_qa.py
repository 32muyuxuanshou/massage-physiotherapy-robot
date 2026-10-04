"""Source-based nonplanar camera audit. Does not read predicted meshes."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from data_v2 import load_json,save_json,point_pixels,sha
from metrics_v2 import distance_summary


def camera_audit(subject,out):
    root=out/'inputs'/subject;meta=load_json(root/'input_manifest.json')
    z=np.load(root/'input.npz',allow_pickle=False);P=z['points_m'];K=z['K'];dep=z['depth_m'];rgb=z['rgb']
    uv,inside=point_pixels(P,K,dep.shape);valid=inside.copy();valid[inside]&=dep[uv[inside,1],uv[inside,0]]>0
    back=z['posterior_point_mask'];ids=np.flatnonzero(valid&back);sensor=dep[uv[ids,1],uv[ids,0]]
    pixel_camera=np.c_[(uv[ids,0]-K[0,2])*sensor/K[0,0],(uv[ids,1]-K[1,2])*sensor/K[1,1],sensor]
    # Coordinates at the same integer image pixels; not nearest-neighbour matching.
    diag=dict(subject=subject,input_sha256=sha(root/'input.npz'),camera_status=meta['camera_status'],
        posterior_nonplanar_z_span_mm=float(np.ptp(P[back,2])*1000),
        posterior_source_z_residual=distance_summary(np.abs(P[ids,2]-sensor)),
        posterior_source_same_pixel_3d_residual=distance_summary(np.linalg.norm(P[ids]-pixel_camera,axis=1)),
        valid_posterior_source_points=len(ids),corner_reprojection_rms_px=meta['corner_reprojection_rms_px'],
        mesh_used_to_adjust_camera=False,decision='DIAGNOSTIC_ONLY; original physical RGB-D calibration not recovered',
        source_depth_warning='unfiltered raw depth and filtered world cloud differ; occlusion/filtering/projection effects mixed')
    h,w=dep.shape;canvas=Image.new('RGB',(w*3,h+80),'white');draw=ImageDraw.Draw(canvas)
    canvas.paste(Image.fromarray(rgb),(0,80))
    near,far=np.percentile(dep[dep>0],[2,98]);display=(np.clip((far-dep)/(far-near),0,1)*255).astype(np.uint8);display[dep<=0]=0
    canvas.paste(Image.fromarray(display).convert('RGB'),(w,80));overlay=rgb.copy()
    # Cyan filtered-cloud sample vs original RGB, independent of any prediction.
    dots=uv[inside][::25];overlay[dots[:,1],dots[:,0]]=(0,255,255)
    canvas.paste(Image.fromarray(overlay),(2*w,80))
    draw.text((8,8),subject+' original RGB',fill='black');draw.text((w+8,8),'rot90(raw depth); mm -> metres',fill='black')
    draw.text((2*w+8,8),'cyan: filtered world cloud projection',fill='black')
    draw.text((2*w+8,28),f'Back depth discrepancy med {diag["posterior_source_z_residual"]["median_mm"]:.2f} mm',fill='black')
    draw.text((2*w+8,46),'Approximate camera, not independent calibration',fill='black')
    dest=out/'camera_audit';dest.mkdir(exist_ok=True);canvas.save(dest/f'{subject}_sources.jpg',quality=93)
    save_json(dest/f'{subject}.json',diag);return diag


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--subjects',nargs='+',required=True);a=p.parse_args()
    for s in a.subjects:camera_audit(s,a.out)
