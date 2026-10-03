"""Freeze source identity and spatial-block partitions before depth fitting."""
import hashlib, json, pickle
from pathlib import Path
import cv2
import numpy as np


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()


def array_sha(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def load_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save_json(path, data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')


def block_split(points, seed, block_m=.06, fraction=.2):
    rng=np.random.default_rng(seed)
    b=np.floor(points[:,:2]/block_m).astype(int)
    key=b[:,0]*1000+b[:,1]                 # historical block convention retained
    unique=np.unique(key)
    chosen=rng.choice(unique,int(round(fraction*len(unique))),replace=False)
    return np.isin(key,chosen)


def thin(indices, n): return indices[::max(1,int(np.ceil(len(indices)/n)))]


def project(points,K):
    return np.c_[K[0,0]*points[:,0]/points[:,2]+K[0,2],K[1,1]*points[:,1]/points[:,2]+K[1,2]]


def polygon_mask(size, polygon):
    mask=np.zeros((size[1],size[0]),np.uint8)
    cv2.fillPoly(mask,[np.asarray(polygon,np.int32)],1)
    return mask.astype(bool)


def point_pixels(points,K,shape):
    uv=np.rint(project(points,K)).astype(int)
    good=(points[:,2]>0)&(uv[:,0]>=0)&(uv[:,0]<shape[1])&(uv[:,1]>=0)&(uv[:,1]<shape[0])
    return uv,good


def prepare_subject(raw_file, subject, delivery, out):
    contract=load_json(delivery/'EXPERIMENT_CONTRACT.json')
    c={r['subject']:r for r in load_json(delivery/'CALIBRATION_INPUT.json')['rows']}[subject]
    b={r['subject']:r for r in load_json(delivery/'BBOX_INPUT.json')['entries']}[subject]
    roi={r['subject']:r for r in load_json(delivery/'POSTERIOR_RGB_ROI.json')['entries']}[subject]
    identity={r['subject']:r for r in load_json(delivery/'RAW_INPUT_IDENTITY.json')['entries']}[subject]
    if sha(raw_file)!=identity['raw_pickle_sha256']: raise RuntimeError('RAW_INPUT_IDENTITY_MISMATCH '+subject)
    with Path(raw_file).open('rb') as f: d=pickle.load(f,encoding='latin1')
    labels=[x.decode('latin1') if isinstance(x,bytes) else x for x in d['pose_type']]
    i=labels.index('p_sel_prn');assert i==int(b['pose_index'])
    rgb=np.asarray(d['RGB'][i],np.uint8)
    depth=np.rot90(np.asarray(d['depth'][i])).astype(float)/1000.
    R=np.asarray(c['R_world_to_camera'],float);C=np.asarray(c['camera_center_m'],float)
    K=np.asarray(c['K'],np.float32)
    points=(np.asarray(d['pc'][i],float)-C)@R.T
    region=polygon_mask((rgb.shape[1],rgb.shape[0]),roi['polygon_xy_px'])
    assert list(rgb.shape[:2][::-1])==roi['rgb_size']
    if array_sha(rgb)!=roi['rgb_array_sha256']: raise RuntimeError('ROI_RGB_IDENTITY_MISMATCH '+subject)
    uv,inside=point_pixels(points,K,region.shape)
    back=np.zeros(len(points),bool);back[inside]=region[uv[inside,1],uv[inside,0]]
    frac=(points[:,1]-points[:,1].min())/np.ptp(points[:,1])
    torso=(frac>=.2)&(frac<=.62)
    out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'input.npz',rgb=rgb,depth_m=depth,points_m=points,K=K,R_world_to_camera=R,
        camera_center_m=C,bbox_xyxy=np.asarray(b['bbox_xyxy'],np.float32),posterior_point_mask=back,
        torso_point_mask=torso,posterior_rgb_mask=region)
    split_records=[]
    for seed in contract['seeds']:
        ho=block_split(points,seed,contract['block_m'],contract['heldout_block_fraction'])
        train=np.flatnonzero(~ho);test=np.flatnonzero(ho)
        posterior=thin(np.flatnonzero(ho&back),contract['eval_points_per_region_max'])
        torso_eval=thin(np.flatnonzero(ho&torso),contract['eval_points_per_region_max'])
        assert not np.intersect1d(train,test).size
        assert len(posterior)>0 and len(torso_eval)>0
        p=out/f'split_{seed}.npz'
        np.savez_compressed(p,train_idx=train,heldout_idx=test,posterior_eval_idx=posterior,torso_eval_idx=torso_eval)
        split_records.append(dict(seed=seed,sha256=sha(p),train_n=len(train),heldout_n=len(test),posterior_eval_n=len(posterior),torso_eval_n=len(torso_eval),train_test_intersection=0))
    valid=inside.copy();valid[inside]&=depth[uv[inside,1],uv[inside,0]]>0
    z=np.zeros(len(points));z[valid]=depth[uv[valid,1],uv[valid,0]]
    from metrics_v2 import distance_summary
    qa=dict(subject=subject,raw_keys=list(d),pose_index=i,source_sha256=sha(raw_file),
        rgb_array_sha256=array_sha(rgb),depth_array_sha256=array_sha(depth),points_array_sha256=array_sha(points),
        raw_depth_shape=list(np.asarray(d['depth'][i]).shape),rotated_depth_shape=list(depth.shape),rgb_shape=list(rgb.shape),
        source_K_or_extrinsics_fields=[k for k in d if any(t in k.lower() for t in ['intrinsic','extrinsic','camera','calib'])],
        corner_reprojection_rms_px=c['mat_corner_reprojection_rms_px'],camera_status='APPROXIMATE_PINHOLE_NOT_INDEPENDENTLY_VALIDATED',
        source_contract='Original RGB; np.rot90(raw depth), mm/1000; official filtered world cloud -> historical corner-fitted camera; no parameter adjustment from mesh',
        projected_valid_depth_fraction=float(valid.mean()),all_pc_vs_raw_depth=distance_summary(np.abs(points[valid,2]-z[valid])),
        posterior_pc_vs_raw_depth=distance_summary(np.abs(points[valid&back,2]-z[valid&back])),
        pc_vs_raw_depth_signed_median_mm=float(np.median(points[valid,2]-z[valid])*1000),
        positive_depth_fraction=float((points[:,2]>0).mean()),splits=split_records,input_npz_sha256=sha(out/'input.npz'))
    save_json(out/'input_manifest.json',qa)
    return qa
