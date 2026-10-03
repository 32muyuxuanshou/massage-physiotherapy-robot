"""Pre-model common-surface qualification from RGB review and sensor geometry.

K0 proposed rectangles are reviewed separately before freezing. Heldout ROI is
the source-patch projection hull, not a separately chosen unrelated back patch.
RGB confirmation remains required; numeric closeness alone is insufficient.
"""
import sys,argparse
import cv2,numpy as np
from scipy.spatial import cKDTree
from PIL import Image,ImageDraw,ImageOps
from common import ROOT,OLD,BEHAVE,read,write,sha
sys.path.insert(0,str(OLD/'code'))
sys.path.insert(0,str(BEHAVE/'behave-dataset'))
from behave_v2_io import read_camera,local_to_world,world_to_local,transform_between
from data.kinect_transform import KinectTransform

Q=ROOT/'b_qualification'

def patches(overrides=None):
    inv=read(Q/'CANDIDATE_INVENTORY.json');review=read(Q/'K0_VISUAL_REVIEW.json')
    views={(v['candidate_index'],v['camera']):v for v in inv['views']}
    cfg=read(Q/'QUALIFICATION_CONTRACT.json');overrides=overrides or {}
    write(Q/'PATCH_PROJECTION_CONTRACT.json',dict(status='FROZEN_BEFORE_MODEL',
        source_patch='fractional source person display crop; default center (.50,.35), RGB-reviewed overrides',
        target_patch='convex hull of distorted-color projections of every source patch point, dilated 5 pixels',
        nn_rule='bidirectional >=50% of all valid patch points within 50mm; both patches >=30 points',
        model_runs=0,source_centers_overrides={str(k):v for k,v in overrides.items()},
        numeric_candidates_require_RGB_patch_confirmation=True))
    rows=[];cams={};qa=[];source_tiles=[]
    for rec in review['rows']:
        if rec['code']!='B' or rec['candidate_index']==153:continue
        i=rec['candidate_index'];seq=rec['sequence'];folder=BEHAVE/'data/sequences'/seq/rec['frame']
        if seq not in cams:
            cams[seq]=[read_camera(BEHAVE/'data/calibs',seq,k) for k in range(4)]
            official=KinectTransform(str(folder.parent),no_intrinsics=True);p=np.array([[.0,0,1],[.2,-.1,2],[-.3,.25,3]])
            errors=[float(np.abs(transform_between(p,cams[seq][0],cams[seq][k])-official.world2local(official.local2world(p,0),k)).max()) for k in [1,2,3]]
            qa.append(dict(sequence=seq,date=cams[seq][0]['date'],official_comparison_max_m=errors,
                status='PASS' if max(errors)<1e-9 else 'FAIL',
                calibration=[dict(path=p,sha256=sha(p)) for c in cams[seq] for p in c['provenance']]))
        cs=cams[seq];v0=views[i,0];x0,y0,x1,y1=v0['display_crop_xyxy'];cx,cy=overrides.get(i,[.50,.35])
        center=np.array([x0+cx*(x1-x0),y0+cy*(y1-y0)])
        extent=np.array([.06*(x1-x0),.05*(y1-y0)])
        poly=np.rint([center-extent,center+[-extent[0],extent[1]],center+extent,center+[extent[0],-extent[1]]]).astype(np.int32)
        cloud_world=[];patch_indices=[];polys=[poly];depths=[];rgbqa=[]
        source_world=None
        for k in range(4):
            depth=cv2.imread(str(folder/f'k{k}.depth.png'),-1);mask=cv2.imread(str(folder/f'k{k}.person_mask.jpg'),0);depths.append(depth)
            roi=np.zeros(depth.shape,np.uint8)
            if k:
                local=world_to_local(source_world,cs[k]);uv=cv2.projectPoints(local[:,None],np.zeros(3),np.zeros(3),cs[k]['K'],cs[k]['dist'])[0].reshape(-1,2)
                target=cv2.convexHull(np.rint(uv).astype(np.int32)).reshape(-1,2)
                cv2.fillPoly(roi,[target],255);roi=cv2.dilate(roi,np.ones((11,11),np.uint8));polys.append(target)
            else:cv2.fillPoly(roi,[poly],255)
            idx=np.flatnonzero((roi>0)&(depth>0)&(mask>127));ys,xs=np.unravel_index(idx,depth.shape)
            local=np.c_[cs[k]['pointcloud_table'][ys,xs],np.ones(len(idx))]*depth[ys,xs,None]/1000
            world=local_to_world(local,cs[k]);cloud_world.append(world);patch_indices.append(idx)
            if k==0:source_world=world;assert len(world)>=30
            projected=cv2.projectPoints(local[:,None],np.zeros(3),np.zeros(3),cs[k]['K'],cs[k]['dist'])[0].reshape(-1,2) if len(local) else np.empty((0,2))
            error=np.linalg.norm(projected-np.c_[xs,ys],axis=1)
            rgbqa.append(float(np.percentile(error,95)) if len(error) else None)
        supports=[]
        for k in [1,2,3]:
            w=cloud_world[k]
            if len(w):
                forward=cKDTree(w).query(source_world)[0];reverse=cKDTree(source_world).query(w)[0]
                f=float(np.mean(forward<=.05));r=float(np.mean(reverse<=.05));med=float(np.median(forward)*1000)
            else:f=r=0.;med=None
            supports.append(dict(camera=k,input_to_target_support=f,target_to_input_support=r,
                source_to_target_median_mm=med,valid_points=len(w),numeric_pass=len(w)>=30 and min(f,r)>=.5))
        directory=Q/'proposed_patches'/f'{i:03d}';directory.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(directory/'indices.npz',**{f'K{k}_flat_idx':patch_indices[k] for k in range(4)},
            **{f'K{k}_world_m':cloud_world[k] for k in range(4)})
        rows.append(dict(**rec,source_roi_center_fraction=[cx,cy],source_polygon_px=poly.tolist(),
            target_polygons_px=[p.tolist() for p in polys[1:]],source_patch_points=len(source_world),supports=supports,
            distorted_reprojection_p95_px=rgbqa,patch_indices_path=str(directory/'indices.npz'),
            patch_indices_sha256=sha(directory/'indices.npz'),numerically_common_back_possible=any(s['numeric_pass'] for s in supports)))
        rgb=Image.open(folder/'k0.color.jpg').convert('RGB');draw=ImageDraw.Draw(rgb);draw.polygon([tuple(p) for p in poly],outline=(0,180,255),width=4)
        crop=ImageOps.contain(rgb.crop(v0['display_crop_xyxy']),(280,370));tile=Image.new('RGB',(300,415),'white');tile.paste(crop,((300-crop.width)//2,40))
        d=ImageDraw.Draw(tile);d.text((5,5),f'#{i} K0 proposed source patch',fill='black');d.text((5,22),f'{rec["subject"]} / numeric common {any(s["numeric_pass"] for s in supports)}',fill='black');source_tiles.append(tile)
    for start in range(0,len(rows),12):
        page=Image.new('RGB',(1800,850),'white')
        for j,t in enumerate(source_tiles[start:start+12]):page.paste(t,(j%6*300,j//6*415))
        page.save(Q/'private_images'/f'source_roi_{start//12:02d}.jpg',quality=95)
    assert all(r['status']=='PASS' for r in qa)
    write(Q/'CAMERA_REFERENCE_QA.json',dict(status='PASS',rows=qa,model_geometry_used=False,
        reprojection_p95_px_max=max(e for r in rows for e in r['distorted_reprojection_p95_px'] if e is not None)))
    write(Q/'PROPOSED_PATCH_SUPPORT.json',dict(status='REQUIRES_RGB_PATCH_CONFIRMATION',rows=rows,model_runs=0))
    print('PROPOSED_COMMON_PATCH',len(rows),sum(r['numerically_common_back_possible'] for r in rows),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--overrides');a=p.parse_args()
    patches({int(k):v for k,v in read(a.overrides).items()} if a.overrides else None)
