"""Concrete cache format shared by the formal runner and the offline sanity."""
from pathlib import Path
import hashlib
import numpy as np
from data_v2 import save_json,load_json,sha,array_sha
from l1_fit import mesh_quality


def mesh_path(out,subject,seed,method):
    return Path(out)/'meshes'/subject/f'seed_{seed}'/(method.replace('+','_')+'.npz')


def historical_sample_indices(indices,n,key):
    if len(indices)<=n:return indices.copy()
    rng=np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:16],16))
    return indices[np.sort(rng.choice(len(indices),n,replace=False))]


def align_global(reference,target):
    """Remove one global rigid rotation before the normal-change diagnostic."""
    a=reference-reference.mean(0);b=target-target.mean(0)
    u,_,vt=np.linalg.svd(a.T@b);q=u@vt
    if np.linalg.det(q)<0:u[:,-1]*=-1;q=u@vt
    return a@q+target.mean(0)


def save_mesh(out,subject,seed,method,vertices,faces,quality_reference,optimization,
              state,source_status,**arrays):
    path=mesh_path(out,subject,seed,method);path.parent.mkdir(parents=True,exist_ok=True)
    split_path=Path(out)/'inputs'/subject/f'split_{seed}.npz'
    split=np.load(split_path,allow_pickle=False)
    opt_idx=np.asarray(arrays.pop('optimization_point_idx',[]),np.int64)
    assert np.isin(opt_idx,split['train_idx']).all()
    assert not np.intersect1d(opt_idx,split['heldout_idx']).size
    # Rigid and D cannot be represented by an MHR pose change. Keep the original
    # complete MHR state AND an explicit external transform/displacement.
    numeric_state={'mhr_'+k:np.asarray(v) for k,v in state.items()}
    arrays.setdefault('effective_cam_t_m',np.asarray(state['pred_cam_t']))
    np.savez_compressed(path,vertices_m=vertices,faces=faces,optimization_point_idx=opt_idx,
                        **numeric_state,**arrays)
    quality=mesh_quality(align_global(quality_reference,vertices),vertices,faces)
    quality['reference']='method input after best global rigid alignment; normal reversal proxy, not self-intersection proof'
    save_json(path.with_suffix('.json'),dict(subject=subject,seed=seed,method=method,
        source_status=source_status,mesh_sha256=sha(path),vertices_sha256=array_sha(vertices),
        faces_sha256=array_sha(faces.astype('<i8')),input_sha256=sha(Path(out)/'inputs'/subject/'input.npz'),
        split_sha256=sha(split_path),optimization=optimization,optimization_point_count=len(opt_idx),
        optimization_heldout_intersection=0,mesh_quality=quality))
    return path


def verify_cache(path,out,subject,seed):
    meta=load_json(path.with_suffix('.json'))
    assert sha(path)==meta['mesh_sha256']
    assert sha(Path(out)/'inputs'/subject/'input.npz')==meta['input_sha256']
    assert sha(Path(out)/'inputs'/subject/f'split_{seed}.npz')==meta['split_sha256']
    split=np.load(Path(out)/'inputs'/subject/f'split_{seed}.npz',allow_pickle=False)
    z=np.load(path,allow_pickle=False);indices=z['optimization_point_idx']
    assert np.isin(indices,split['train_idx']).all()
    assert not np.intersect1d(indices,split['heldout_idx']).size
    if 'pose_point_idx' in z:
        assert np.isin(z['pose_point_idx'],split['train_idx']).all()
        assert not np.intersect1d(z['pose_point_idx'],split['heldout_idx']).size
    return meta
