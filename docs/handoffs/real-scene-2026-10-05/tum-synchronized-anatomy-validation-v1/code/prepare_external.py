"""Source geometry QA and label-free input; no model inference or source cropping."""
import json, hashlib, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import torch
import torch.nn.functional as TF
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path('/raid5/xuhd/datasets/tum_synchronized_anatomy_validation_20261005')
LEVELS=['C7','T3','T5','T9','L2']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')

def raster(vertices,faces,bounds,shape):
    xmin,xmax,zmin,zmax=bounds;h,w=shape
    xy=np.column_stack(((vertices[:,0]-xmin)/(xmax-xmin)*(w-1),(zmax-vertices[:,2])/(zmax-zmin)*(h-1)))
    height=np.full((h,w),np.inf)
    for face in faces:
        q=xy[face];y=vertices[face,1]
        den=(q[1,1]-q[2,1])*(q[0,0]-q[2,0])+(q[2,0]-q[1,0])*(q[0,1]-q[2,1])
        if abs(den)<1e-12:continue
        x0=max(0,int(np.ceil(q[:,0].min())));x1=min(w-1,int(np.floor(q[:,0].max())))
        y0=max(0,int(np.ceil(q[:,1].min())));y1=min(h-1,int(np.floor(q[:,1].max())))
        if x1<x0 or y1<y0:continue
        xx,yy=np.meshgrid(np.arange(x0,x1+1),np.arange(y0,y1+1))
        a=((q[1,1]-q[2,1])*(xx-q[2,0])+(q[2,0]-q[1,0])*(yy-q[2,1]))/den
        b=((q[2,1]-q[0,1])*(xx-q[2,0])+(q[0,0]-q[2,0])*(yy-q[2,1]))/den;c=1-a-b
        inside=(a>=-1e-10)&(b>=-1e-10)&(c>=-1e-10)
        view=height[y0:y1+1,x0:x1+1];np.minimum(view,np.where(inside,a*y[0]+b*y[1]+c*y[2],np.inf),out=view)
    valid=np.isfinite(height);height[~valid]=0
    return height,valid

def surface_at(uv,bounds,height,valid):
    if not np.isfinite(uv).all() or (uv<0).any() or (uv>1).any():return None
    h,w=height.shape;x=uv[0]*(w-1);y=uv[1]*(h-1);i=int(np.floor(x));j=int(np.floor(y));i1=min(i+1,w-1);j1=min(j+1,h-1)
    if not valid[j:j1+1,i:i1+1].all():return None
    a=x-i;b=y-j;depth=(1-b)*((1-a)*height[j,i]+a*height[j,i1])+b*((1-a)*height[j1,i]+a*height[j1,i1])
    xmin,xmax,zmin,zmax=bounds;return np.array([xmin+uv[0]*(xmax-xmin),depth,zmax-uv[1]*(zmax-zmin)])

def one(header):
    torch.set_num_threads(1);subject=header['subject'];start=time.time();base=ROOT/'raw/PLOS_repo/dataset'/subject
    mesh=trimesh.load(base/'surfaces/body_surface.ply',process=False);vertices=np.asarray(mesh.vertices)*1000;faces=np.asarray(mesh.faces)
    world=header['qform_code']>0 or header['sform_code']>0
    A=np.array(header['affine_ras_mm']) if world else np.diag(header['voxel_spacing_mm']+[1.]);shape=np.array(header['shape']);assert np.allclose(A[:3,:3],np.diag(np.diag(A[:3,:3])))
    end=A[:3,3]+np.diag(A[:3,:3])*(shape-1);lower=np.minimum(A[:3,3],end);upper=np.maximum(A[:3,3],end)
    bounds=np.array([lower[0],upper[0],lower[2],upper[2]])
    saved=ROOT/'inputs'/(subject+'.npz')
    if saved.exists():
        data=dict(np.load(saved));assert np.array_equal(data['xz_bounds_mm'],bounds);height=data['surface_height_mm'];valid=data['surface_valid']
    else:height,valid=raster(vertices,faces,bounds,(int(shape[2]),int(shape[0])))
    inv=np.linalg.inv(A);body_voxel=vertices@inv[:3,:3].T+inv[:3,3];inside=((body_voxel>=-1.5)&(body_voxel<=shape+0.5)).all(1)
    assert inside.mean()>.99
    targets=[];flags=[];xyz=[]
    for level in LEVELS:
        path=base/'surfaces/vertebrae'/(level+'.stl')
        if not path.exists():targets.append(dict(level=level,status='MISSING_SOURCE_BONE'));flags.append(False);xyz.append([0.,0.,0.]);continue
        bone=trimesh.load(path,process=False);V=np.unique(np.asarray(bone.vertices),axis=0)
        # The author STL is already mm, unlike the body PLY which is metres.
        vox=V@inv[:3,:3].T+inv[:3,3];bone_inside=((vox>=-1.5)&(vox<=shape+0.5)).all(1);assert bone_inside.mean()>.99
        clipped=bool((vox.min(0)<=.5).any() or (vox.max(0)>=shape-1.5).any())
        threshold=np.quantile(V[:,1],.02);tip=V[V[:,1]<=threshold].mean(0)
        uv=np.array([(tip[0]-bounds[0])/(bounds[1]-bounds[0]),(bounds[3]-tip[2])/(bounds[3]-bounds[2])]);skin=surface_at(uv,bounds,height,valid)
        gap=None if skin is None else float(tip[1]-skin[1]);ok=not clipped and skin is not None and 0<=gap<=200
        targets.append(dict(level=level,status='CT_SURFACE_PROXY' if ok else 'DATA_INVALID_TARGET',clipped=clipped,posterior_extreme_bone_xyz_mm=tip.tolist(),surface_xyz_mm=None if skin is None else skin.tolist(),bone_to_skin_posterior_mm=gap,bone_inside_native_volume_fraction=float(bone_inside.mean()),mesh_sha256=sha(path)))
        flags.append(bool(ok));xyz.append(skin.tolist() if ok else [0.,0.,0.])
    xyz=np.array(xyz,np.float32);flags=np.array(flags,bool);z=xyz[flags,2];order=bool((np.diff(z)<0).all());eligible=flags.sum()>=3 and valid.sum()>=10000 and order
    center=float(np.median(height[valid]));weighted=np.where(valid,height-center,0)
    small=TF.interpolate(torch.tensor(np.stack([weighted,valid.astype(np.float32)]))[None],size=(128,128),mode='bilinear',align_corners=True)[0].numpy()
    small_height=np.divide(small[0],small[1],out=np.zeros_like(small[0]),where=small[1]>.5)/300
    u,v=np.meshgrid(np.linspace(0,1,128),np.linspace(0,1,128));inp=np.stack([small_height,(small[1]>.5).astype(float),(u-.5)*(bounds[1]-bounds[0])/400,(v-.5)*(bounds[3]-bounds[2])/800]).astype(np.float32)
    uv=np.column_stack(((xyz[:,0]-bounds[0])/(bounds[1]-bounds[0]),(bounds[3]-xyz[:,2])/(bounds[3]-bounds[2]))).astype(np.float32)
    path=ROOT/'inputs'/(subject+'.npz');path.parent.mkdir(exist_ok=True)
    np.savez_compressed(path,input=inp,target_uv=uv,target_xyz_mm=xyz,target_valid=flags,xz_bounds_mm=bounds,surface_height_mm=height,surface_valid=valid)
    fig,ax=plt.subplots(figsize=(8,8));im=np.ma.masked_where(~valid,height);ax.imshow(im,cmap='viridis',extent=[bounds[0],bounds[1],bounds[2],bounds[3]],aspect='equal');ax.scatter(xyz[flags,0],xyz[flags,2],s=30,c='red')
    for point,level,ok in zip(xyz,LEVELS,flags):
        if ok:ax.text(point[0]+6,point[2],level,color='red')
    ax.set_title(subject+' / source body + projected CT bone proxy\n'+str(int(flags.sum()))+' valid levels / '+('qualified' if eligible else 'data failure'))
    ax.set_xlabel(('RAS' if world else 'Export')+' X mm');ax.set_ylabel(('RAS' if world else 'Export')+' Z mm');fig.tight_layout();(ROOT/'qualification_figures').mkdir(exist_ok=True);fig.savefig(ROOT/'qualification_figures'/(subject+'.png'),dpi=130);plt.close(fig)
    row=dict(subject=subject,role='external_TUM',eligible=bool(eligible),path=str(path),input_sha256=sha(path),target_valid=flags.tolist(),targets=targets,body_mesh_sha256=sha(base/'surfaces/body_surface.ply'),body_native_unit='m',bone_native_unit='mm',header_declared_unit=header['units'],unit_evidence='author Patient multiplies body by 1000; STL already mm. q/sform=0 cases use source unregistered positive-export extent, not nibabel fallback-world affine; unknown unit and orientation remain unvalidated',native_axes=header['axes'] if world else ['EXPORT_X','EXPORT_Y','EXPORT_Z'],coordinate_evidence='NATIVE_NIFTI_WORLD' if world else 'UNORIENTED_EXPORT_VOLUME_DIAGNOSTIC',native_world_validated=bool(world),body_inside_native_volume_fraction=float(inside.mean()),surface_valid_columns=int(valid.sum()),anatomical_label_order_pass=order,field_size_xz_mm=[bounds[1]-bounds[0],bounds[3]-bounds[2]],body_faces=len(faces),raster='exact triangle orthographic min source-frame Y at native NIfTI X/Z voxel center grid',reference_scope='posterior 2% of unique STL vertices (not bone voxels); same posterior-proxy concept, source tessellation differs from prior pilot',seconds=time.time()-start)
    print('source_qualified',subject,eligible,flags.tolist(),flush=True);return row

if __name__=='__main__':
    headers=json.loads((ROOT/'NATIVE_HEADERS.json').read_text());start=time.time()
    with ProcessPoolExecutor(max_workers=4) as pool:rows=list(pool.map(one,headers))
    write(ROOT/'CASE_MANIFEST.json',rows);write(ROOT/'DATA_SUMMARY.json',dict(all_cases=len(rows),qualified_cases=sum(x['eligible'] for x in rows),valid_level_counts=np.sum([x['target_valid'] for x in rows if x['eligible']],axis=0).tolist(),seconds=time.time()-start,unit_unknown_cases=[x['subject'] for x in rows if x['header_declared_unit']=='unknown']))
