"""Rigid-equivariant frame from two supplied references and posterior direction.

No anatomical grade is inferred by this module. Caller supplies semantic T3/L2
slots and an outward posterior direction in its native physical coordinates.
"""
import numpy as np


def make_frame(references, posterior_direction, native_to_mm):
    references = np.asarray(references, dtype=np.float64) * native_to_mm
    down = references[1]-references[0]
    length = np.linalg.norm(down)
    assert length > 0, 'COINCIDENT_REFERENCE_INPUTS'
    down /= length
    posterior = np.array(posterior_direction, dtype=np.float64, copy=True)
    posterior -= np.dot(posterior, down)*down
    assert np.linalg.norm(posterior) > 1e-8, 'POSTERIOR_DIRECTION_PARALLEL_TO_AXIS'
    posterior /= np.linalg.norm(posterior)
    right = np.cross(posterior, down)
    basis = np.column_stack([right, posterior, down])
    return dict(origin_mm=references[0], basis=basis,
                reference_length_mm=float(length), native_to_mm=float(native_to_mm))


def to_local(points, frame):
    return ((np.asarray(points)*frame['native_to_mm']-frame['origin_mm']) @ frame['basis'])/500.


def from_local(points, frame):
    return (np.asarray(points)*500. @ frame['basis'].T + frame['origin_mm'])/frame['native_to_mm']


def direction_to_local(directions, frame):
    return np.asarray(directions) @ frame['basis']


def serializable(frame):
    return {k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in frame.items()}
