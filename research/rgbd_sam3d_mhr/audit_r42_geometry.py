"""Independent HuMMan geometry audit. No fitting, new sampling contract or training."""
import argparse
import ast
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time
import numpy as np
from scipy.spatial import cKDTree
from run_r41_txyz import dependencies,sha,summary


def official_functions(path):
    space=dict(np=np)
    names=['compute_transform_from_camera_params','transform_points','perspective_projection']
    tree=ast.parse(path.read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(nodes)==len(names)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),space)
    return space


def ray_z(points,vertices,faces,K):
    """Exact frontmost two-sided triangle hit along each observation's colour ray.

    All mesh vertices must lie in front of this camera. Projected triangle AABBs
    conservatively select candidates; full triangle size is retained. Directions
    have z=1, so the Moller-Trumbore ray parameter is metric Z, not ray length.
    """
    tri=np.asarray(vertices,np.float64)[faces]
    assert tri[:,:,2].min()>0
    uv=tri[:,:,:2]/tri[:,:,2,None]*[K[0,0],K[1,1]]+K[:2,2]
    low,high=uv.min(1),uv.max(1)
    rays=points/points[:,2,None];pixels=rays[:,:2]*[K[0,0],K[1,1]]+K[:2,2]
    z=np.full(len(points),np.nan)
    for i,(d,pixel) in enumerate(zip(rays,pixels)):
        ids=np.flatnonzero(((pixel>=low-1e-7)&(pixel<=high+1e-7)).all(1))
        t=tri[ids];e1=t[:,1]-t[:,0];e2=t[:,2]-t[:,0]
        h=np.cross(d,e2);det=np.einsum('ij,ij->i',e1,h)
        usable=np.abs(det)>1e-12
        inv=np.zeros(len(det));inv[usable]=1/det[usable]
        s=-t[:,0];u=inv*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1)
        v=inv*(q@d);depth=inv*np.einsum('ij,ij->i',e2,q)
        valid=usable&(u>=-1e-8)&(v>=-1e-8)&(u+v<=1+1e-8)&(depth>0)
        if valid.any():z[i]=depth[valid].min()
    return z


def independent_triangle_distance(p,triangles):
    """Brute-force plane-interior plus closed-edge distance; independent of BVH kernel."""
    a,b,c=np.moveaxis(triangles,1,0);ab=b-a;ac=c-a
    normal=np.cross(ab,ac);n2=(normal*normal).sum(1)
    projected=p-normal*(((p-a)*normal).sum(1)/np.maximum(n2,1e-30))[:,None]
    v2=projected-a;aa=(ab*ab).sum(1);cc=(ac*ac).sum(1);bb=(ab*ac).sum(1)
    d=(v2*ab).sum(1);e=(v2*ac).sum(1);den=aa*cc-bb*bb
    u=(cc*d-bb*e)/np.maximum(den,1e-30);v=(aa*e-bb*d)/np.maximum(den,1e-30)
    interior=(den>1e-20)&(u>=0)&(v>=0)&(u+v<=1)
    best=np.where(interior,((p-projected)**2).sum(1),np.inf)
    for q,r in [(a,b),(b,c),(c,a)]:
        edge=r-q;t=np.clip(((p-q)*edge).sum(1)/np.maximum((edge*edge).sum(1),1e-30),0,1)
        best=np.minimum(best,((p-q-t[:,None]*edge)**2).sum(1))
    return float(np.sqrt(best.min()))


def controls():
    K=np.array([[500.,0,320],[0,500.,240],[0,0,1.]])
    tri=np.array([[-4.,-4.,1.],[4.,-4.,3.],[0.,4.,2.]])
    points=np.array([tri.mean(0),.15*tri[0]+.35*tri[1]+.5*tri[2]])
    z=ray_z(points,tri,np.array([[0,1,2]]),K)
    assert np.max(abs(z-points[:,2]))<1e-12
    # An interior point far from all projected vertices checks large-face coverage.
    assert np.linalg.norm((points[0,:2]/points[0,2])-tri[:,:2]/tri[:,2,None],axis=1).min()>.5
    assert independent_triangle_distance(points[0],tri[None])<1e-12
    return dict(status='PASS',perspective_ray_max_error_m=float(np.max(abs(z-points[:,2]))),large_triangle_interior_hit=True)


def frame_diagnostic(task):
    source,old,work,row=task;source,old,work=Path(source),Path(old),Path(work)
    f=dependencies(source/'code');assets=source/'assets';key=row['key']
    a=np.load(assets/'original_assets/inputs'/(key+'.npz'));pa=a['points_camera_A'].astype(float)
    pb=np.load(assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
    faces=np.load(assets/'original_assets/official/faces.npy');K=a['A_K']
    indices=np.linspace(0,len(pa)-1,512,dtype=int);raypoints=pa[indices]
    cells=[('official','before',assets/'original_assets/official'),('official','after',source/'corrected/official')]
    for seed in [11,23,37]:
        g=f'g1_seed{seed}';s=f'official_body_g1_camera_seed{seed}'
        cells += [(g,'before',assets/f'r4/formal/{g}/real'),(g,'after',source/f'corrected/{g}'),
                  (s,'before',old/f'raw/{s}'),(s,'after',old/f'corrected/{s}')]
    results=[];rayarrays={}
    for cell,stage,directory in cells:
        z=np.load(directory/(key+'.npz'));v=z['vertices_camera_A'];d=f['distance'](pa,v,faces)*1000
        predicted=ray_z(raypoints,v,faces,K);hit=np.isfinite(predicted);signed=(predicted-raypoints[:,2])*1000
        rayarrays[cell+'_'+stage]=predicted
        results.append(dict(cell=cell,stage=stage,A_observed_to_mesh=summary(d),
            A_ray=dict(point_count=512,hits=int(hit.sum()),hit_fraction=float(hit.mean()),
                       signed_z_median_mm=float(np.median(signed[hit])) if hit.any() else None,
                       absolute_z_median_mm=float(np.median(abs(signed[hit]))) if hit.any() else None,
                       absolute_z_p95_mm=float(np.quantile(abs(signed[hit]),.95)) if hit.any() else None),
            mesh_z_range_m=[float(v[:,2].min()),float(v[:,2].max())],camera_m=z['pred_cam_t'].reshape(3).tolist(),
            body_extent_xyz_m=np.ptp(v.astype(float)-z['pred_cam_t'].reshape(3),axis=0).tolist(),mesh_sha256=sha(directory/(key+'.npz'))))
    # Same ray set across all methods; report common-hit residual, not just individual hits.
    common=np.logical_and.reduce([np.isfinite(v) for v in rayarrays.values()])
    for r in results:
        pred=rayarrays[r['cell']+'_'+r['stage']]
        r['A_ray']['all_method_common_hits']=int(common.sum())
        r['A_ray']['common_hit_absolute_z_median_mm']=float(np.median(abs(pred[common]-raypoints[common,2]))*1000) if common.any() else None
    independent=[]
    if key in ['p001195_a000053_000037','p001196_a000388_000040','p001194_a000062_000005','p100069_a005191_000006']:
        for stage,directory in [('before',assets/'original_assets/official'),('after',source/'corrected/official')]:
            z=np.load(directory/(key+'.npz'));tri=z['vertices_camera_B'].astype(float)[faces]
            ix=np.linspace(0,2047,8,dtype=int);reference=f['distance'](pb[ix],z['vertices_camera_B'],faces)
            brute=np.array([independent_triangle_distance(p,tri) for p in pb[ix]])
            error=float(np.max(abs(reference-brute)));assert error<1e-9
            independent.append(dict(stage=stage,point_indices=ix.tolist(),max_difference_mm=error*1000))
    cache=work/'ray_cache';cache.mkdir(exist_ok=True)
    np.savez_compressed(cache/(key+'.npz'),source_A_indices=indices,observed_points_A=raypoints,common_hit=common,**rayarrays)
    return dict(key=key,identity=row['identity'],role=row['role'],methods=results,independent_bruteforce=independent)


def main(a):
    started=time.monotonic();a.out.mkdir(parents=True,exist_ok=True)
    official=official_functions(a.out/'official_sources/visualizer_rgbd.py');f=dependencies(a.source/'code')
    rows=json.loads((a.source/'FRAME_CONTRACT.json').read_text())['records'];checks=[]
    assets=a.source/'assets'
    for row in rows:
        key=f"{row['sequence']}_{row['frame']:06d}";z=np.load(assets/'original_assets/inputs'/(key+'.npz'))
        cams=json.loads((a.out/'calibration'/row['sequence']/'cameras.json').read_text())
        ca,cb=({k:z[p+'_'+k] for k in ['K','R','T']} for p in ['A','B'])
        for prefix,suffix in [('A','000'),('B','001')]:
            for k in ['K','R','T']:assert np.array_equal(z[prefix+'_'+k],np.asarray(cams['kinect_color_'+suffix][k],dtype=z[prefix+'_'+k].dtype))
        p=z['points_camera_A'].astype(float);b=np.load(assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B'].astype(float)
        transform=official['compute_transform_from_camera_params'](ca,cb)
        exact=p@transform[:3,:3].T+transform[:3,3];old=f['transform_camera'](p,ca,cb)
        err=float(np.max(abs(exact-old)));assert err<2e-5
        projection=official['perspective_projection'](b,cb['K']);own=b[:,:2]/b[:,2,None]*[cb['K'][0,0],cb['K'][1,1]]+cb['K'][:2,2]
        assert np.max(abs(projection-own))<1e-9
        inv=official['compute_transform_from_camera_params'](cb,ca);ba=b@inv[:3,:3].T+inv[:3,3]
        # Observed A/B agreement only; opposite visible surfaces can inflate these values.
        uv_a=official['perspective_projection'](p,ca['K']);uv_ba=official['perspective_projection'](ba,ca['K'])
        pix,ix=cKDTree(uv_a).query(uv_ba);match=(pix<=4)&(ba[:,2]>0)
        dz=(ba[match,2]-p[ix[match],2])*1000
        nn=cKDTree(p).query(ba)[0]*1000
        checks.append(dict(key=key,identity=row['identity'],role=row['role'],calibration_exact=True,
            official_transform_max_difference_mm=err*1000,projection_max_difference_px=float(np.max(abs(projection-own))),
            rotation_orthogonality_max=max(float(np.max(abs(c['R']@c['R'].T-np.eye(3)))) for c in [ca,cb]),
            observed_B_to_A_nn=summary(nn),same_ray_4px=dict(matches=int(match.sum()),count=len(b),
                signed_z_median_mm=float(np.median(dz)) if len(dz) else None,
                absolute_z_median_mm=float(np.median(abs(dz))) if len(dz) else None,
                absolute_z_p95_mm=float(np.quantile(abs(dz),.95)) if len(dz) else None),
            evidence_limit='Different visible surfaces, sparse points, 4px association and occlusion; no registration/clock GT.'))
    selection=json.loads((a.previous/'VISUAL_SELECTION.json').read_text())['records'];assert len(selection)==27
    tasks=[(str(a.source),str(a.previous),str(a.out),r) for r in selection]
    with ProcessPoolExecutor(a.workers) as pool:diagnostics=list(pool.map(frame_diagnostic,tasks))
    report=dict(status='COMPUTATIONAL_CHAIN_PASS_PHYSICAL_QA_SEPARATE',controls=controls(),full_calibration_checks=checks,
                detailed_27_frames=diagnostics,seconds=time.monotonic()-started,source_commit='4ac1f413',
                no_model_inference=True,no_training=True,no_Txyz_refit=True,no_B_fit=True,test_read=False,
                diagnostic_contract=dict(A_ray_points=512,ray_selection='linspace of original fixed A array; audit only',
                historical_B_points=2048,primary_metric_unchanged=True,all_seeds=[11,23,37]))
    (a.out/'GEOMETRY_AUDIT.json').write_text(json.dumps(report,indent=2));print('GEOMETRY_AUDIT_COMPLETE',report['seconds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--previous',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);main(p.parse_args())
