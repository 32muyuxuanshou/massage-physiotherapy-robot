"""Re-evaluate frozen meshes; this file never imports model fitting functions."""
import argparse
from pathlib import Path
import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt
from data_v2 import load_json,save_json,sha,project
from metrics_v2 import ray_depth_residual,distance_summary,common_hit_mask
from surface_metrics import point_to_triangle_distances


def projected_support(points,K,shape):
    uv=np.rint(project(points,K)).astype(int)
    ok=(uv[:,0]>=0)&(uv[:,0]<shape[1])&(uv[:,1]>=0)&(uv[:,1]<shape[0])
    mask=np.zeros(shape,np.uint8);mask[uv[ok,1],uv[ok,0]]=1
    return cv2.dilate(mask,np.ones((7,7),np.uint8)).astype(bool)


def silhouette_metrics(pred,reference):
    p=pred.astype(np.uint8);r=reference.astype(np.uint8)
    ep=p-cv2.erode(p,np.ones((3,3),np.uint8));er=r-cv2.erode(r,np.ones((3,3),np.uint8))
    if ep.any() and er.any():
        d=np.r_[distance_transform_edt(~er.astype(bool))[ep>0],distance_transform_edt(~ep.astype(bool))[er>0]]
        boundary=float(np.median(d));p95=float(np.percentile(d,95))
    else: boundary=None;p95=None
    return dict(iou=float((pred&reference).sum()/max((pred|reference).sum(),1)),
        boundary_median_px=boundary,boundary_p95_px=p95,
        reference='full filtered-pointcloud projected support dilated 3 px; shared upstream diagnostic, not manual GT')


def evaluate_subject(subject,delivery,out,methods=None,seeds=None):
    contract=load_json(delivery/'EXPERIMENT_CONTRACT.json');method_names=methods or contract['methods']
    inputs=np.load(out/'inputs'/subject/'input.npz',allow_pickle=False)
    points=inputs['points_m'];K=inputs['K']
    ids=np.asarray(load_json(delivery/'POSTERIOR_FACE_MASK.json')['face_ids'],int)
    rows=[]
    for seed in (contract['seeds'] if seeds is None else seeds):
        split=np.load(out/'inputs'/subject/f'split_{seed}.npz',allow_pickle=False)
        residuals={};meshes={};distances={}
        for method in method_names:
            p=out/'meshes'/subject/f'seed_{seed}'/(method.replace('+','_')+'.npz')
            z=np.load(p,allow_pickle=False); V=z['vertices_m'];F=z['faces']
            meshes[method]=(V,F,p)
            for region,index_key in [('posterior','posterior_eval_idx'),('torso','torso_eval_idx')]:
                query=points[split[index_key]]
                surface_faces=F[ids] if region=='posterior' else F
                distances[method,region]=point_to_triangle_distances(query,V,surface_faces)
                residuals[method,region]=ray_depth_residual(query,V,F,K)
        common={region:common_hit_mask([residuals[m,region][1] for m in method_names]) for region in ['posterior','torso']}
        for method in method_names:
            V,F,path=meshes[method]
            row=dict(subject=subject,split='dev' if subject in contract['dev'] else 'test',seed=seed,method=method,mesh_sha256=sha(path))
            per_point={}
            for region,index_key in [('posterior','posterior_eval_idx'),('torso','torso_eval_idx')]:
                d=distances[method,region];r,hit=residuals[method,region];cm=common[region]
                row[region]=dict(d3d=distance_summary(d),ray_absolute=distance_summary(np.abs(r[hit])),
                    ray_common_hit_absolute=distance_summary(np.abs(r[cm])),ray_hit_fraction=float(hit.mean()),
                    ray_common_hit_fraction=float(cm.mean()),point_count=len(d),
                    ray_signed_median_mm=float(np.median(r[hit])*1000) if hit.any() else None)
                per_point[region+'_point_idx']=split[index_key]
                per_point[region+'_d3d_m']=d;per_point[region+'_ray_signed_m']=r
                per_point[region+'_hit']=hit;per_point[region+'_common_hit']=cm
            metric_npz=out/'evaluation'/subject/f'seed_{seed}'/(method.replace('+','_')+'_metrics.npz')
            metric_npz.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(metric_npz,**per_point)
            meta=load_json(path.with_suffix('.json'));row['optimization']=meta['optimization'];row['mesh_quality']=meta['mesh_quality']
            row['silhouette']=meta.get('silhouette',{'status':'NOT_RENDERED_YET'})
            row['common_hit_methods']=method_names
            row['source_status']=meta['source_status']
            row['input_sha256']=sha(out/'inputs'/subject/'input.npz')
            row['split_sha256']=sha(out/'inputs'/subject/f'split_{seed}.npz')
            rows.append(row)
    save_json(out/'evaluation'/subject/'results.json',rows)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--subjects',nargs='+')
    p.add_argument('--methods',nargs='+');p.add_argument('--seeds',nargs='+',type=int);a=p.parse_args()
    delivery=Path(__file__).resolve().parents[1]
    subjects=a.subjects or load_json(delivery/'EXPERIMENT_CONTRACT.json')['subjects']
    for s in subjects:
        r=evaluate_subject(s,delivery,a.out,a.methods,a.seeds);print(s,len(r),'cached-mesh evaluation complete',flush=True)
