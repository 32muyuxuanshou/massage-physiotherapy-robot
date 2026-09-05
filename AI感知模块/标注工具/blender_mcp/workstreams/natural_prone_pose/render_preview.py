"""Render a low-resolution visual probe from a prepared prone snapshot."""

from __future__ import annotations

import sys
from pathlib import Path

import bpy


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    output = Path(argv[0])
    scene = bpy.context.scene
    scene.render.resolution_x = 640
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    print("ACU_NATURAL_PRONE_PREVIEW=PASS")


if __name__ == "__main__":
    main()
