"""Frozen nonlearned translation operators, with their differences explicit."""
import numpy as np
from scipy.spatial import cKDTree
from common import CFG


def update(residual,normals,kind,distance=None):
    if not len(residual):return np.zeros(3),dict(count=0,rank=0)
    if distance is None:distance=np.linalg.norm(residual,axis=1)
    keep=distance<=np.quantile(distance,.8)
    r=residual[keep];n=normals[keep]
    if kind=='median':step=np.median(r,axis=0)
    elif kind=='mean':step=np.mean(r,axis=0)
    else:
        # n dot (delta-r)=0, not a weighted XYZ centroid.
        step=np.linalg.lstsq(n,np.einsum('ij,ij->i',n,r),rcond=1e-6)[0]
        if kind=='plane_gate':
            matrix=n.T@n/len(n);ev,axes=np.linalg.eigh(matrix)
            step=axes@((ev.clip(0)/(ev.clip(0)+.01))*(axes.T@step))
    ev=np.linalg.eigvalsh(n.T@n/len(n))
    return np.clip(step,-.05,.05),dict(count=len(r),normal_eigenvalues=ev.tolist(),rank=int(np.sum(ev>ev.max()*1e-12)),euclidean_median_m=float(np.median(distance)))


def finish(raw):
    fallback=bool(np.linalg.norm(raw)>.17788820176363325)
    return np.zeros(3) if fallback else raw.copy(),fallback


def nn_path(points,anchors,normals,steps=6,direction='o2m',kind='median'):
    t=np.zeros(3);trace=[];point_tree=cKDTree(points) if direction=='m2o' else None
    for i in range(steps):
        if direction=='o2m':
            distance,near=cKDTree(anchors+t).query(points,workers=1)
            residual=points-(anchors+t)[near];n=normals[near]
        else:
            distance,near=point_tree.query(anchors+t,workers=1)
            residual=points[near]-(anchors+t);n=normals
        step,stats=update(residual,n,kind,distance);t+=step
        trace.append(dict(iteration=i+1,step_m=step.tolist(),raw_t_m=t.tolist(),**stats))
    return t,trace


def fixed_update(residual,normals,kind='median'):
    step,stats=update(residual,normals,kind)
    return step,[dict(iteration=1,step_m=step.tolist(),raw_t_m=step.tolist(),**stats)]
