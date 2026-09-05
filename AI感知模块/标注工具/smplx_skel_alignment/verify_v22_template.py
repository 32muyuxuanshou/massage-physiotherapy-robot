"""Verify that a v2.2 SMPL-X template remains complete and adjustable."""

import argparse
import sys

import bpy


parser = argparse.ArgumentParser()
parser.add_argument("--gender", choices=("neutral", "female", "male"), required=True)
argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
args = parser.parse_args(argv)

meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and len(obj.data.vertices) == 10475]
if len(meshes) != 1:
    raise RuntimeError(f"Expected one SMPL-X mesh, got {len(meshes)}")
mesh = meshes[0]
if len(mesh.data.polygons) != 20908:
    raise RuntimeError("Unexpected SMPL-X triangle count")
keys = mesh.data.shape_keys.key_blocks if mesh.data.shape_keys else []
if len(keys) < 887:
    raise RuntimeError(f"Full adjustable shape keys missing: {len(keys)}")
if mesh.parent is None or mesh.parent.type != "ARMATURE":
    raise RuntimeError("SMPL-X armature missing")
if mesh.get("smplx_template_release") != "2.2.0":
    raise RuntimeError("v2.2 template identity missing")
if mesh.get("smplx_gender") != args.gender:
    raise RuntimeError("Template gender mismatch")
print(
    f"V22_TEMPLATE_VERIFY=PASS gender={args.gender} vertices={len(mesh.data.vertices)} "
    f"triangles={len(mesh.data.polygons)} shape_keys={len(keys)} armature={mesh.parent.name}"
)
