"""BEHAVE registered color-depth geometry; source calibration is never fitted."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from metrics import behave_world_to_camera

def camera(calibs, sequence, kid):
    root=Path(calibs);date=sequence.split('_')[0]
    intrinsic=root/'intrinsics'/str(kid)/'calibration.json'
    extrinsic=root/date/'config'/str(kid)/'config.json'
    c=json.loads(intrinsic.read_text())['color'];e=json.loads(extrinsic.read_text())
    return {'K':np.array([[c['fx'],0,c['cx']],[0,c['fy'],c['cy']],[0,0,1.]]),
            'dist':np.array(c['opencv'][4:]),'R':np.array(e['rotation']).reshape(3,3),
            't':np.array(e['translation']),
            'table':np.load(root/'intrinsics'/str(kid)/'pointcloud_table.npy',mmap_mode='r'),
            'files':[intrinsic,extrinsic,root/'intrinsics'/str(kid)/'pointcloud_table.npy']}

def sensor(frame, kid, cam):
    frame=Path(frame)
    rgb=cv2.imread(str(frame/f'k{kid}.color.jpg'))
    depth=cv2.imread(str(frame/f'k{kid}.depth.png'),cv2.IMREAD_UNCHANGED)
    mask=cv2.imread(str(frame/f'k{kid}.person_mask.jpg'),cv2.IMREAD_GRAYSCALE)
    if rgb is None or depth is None or mask is None:
        raise ValueError('Unreadable actual RGB/depth/mask: '+str(frame))
    if depth.dtype!=np.uint16 or mask.shape!=depth.shape or cam['table'].shape[:2]!=depth.shape or rgb.shape[:2]!=depth.shape:
        raise ValueError('Unexpected registered BEHAVE pixel-domain shapes')
    indices=np.flatnonzero((depth>0)&(mask>127))
    table=cam['table'].reshape(-1,2)[indices]
    z=depth.reshape(-1)[indices].astype(np.float64)/1000.
    points=np.column_stack([table*z[:,None],z])
    valid=np.isfinite(points).all(1)
    return cv2.cvtColor(rgb,cv2.COLOR_BGR2RGB),depth,mask,points[valid],indices[valid]

def fixed_indices(length, key, count):
    if length<=count:return np.arange(length,dtype=np.int64)
    seed=int(hashlib.sha256(key.encode()).hexdigest()[:16],16)
    return np.sort(np.random.default_rng(seed).choice(length,count,replace=False))

def project(points, cam):
    return cv2.projectPoints(np.asarray(points,dtype=np.float64),np.zeros(3),np.zeros(3),cam['K'],cam['dist'])[0].reshape(-1,2)

def local_to_world(points, cam):return np.asarray(points)@cam['R'].T+cam['t']
def world_to_local(points, cam):return behave_world_to_camera(points,cam['R'],cam['t'])

def pinhole_input(rgb, depth, mask, cam):
    """Explicit all-method undistortion, with the released K held fixed."""
    h,w=depth.shape
    mx,my=cv2.initUndistortRectifyMap(cam['K'],cam['dist'],None,cam['K'],(w,h),cv2.CV_32FC1)
    color=cv2.remap(rgb,mx,my,cv2.INTER_LINEAR,borderValue=0)
    d=cv2.remap(depth,mx,my,cv2.INTER_NEAREST,borderValue=0).astype(np.float32)/1000.
    m=cv2.remap(mask,mx,my,cv2.INTER_NEAREST,borderValue=0)>127
    y,x=np.where(m)
    if not len(x):raise ValueError('Empty actual K0 foreground mask')
    bbox=np.array([max(0,x.min()-25),max(0,y.min()-25),min(w-1,x.max()+25),min(h-1,y.max()+25)],np.float32)
    return color,d*m,m,bbox
