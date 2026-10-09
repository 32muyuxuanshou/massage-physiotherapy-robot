"""Deterministic metadata/data QA and calibrated registration; no model outputs.

Geometry functions copied unchanged from the project's 2026-09-09 audited
HuMMan adapter. Never fill RGB registration holes with dilated depth values.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import cv2
import numpy as np
from humman_geometry import load_humman_view,project


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--split',type=Path,required=True)
    p.add_argument('--frames-per-sequence',type=int,default=8)
    args=p.parse_args();cv2.setNumThreads(1)
    split=json.loads(args.split.read_text())
    data=args.root/'datasets/processed'
    out=args.root/'datasets/registered_v1';out.mkdir(exist_ok=False)
    records=[];start=time.monotonic()
    for sequence,role in sorted(split['sequence_roles'].items()):
        frame_sets=[{int(p.stem) for p in (data/sequence/modality/camera).glob('*.png')}
                    for modality in ['kinect_depth','kinect_mask'] for camera in ['kinect_000','kinect_001']]
        candidates=sorted(set.intersection(*frame_sets))
        assert candidates,'MISSING_PAIRED_FRAMES'
        # Pure-data sampling, frozen irrespective of any network/metric result.
        selected=sorted({candidates[round(i)] for i in np.linspace(.05*(len(candidates)-1),
                              .95*(len(candidates)-1),min(args.frames_per_sequence,len(candidates)))})
        for frame in selected:
            row=dict(sequence=sequence,identity=sequence.split('_')[0],role=role,frame=frame,views={})
            for camera in ['kinect_000','kinect_001']:
                view=load_humman_view(data,sequence,camera,frame)
                points=view['points_color'];h,w=view['rgb'].shape[:2]
                assert len(points)>100,'EMPTY_OR_INSUFFICIENT_REGISTERED_DEPTH'
                uv,positive=project(points,view['color_camera']['K'])
                u,v=np.rint(uv[:,0]).astype(int),np.rint(uv[:,1]).astype(int)
                zbuffer=np.full((h,w),np.inf,np.float32)
                np.minimum.at(zbuffer,(v,u),points[:,2])
                registered=np.where(np.isfinite(zbuffer),zbuffer,0).astype(np.float32)
                folder=out/sequence;folder.mkdir(exist_ok=True)
                name=f'{camera}_{frame:06d}.npz';path=folder/name
                np.savez_compressed(path,rgb=view['rgb'],depth_rgb_z_m=registered,
                    valid=registered>0,mask_rgb=view['mask'],bbox=view['bbox'],
                    K=view['color_camera']['K'].astype(np.float32),
                    R=view['color_camera']['R'],T=view['color_camera']['T'],
                    points_color=points,depth_raw_mm=view['depth'],mask_depth=view['mask_depth'])
                row['views'][camera]=dict(file=str(path.relative_to(out)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    rgb_shape=list(view['rgb'].shape),depth_shape=list(view['depth'].shape),
                    valid_registered_pixels=int((registered>0).sum()),person_points=len(points),
                    depth_range_m=[float(points[:,2].min()),float(points[:,2].max())],
                    registration=view['registration'],use='INPUT_OPTIMIZATION' if camera=='kinect_000' else 'HELD_OUT_ONLY')
            records.append(row)
        print('QA_PREPARED',sequence,role,len(selected),flush=True)
    report=dict(status='FRAME_READ_AND_REGISTRATION_QA_PASS_NO_MODEL_EXECUTED',records=records,
        frames=len(records),sequences=len(split['sequence_roles']),
        sampling='8 quantiles from 5%-95% of joint depth/mask frame-index intersection; unchanged across cameras',
        identity_split_sha256=hashlib.sha256(args.split.read_bytes()).hexdigest(),
        input_camera='kinect_000',heldout_camera='kinect_001',seconds=time.monotonic()-start,
        limitations='Read/validity/calibrated registration QA, not independent proof of sensor precision. No new distortion coefficients invented.')
    (out/'FRAME_MANIFEST_V1.json').write_text(json.dumps(report,indent=2))
    (args.root/'runs/HUMMAN_FRAME_QA_R1.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)


if __name__=='__main__':main()
