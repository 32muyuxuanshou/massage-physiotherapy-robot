"""Nonnegative graph-distance reference blending on a fixed Mesh."""
import sys
from pathlib import Path
import numpy as np
PARENT=Path('/raid5/xuhd/datasets/back_reference_assisted_v1_20261004')
sys.path.insert(0,str(PARENT/'code'))
from correspondence import graph_distances,surface_project


def convex_weights(distances,distance_floor_m=.001):
    d=np.asarray(distances,float).T
    weight=np.maximum(d,distance_floor_m)**-2
    weight/=weight.sum(axis=1,keepdims=True)
    for i in np.flatnonzero((d<=1e-10).any(axis=1)):
        weight[i]=0.;weight[i,np.argmin(d[i])]=1.
    return weight


def estimate(V,F,records,input_indices,input_xyz,face_ids):
    P,distance=graph_distances(V,F,records,input_indices)
    weight=convex_weights(distance)
    offset=weight@(input_xyz-P[input_indices])
    result=surface_project(P+offset,V,F,face_ids)
    result.update(preprojection_xyz_m=P+offset,interpolated_offset_m=offset,
        reference_weights=weight,graph_distance_m=distance)
    return result
