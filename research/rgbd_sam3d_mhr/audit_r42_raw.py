"""Raw sensor replay using the independent official homogeneous transforms."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from scipy.spatial import cKDTree
from audit_r42_geometry import official_functions
from run_r41_txyz import sha


def raw_points(depth,mask,cameras,suffix,functions):
    dc,cc=({k:np.asarray(v) for k,v in cameras[name].items()}
           for name in ['kinect_depth_'+suffix,'kinect_color_'+suffix])
    y,x=np.nonzero((mask>0)&(depth>100)&(depth<5000));z=depth[y,x].astype(float)/1000
    points=np.column_stack(((x-dc['K'][0,2])*z/dc['K'][0,0],
                            (y-dc['K'][1,2])*z/dc['K'][1,1],z))
    H=functions['compute_transform_from_camera_params'](dc,cc)
    pc=points@H[:3,:3].T+H[:3,3];uv=functions['perspective_projection'](pc,cc['K'])
    xi,yi=np.rint(uv).astype(int).T
    inside=(pc[:,2]>0)&(xi>=0)&(xi<1920)&(yi>=0)&(yi<1080)
    depth_rgb=np.full((1080,1920),np.inf);np.minimum.at(depth_rgb,(yi[inside],xi[inside]),pc[inside,2])
    keep=inside.copy();keep[inside]=pc[inside,2]<=depth_rgb[yi[inside],xi[inside]]+.005
    return pc[keep],uv[keep],dict(raw_mask_valid_points=len(points),registered_front_points=int(keep.sum()))


def main(a):
    f=official_functions(a.work/'official_sources/visualizer_rgbd.py')
    selected=json.loads((a.previous/'VISUAL_SELECTION.json').read_text())['records']
    receipt=json.loads((a.work/'raw/RAW_EXPORT_RECEIPT.json').read_text())
    registered={(r['key'],r['device']):r for r in receipt['records']};views=[];cross=[];timing=[]
    for row in selected:
        key=row['key'];folder=a.work/'raw'/row['sequence'];cams=json.loads((folder/'cameras.json').read_text())
        released=json.loads((a.work/'calibration'/row['sequence']/'cameras.json').read_text());assert cams==released
        observations={}
        for device in ['kinect_000','kinect_001']:
            suffix=device[-3:];path=folder/f"{device}_{row['frame']:06d}.npz";z=np.load(path)
            assert sha(path)==registered[key,device]['registered_sha256']
            raw_depth=folder/f"{device}_{row['frame']:06d}_depth.png";raw_mask=folder/f"{device}_{row['frame']:06d}_mask.png"
            assert sha(raw_depth)==registered[key,device]['raw_depth_sha256'] and sha(raw_mask)==registered[key,device]['raw_mask_sha256']
            depth=cv2.imdecode(np.fromfile(raw_depth,np.uint8),cv2.IMREAD_UNCHANGED)
            mask=cv2.imdecode(np.fromfile(raw_mask,np.uint8),cv2.IMREAD_GRAYSCALE)
            assert np.array_equal(depth,z['depth_raw_mm']) and np.array_equal(mask,z['mask_depth'])
            p,uv,counts=raw_points(depth,mask,cams,suffix,f);observations[device]=(p,uv)
            nearest=cKDTree(p).query(z['points_color'])[0];assert nearest.max()<2e-5
            views.append(dict(key=key,device=device,**counts,stored_front_points=len(z['points_color']),
                 nearest_replayed_point_max_mm=float(nearest.max()*1000),depth_dtype=str(depth.dtype),
                 depth_shape=list(depth.shape),raw_depth_mask_exact=True,calibration_original_exact=True))
            if key not in ['p001195_a000053_000037','p001196_a000388_000040','p001194_a000062_000005','p100069_a005191_000006']:continue
            # Fixed measured boundary against current / neighbouring RGB; no lag is fitted.
            boundary=cv2.morphologyEx(mask,cv2.MORPH_GRADIENT,np.ones((3,3),np.uint8))
            boundary_points,boundary_uv,_=raw_points(depth,boundary,cams,suffix,f)
            boundary_uv=np.rint(boundary_uv).astype(int);scores=[]
            for offset in [-1,0,1]:
                rp=folder/f"{device}_{row['frame']+offset:06d}_rgb.png"
                rgb=cv2.imdecode(np.fromfile(rp,np.uint8),cv2.IMREAD_COLOR)
                if offset==0:assert np.array_equal(cv2.cvtColor(rgb,cv2.COLOR_BGR2RGB),z['rgb'])
                edges=cv2.Canny(rgb,60,120);distance=cv2.distanceTransform(255-edges,cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
                dd=distance[boundary_uv[:,1],boundary_uv[:,0]]
                scores.append(dict(offset_frames=offset,boundary_to_any_RGB_edge_median_px=float(np.median(dd)),
                                   p95_px=float(np.quantile(dd,.95)),sample_count=len(dd)))
            timing.append(dict(key=key,device=device,current_sequential_RGB_exact=True,scores=scores,
                interpretation='Edge proximity sensitivity only. Clothing texture/internal edges can dominate; not a hardware sync measurement. No offset selected or applied.'))
        pa,uva=observations['kinect_000'];pb,uvb=observations['kinect_001']
        ca={k:np.asarray(v) for k,v in cams['kinect_color_000'].items()};cb={k:np.asarray(v) for k,v in cams['kinect_color_001'].items()}
        H=f['compute_transform_from_camera_params'](cb,ca);ba=pb@H[:3,:3].T+H[:3,3]
        uvba=f['perspective_projection'](ba,ca['K']);pixel,ix=cKDTree(uva).query(uvba)
        match=(pixel<=4)&(ba[:,2]>0);dz=(ba[match,2]-pa[ix[match],2])*1000
        cross.append(dict(key=key,identity=row['identity'],matched_points=int(match.sum()),total_B_points=len(pb),
            signed_z_median_mm=float(np.median(dz)),absolute_z_median_mm=float(np.median(abs(dz))),
            absolute_z_p95_mm=float(np.quantile(abs(dz),.95)),fraction_abs_over_50mm=float(np.mean(abs(dz)>50)),
            note='Independent observed sensors, full point clouds. Occluded/opposite surfaces are included, not fitted; 4px proximity is not certified point correspondence.'))
    out=dict(status='RAW_REPLAY_AND_FRAME_IDENTITY_PASS',views=views,cross_camera_observed=cross,temporal=timing,
             video_metadata=receipt['temporal_records'],test_read=False,model_used=False,calibration_modified=False,
             synchronization_status='FRAME_INDEX_PASS_HARDWARE_TIMESTAMPS_UNAVAILABLE',
             registration_status='RELEASED_PINHOLE_REPLAY_PASS_PHYSICAL_PIXEL_ACCURACY_NOT_CERTIFIED')
    (a.work/'RAW_SENSOR_QA.json').write_text(json.dumps(out,indent=2));print('RAW_QA_PASS',len(views),len(timing),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--previous',type=Path,required=True);main(p.parse_args())
