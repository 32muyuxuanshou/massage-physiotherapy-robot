"""Create a neutral SMPL annotation demo from the validated Blender scene."""

import os

import bpy
from mathutils import Vector

import smpl_acupoint_annotator as addon


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_BLEND = os.path.join(PROJECT_DIR, "SMPL背部穴位标注演示.blend")
OUTPUT_JSON = os.path.join(PROJECT_DIR, "示例标注_非医学.json")

scene = bpy.context.scene
target = bpy.data.objects["SMPL-mesh-female"]
scene.smpl_acupoint_settings.target_mesh = target

bpy.ops.object.select_all(action="DESELECT")
target.select_set(True)
bpy.context.view_layer.objects.active = target

if hasattr(bpy.ops.object, "smpl_reset_shapes"):
    bpy.ops.object.smpl_reset_shapes("EXEC_DEFAULT")
if hasattr(bpy.ops.object, "smpl_reset_pose"):
    bpy.ops.object.smpl_reset_pose("EXEC_DEFAULT")
if hasattr(bpy.ops.object, "smpl_update_joint_locations"):
    bpy.ops.object.smpl_update_joint_locations("EXEC_DEFAULT")
bpy.context.view_layer.update()

addon.clear_annotations(scene)
evaluated = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
hit, location, _normal, face_index = evaluated.ray_cast(
    Vector((0.0, 2.0, 0.2)), Vector((0.0, -1.0, 0.0))
)
if not hit:
    raise RuntimeError("Could not find a central back surface for the demo marker")

evaluated_mesh = evaluated.to_mesh()
try:
    polygon = evaluated_mesh.polygons[face_index]
    vertex_ids = tuple(polygon.vertices)
    a, b, c = (evaluated_mesh.vertices[index].co.copy() for index in vertex_ids)
    barycentric = addon._barycentric_weights(location, a, b, c)
finally:
    evaluated.to_mesh_clear()

addon.add_annotation_from_surface(
    scene,
    target,
    face_index,
    barycentric,
    code="DEMO-ONLY",
    name_zh="非医学示例点",
    meridian="仅用于验证工具",
    side="MIDLINE",
    notes="该点不代表任何穴位，正式位置必须由专业医生标注。",
    confidence=0.0,
)

addon.export_annotations(scene, OUTPUT_JSON)
bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)
print(f"DEMO_BLEND={OUTPUT_BLEND}")
print(f"DEMO_JSON={OUTPUT_JSON}")

