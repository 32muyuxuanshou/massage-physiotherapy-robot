"""Enable the doctor add-ons in an isolated portable Blender profile."""

import bpy


MODULES = (
    "smpl_acupoint_annotator",
)

for module in MODULES:
    result = bpy.ops.preferences.addon_enable(module=module)
    if "FINISHED" not in result:
        raise RuntimeError(f"Could not enable Blender add-on: {module}: {result}")

bpy.ops.wm.save_userpref()
print("DOCTOR_PORTABLE_BLENDER_CONFIG=PASS")
