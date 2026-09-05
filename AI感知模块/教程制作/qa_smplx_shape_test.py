"""Verify the doctor-facing height/weight and reset controls in SMPL-X."""

import sys
from pathlib import Path

import bpy


ai_root = Path(__file__).resolve().parents[1]
extension_parent = ai_root / "模型资源" / "SMPL-X" / "Blender扩展"
if str(extension_parent) not in sys.path:
    sys.path.insert(0, str(extension_parent))
import smplx_blender_addon

try:
    smplx_blender_addon.unregister()
except Exception:
    pass
smplx_blender_addon.register()


target = next(
    obj for obj in bpy.context.scene.objects
    if obj.type == "MESH" and obj.name.startswith("SMPLX-mesh-")
)
bpy.context.view_layer.objects.active = target
target.select_set(True)
assert hasattr(bpy.context.window_manager, "smplx_tool")
assert bpy.ops.object.smplx_measurements_to_shape.poll()

keys = target.data.shape_keys.key_blocks
before = [float(keys[f"Shape{i:03d}"].value) for i in range(10)]
tool = bpy.context.window_manager.smplx_tool
tool.smplx_height = 1.82
tool.smplx_weight = 82.0
result = bpy.ops.object.smplx_measurements_to_shape("EXEC_DEFAULT")
assert "FINISHED" in result
after = [float(keys[f"Shape{i:03d}"].value) for i in range(10)]
assert any(abs(a - b) > 1e-8 for a, b in zip(before, after))

result = bpy.ops.object.smplx_reset_shape("EXEC_DEFAULT")
assert "FINISHED" in result
assert all(abs(float(key.value)) < 1e-8 for key in keys if key.name.startswith("Shape"))

armature = target.parent
bone = armature.pose.bones.get("left_elbow")
assert bone is not None
bone.rotation_mode = "XYZ"
bone.rotation_euler.x = 0.2
assert abs(bone.rotation_euler.x) > 0
result = bpy.ops.object.smplx_reset_pose("EXEC_DEFAULT")
assert "FINISHED" in result
assert abs(bone.rotation_quaternion.angle) < 1e-8

print("SMPLX_HEIGHT_WEIGHT_AND_RESET=PASS")
print("BETAS_AFTER_MEASUREMENTS=" + ",".join(f"{value:.6f}" for value in after))
