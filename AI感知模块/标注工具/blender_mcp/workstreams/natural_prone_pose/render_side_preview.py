"""Render a diagnostic side view without saving the source Blend."""

from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector


def main() -> None:
    if "--" not in sys.argv:
        raise RuntimeError("output path required")
    output = Path(sys.argv[sys.argv.index("--") + 1])
    target = bpy.data.objects.get("SKEL-skin-female")
    camera = bpy.data.objects.get("ACU_PRONE_BACK_CAMERA")
    if target is None or camera is None:
        raise RuntimeError("target or camera missing")
    scene = bpy.context.scene
    camera.location = Vector((1.75, -0.2915360629558563, 0.23))
    aim = Vector((0.0, -0.2915360629558563, 0.13))
    camera.rotation_euler = ((aim - camera.location).to_track_quat("-Z", "Y")).to_euler()
    camera.data.lens = 58.0
    scene.camera = camera
    scene.render.resolution_x = 960
    scene.render.resolution_y = 420
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    print("ACU_NATURAL_PRONE_SIDE_PREVIEW=PASS")


if __name__ == "__main__":
    main()
