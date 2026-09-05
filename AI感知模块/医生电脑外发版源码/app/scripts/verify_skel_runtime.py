"""Headless acceptance check for the portable SKEL pose-update pipeline."""

import argparse
import sys

import bpy


parser = argparse.ArgumentParser()
parser.add_argument("--gender", choices=("female", "male"), required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])

bpy.ops.preferences.addon_enable(module="smpl_acupoint_annotator")
bpy.ops.preferences.addon_enable(module="skel_blender_controls")
scene = bpy.context.scene
skin = bpy.data.objects.get(f"SKEL-skin-{args.gender}")
if skin is None:
    raise RuntimeError("SKEL skin mesh is missing")

before = [vertex.co.copy() for vertex in skin.data.vertices]
scene.skel_controls.lumbar_bending = 8.0
scene.skel_controls.thorax_twist = 5.0
result = bpy.ops.skel.update_skin("EXEC_DEFAULT")
if "FINISHED" not in result:
    raise RuntimeError(f"Portable SKEL update failed: {result}")

movement = max((vertex.co - start).length for vertex, start in zip(skin.data.vertices, before))
if movement <= 1e-8:
    raise RuntimeError("SKEL update completed but the skin did not move")
if scene.get("skel_parameters_dirty") is not False:
    raise RuntimeError("SKEL dirty state was not cleared")

print(f"DOCTOR_PORTABLE_SKEL_UPDATE=PASS gender={args.gender}")
print(f"MAX_VERTEX_MOVEMENT_M={movement:.9f}")
