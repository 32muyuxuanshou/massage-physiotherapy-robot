"""CPU real-frame QA against pinned BEHAVE transforms and sensor reprojections."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from dataset_io import camera,sensor,fixed_indices,project,world_to_local,local_to_world

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--limit',type=int,default=3)
    a=p.parse_args();a.root=a.root.resolve();data=a.root/'data';out=a.root/'reports'/'coordinate_qa';out.mkdir(parents=True,exist_ok=True)
    vendor=a.root/'vendor'/'behave-dataset'
    sys.path.insert(0,str(vendor))
    from data.kinect_transform import KinectTransform
    manifest=json.loads((data/'FROZEN_INPUT_MANIFEST.json').read_text());records=[]
    # The same historical Sub03 frames are used only for CPU geometry QA.
    chosen=manifest['rows'][:a.limit]
    for spec in chosen:
        seq=data/'sequences'/spec['sequence'];frame=seq/spec['frame'];official=KinectTransform(str(seq),no_intrinsics=True)
        mesh=trimesh.load(frame/'person/fit02/person_fit.ply',process=False)
        vw=np.asarray(mesh.vertices,dtype=np.float64)
        if vw.shape!=(6890,3):raise ValueError('Fitted reference vertex layout mismatch')
        cams=[camera(data/'calibs',spec['sequence'],k) for k in range(4)]
        worlds=[];per=[];sheet=[]
        key=spec['sequence']+'_'+spec['frame']
        for k,cam in enumerate(cams):
            v=world_to_local(vw,cam);expected=official.world2local(vw,k)
            diff=float(np.max(np.abs(v-expected)))
            rgb,depth,mask,pc,flat=sensor(frame,k,cam)
            ids=fixed_indices(len(pc),key+f':K{k}',5000)
            observed=pc[ids];worlds.append(local_to_world(observed,cam))
            uv=project(observed,cam);target=np.column_stack([flat[ids]%depth.shape[1],flat[ids]//depth.shape[1]])
            reprojection=np.linalg.norm(uv-target,axis=1)
            fit_uv=project(v,cam);canvas=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
            for pt in np.rint(fit_uv[v[:,2]>0]).astype(np.int64)[::5]:
                if 0<=pt[0]<canvas.shape[1] and 0<=pt[1]<canvas.shape[0]:cv2.circle(canvas,tuple(pt),2,(210,40,200),-1)
            canvas=cv2.resize(canvas,(640,480));cv2.putText(canvas,f'K{k}: fitted reference (purple)',(10,30),0,.65,(255,255,255),2)
            sheet.append(canvas)
            per.append({'camera':f'K{k}','official_transform_max_difference_m':diff,
                        'positive_reference_vertex_fraction':float(np.mean(v[:,2]>0)),
                        'sensor_valid_person_points':len(pc),'depth_pixel_shape':list(depth.shape),
                        'sensor_reprojection_median_px':float(np.median(reprojection)),
                        'sensor_reprojection_p95_px':float(np.percentile(reprojection,95)),
                        'fitted_reference_to_observed_vertex_nearest_median_mm':float(np.median(cKDTree(v).query(observed)[0])*1000),
                        'pass':bool(diff<1e-9 and len(pc)>0 and np.isfinite(v).all() and np.percentile(reprojection,95)<1.0)})
        overlap=[]
        for k in [1,2,3]:
            d1=cKDTree(worlds[k]).query(worlds[0])[0];d2=cKDTree(worlds[0]).query(worlds[k])[0]
            value=float((np.median(d1)+np.median(d2))*500)
            overlap.append({'pair':f'K0-K{k}','symmetric_nearest_median_mm':value,'broad_sanity_pass':value<200.0})
        image=out/(key+'.jpg');cv2.imwrite(str(image),np.vstack([np.hstack(sheet[:2]),np.hstack(sheet[2:])]))
        np.save(out/(key+'_reference_K0_m.npy'),world_to_local(vw,cams[0]))
        records.append({'sequence':spec['sequence'],'frame':spec['frame'],'reference_vertices':len(vw),
                        'reference_faces':len(mesh.faces),'reference_sha256':hashlib.sha256((frame/'person/fit02/person_fit.ply').read_bytes()).hexdigest(),
                        'cameras':per,'world_cloud_overlap':overlap,'visualization':str(image)})
    result={'status':'PASS_CODE_REPROJECTION_AND_CLOUD_SANITY' if all(c['pass'] for r in records for c in r['cameras']) and all(x['broad_sanity_pass'] for r in records for x in r['world_cloud_overlap']) else 'FAIL',
            'records':records,'official_code_loading':'Direct import of pinned official KinectTransform and its original pose loaders; dependencies isolated in vendor_python; no source modification',
            'physical_calibration_accuracy_mm':'NOT_ESTABLISHED_BY_THIS_QA',
            'interpretation':'Official code agreement, real sensor reprojection and cross-camera cloud sanity; fitted reference is not direct skin/acupoint GT; nearest-vertex distances are QA only, not benchmark metrics'}
    (out/'COORDINATE_QA.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
