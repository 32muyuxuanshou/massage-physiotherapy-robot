"""Evaluated-mesh surface binding sampling with strict mesh lifecycle handling."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import bpy
from mathutils import Vector


@dataclass(frozen=True)
class SurfaceSample:
    object_name: str
    face_index: int
    vertex_indices: tuple[int, int, int]
    barycentric: tuple[float, float, float]
    xyz_world_m: tuple[float, float, float]
    world_normal: tuple[float, float, float]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["vertex_indices"] = list(self.vertex_indices)
        payload["barycentric"] = list(self.barycentric)
        payload["xyz_world_m"] = list(self.xyz_world_m)
        payload["world_normal"] = list(self.world_normal)
        return payload


def _validated_barycentric(values: Sequence[float]) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError("barycentric must contain exactly three weights")
    weights = tuple(float(value) for value in values)
    if any(value < -1e-6 or value > 1.0 + 1e-6 for value in weights):
        raise ValueError(f"barycentric weights outside [0, 1]: {weights}")
    if abs(sum(weights) - 1.0) > 1e-5:
        raise ValueError(f"barycentric weights must sum to 1: {weights}")
    return weights


def sample_surface_binding(
    mesh_object: bpy.types.Object,
    face_index: int,
    barycentric: Sequence[float],
    *,
    depsgraph: bpy.types.Depsgraph,
    expected_vertex_indices: Sequence[int] | None = None,
) -> SurfaceSample:
    """Resolve a frozen face+barycentric binding on the current evaluated mesh.

    The evaluated mesh is always released in ``finally``.  The function rejects
    non-triangular polygons and optionally verifies the exact frozen vertex order.
    """

    if mesh_object.type != "MESH":
        raise ValueError("mesh_object must have type MESH")
    weights = _validated_barycentric(barycentric)
    face_index = int(face_index)
    evaluated = mesh_object.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        if face_index < 0 or face_index >= len(mesh.polygons):
            raise IndexError(f"face_index {face_index} outside evaluated mesh polygon range")
        polygon = mesh.polygons[face_index]
        vertex_indices = tuple(int(index) for index in polygon.vertices)
        if len(vertex_indices) != 3:
            raise ValueError(f"face {face_index} is not triangular: {vertex_indices}")
        if expected_vertex_indices is not None:
            expected = tuple(int(index) for index in expected_vertex_indices)
            if vertex_indices != expected:
                raise ValueError(
                    f"frozen topology mismatch for face {face_index}: {vertex_indices} != {expected}"
                )

        point_local = Vector((0.0, 0.0, 0.0))
        for weight, vertex_index in zip(weights, vertex_indices):
            vertex = mesh.vertices[vertex_index]
            point_local += weight * vertex.co
        # Keep the normal definition tied to the frozen triangle itself.  This
        # matches the annotator's face binding and remains independently
        # reproducible without depending on smooth-shading/custom-loop normals.
        normal_local = polygon.normal.copy()
        if normal_local.length_squared <= 1e-20:
            raise ValueError(f"evaluated face {face_index} has a degenerate normal")
        normal_local.normalize()

        point_world = evaluated.matrix_world @ point_local
        normal_matrix = evaluated.matrix_world.to_3x3().inverted_safe().transposed()
        normal_world = normal_matrix @ normal_local
        if normal_world.length_squared <= 1e-20:
            raise ValueError("evaluated world normal is degenerate")
        normal_world.normalize()
        return SurfaceSample(
            object_name=mesh_object.name,
            face_index=face_index,
            vertex_indices=vertex_indices,
            barycentric=weights,
            xyz_world_m=tuple(float(value) for value in point_world),
            world_normal=tuple(float(value) for value in normal_world),
        )
    finally:
        evaluated.to_mesh_clear()
