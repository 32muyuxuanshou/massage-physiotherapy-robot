"""Read-only probe for the user-reviewed DMD37 Blender asset."""

import hashlib
import json

import bpy


def topology_signature(mesh):
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update((",".join(str(int(v)) for v in polygon.vertices) + ";").encode("ascii"))
    return digest.hexdigest()


objects = []
for obj in bpy.data.objects:
    row = {"name": obj.name, "type": obj.type, "custom_keys": sorted(obj.keys())}
    if obj.type == "MESH":
        row.update(
            vertex_count=len(obj.data.vertices),
            polygon_count=len(obj.data.polygons),
            topology_signature_sha256=topology_signature(obj.data),
        )
    objects.append(row)

scene = bpy.context.scene
scene_values = {}
for key in (
    "DRAFT_NOTICE",
    "acupoint_atlas_family",
    "medical_warning",
    "skel_gender",
    "template_role",
    "topology_warning",
):
    value = scene.get(key)
    if isinstance(value, (str, int, float, bool)) or value is None:
        scene_values[key] = value
target = bpy.data.objects.get("SKEL-skin-male")
target_values = {}
if target is not None:
    for key in target.keys():
        value = target.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            target_values[key] = value
print(
    "TRACK_B_BLEND_PROBE="
    + json.dumps(
        {
            "scene_custom_keys": sorted(scene.keys()),
            "scene_values": scene_values,
            "target_values": target_values,
            "objects": objects,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
)
