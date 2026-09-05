"""Render a canonical rear-view QC image with E01-E20 markers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def material(name, color, emission=0.0):
    value = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    value.diffuse_color = color
    value.use_nodes = True
    bsdf = value.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.65
    if emission:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = emission
    return value


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) != 2:
        raise ValueError("expected atlas and output paths")
    atlas_path, output = map(Path, argv)
    atlas = json.loads(atlas_path.read_text(encoding="utf-8-sig"))
    scene = bpy.context.scene
    target = bpy.data.objects.get("SKEL-skin-female")
    if target is None:
        raise RuntimeError("canonical target missing")
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.025, 0.025, 0.025)
    target.data.materials.clear()
    target.data.materials.append(material("ENG_ATLAS_SKIN", (0.22, 0.07, 0.035, 1.0)))
    data = bpy.data.cameras.new("ENG_ATLAS_CAMERA_DATA")
    data.lens = 68.0
    camera = bpy.data.objects.new("ENG_ATLAS_CAMERA", data)
    scene.collection.objects.link(camera)
    camera.location = Vector((0.0, 2.45, -0.02))
    aim = Vector((0.0, 0.0, 0.03))
    camera.rotation_euler = (aim - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    for name, location, energy, size in (("KEY", (-0.65, 1.5, 0.65), 360.0, 1.8), ("FILL", (0.75, 1.2, -0.2), 160.0, 1.4)):
        light_data = bpy.data.lights.new(f"ENG_ATLAS_{name}_DATA", "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = size
        light = bpy.data.objects.new(f"ENG_ATLAS_{name}", light_data)
        scene.collection.objects.link(light)
        light.location = Vector(location)
        light.rotation_euler = (aim - light.location).to_track_quat("-Z", "Y").to_euler()
    marker_mat = material("ENG_ATLAS_MARKER", (0.02, 1.0, 0.16, 1.0), emission=2.5)
    text_mat = material("ENG_ATLAS_TEXT", (0.005, 0.005, 0.005, 1.0))
    for item in atlas["anchors"]:
        local_point = Vector(item["xyz_local_m"])
        local_normal = Vector(item["normal_local"])
        world_point = target.matrix_world @ local_point
        world_normal = (target.matrix_world.to_3x3() @ local_normal).normalized()
        location = world_point + world_normal * 0.006
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.007, location=location)
        bpy.context.object.data.materials.append(marker_mat)
        bpy.ops.object.text_add(location=location + Vector((0.010, 0.005, 0.004)))
        text = bpy.context.object
        text.data.body = item["code"]
        text.data.size = 0.020
        text.data.extrude = 0.0005
        text.data.materials.append(text_mat)
        text.rotation_euler = (camera.location - text.location).to_track_quat("Z", "Y").to_euler()
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    print("ACU_RENDER_ENG_BACK20=PASS")


if __name__ == "__main__":
    main()
