"""Four provided marker coordinates define an engineering frame, not acupoints."""
import numpy as np

def reference_frame(markers_m):
    m = np.asarray(markers_m, float)[:4]
    longitudinal = m[1] - m[0]
    length = np.linalg.norm(longitudinal)
    if length < 1e-8:
        return None
    longitudinal /= length
    lateral = m[2] - m[3]
    lateral -= longitudinal * np.dot(lateral, longitudinal)
    if np.linalg.norm(lateral) < 1e-8:
        return None
    lateral /= np.linalg.norm(lateral)
    normal = np.cross(lateral, longitudinal)
    basis = np.column_stack([lateral, longitudinal, normal])
    return dict(origin_m=m[0], basis=basis, axis_length_m=length)

def local_coordinates(points_m, frame):
    return (points_m-frame['origin_m']) @ frame['basis']

def world_coordinates(points_local_m, frame):
    return points_local_m @ frame['basis'].T + frame['origin_m']
