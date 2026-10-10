"""Export frozen development observations and four temporal QA fixtures; CPU only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import cv2
import numpy as np


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(a):
    selected=json.loads(a.selection.read_text())['records']
    a.out.mkdir(parents=True,exist_ok=True)
    sync_keys=['p001195_a000053_000037','p001196_a000388_000040',
               'p001194_a000062_000005','p100069_a005191_000006']
    records=[];timing=[]
    for row in selected:
        key=row['key'];seq=row['sequence'];frame=row['frame']
        raw=a.root/'datasets/processed'/seq
        folder=a.out/seq;folder.mkdir(exist_ok=True)
        shutil.copy2(raw/'cameras.json',folder/'cameras.json')
        for device in ['kinect_000','kinect_001']:
            source=a.root/'datasets/registered_v1'/seq/f'{device}_{frame:06d}.npz'
            target=folder/source.name;shutil.copy2(source,target)
            with np.load(source) as z:
                dp=raw/'kinect_depth'/device/f'{frame:06d}.png'
                mp=raw/'kinect_mask'/device/f'{frame:06d}.png'
                depth=cv2.imread(str(dp),cv2.IMREAD_UNCHANGED)
                mask=cv2.imread(str(mp),cv2.IMREAD_GRAYSCALE)
                assert np.array_equal(depth,z['depth_raw_mm']) and np.array_equal(mask,z['mask_depth'])
                shutil.copy2(dp,folder/f'{device}_{frame:06d}_depth.png')
                shutil.copy2(mp,folder/f'{device}_{frame:06d}_mask.png')
                records.append(dict(key=key,device=device,registered_sha256=sha(source),
                    raw_depth_sha256=sha(dp),raw_mask_sha256=sha(mp),
                    raw_arrays_exact=True,role=row['role']))
                if key not in sync_keys:continue
                # Sequential decode independently verifies historical random-seek frame identity.
                video=raw/'kinect_color'/f'{device}.mp4';cap=cv2.VideoCapture(str(video))
                fps=cap.get(cv2.CAP_PROP_FPS);count=cap.get(cv2.CAP_PROP_FRAME_COUNT)
                for i in range(frame+2):
                    ok,bgr=cap.read();assert ok
                    if i not in [frame-1,frame,frame+1]:continue
                    rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
                    cv2.imwrite(str(folder/f'{device}_{i:06d}_rgb.png'),bgr)
                    if i==frame:assert np.array_equal(rgb,z['rgb'])
                    nd=raw/'kinect_depth'/device/f'{i:06d}.png'
                    nm=raw/'kinect_mask'/device/f'{i:06d}.png'
                    if nd.exists() and nm.exists():
                        shutil.copy2(nd,folder/f'{device}_{i:06d}_depth.png')
                        shutil.copy2(nm,folder/f'{device}_{i:06d}_mask.png')
                    timing.append(dict(key=key,device=device,decoded_index=i,
                        video_pts_ms=cap.get(cv2.CAP_PROP_POS_MSEC),fps=fps,frame_count=count,
                        exact_current_registered_rgb=i==frame,
                        neighbouring_raw_depth_exists=nd.exists(),neighbouring_raw_mask_exists=nm.exists()))
                cap.release()
        print('RAW_EXPORT',key,flush=True)
    report=dict(status='EXACT_RAW_ARRAYS_AND_SEQUENTIAL_RGB_VERIFIED',records=records,
                temporal_records=timing,test_read=False,scope='27 historical frames; 4 temporal fixtures; no model inference',
                synchronization_limit='Video PTS and file indices are not original hardware clock timestamps.')
    (a.out/'RAW_EXPORT_RECEIPT.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--selection',type=Path,required=True)
    main(p.parse_args())
