"""Export the evaluated SMPL-X surface for the external SKEL fitter."""

from __future__ import annotations

import argparse
import os
import sys

import bpy
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def blender_to_skel_raw(value):
    """Blender Z-up -> SKEL/OpenSim Y-up coordinates."""
    return (float(value.x), float(value.z), -float(value.y))


def main() -> None:
    args = parse_args()
    scene = bpy.context.scene
    settings = getattr(scene, "smpl_acupoint_settings", None)
    target = settings.target_mesh if settings and settings.target_mesh else None
    if target is None or target.type != "MESH" or len(target.data.vertices) != 10475:
        candidates = [
            obj
            for obj in bpy.data.objects
            if obj.type == "MESH" and len(obj.data.vertices) == 10475
        ]
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one SMPL-X mesh, got {len(candidates)}")
        target = candidates[0]

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    vertices = np.asarray(
        [blender_to_skel_raw(target.matrix_world @ vertex.co) for vertex in evaluated.data.vertices],
        dtype=np.float32,
    )
    faces = np.asarray(
        [tuple(polygon.vertices) for polygon in target.data.polygons], dtype=np.int32
    )
    if vertices.shape != (10475, 3) or faces.shape[1] != 3:
        raise RuntimeError(f"Unexpected SMPL-X topology: vertices={vertices.shape}, faces={faces.shape}")

    output = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    np.savez_compressed(
        output,
        vertices=vertices,
        faces=faces,
        target_name=target.name,
        gender=str(target.get("gender", scene.get("smplx_gender", "unknown"))),
    )
    print("SMPLX_SKEL_TARGET_EXPORT=PASS")
    print(f"OUTPUT={output}")
    print(f"TARGET={target.name}")
    print(f"VERTICES={len(vertices)}")
    print(f"FACES={len(faces)}")


main()
