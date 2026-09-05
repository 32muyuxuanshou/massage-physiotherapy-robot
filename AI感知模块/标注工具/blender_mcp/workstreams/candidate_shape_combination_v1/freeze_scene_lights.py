"""Capture or apply the frozen baseline light contract inside Blender."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


def args():
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", type=Path)
    group.add_argument("--apply", type=Path)
    parser.add_argument("--save", type=Path)
    return parser.parse_args(values)


def rows(matrix):
    return [[float(value) for value in row] for row in matrix]


def main() -> None:
    options = args()
    lights = sorted((item for item in bpy.context.scene.objects if item.type == "LIGHT"), key=lambda item: item.name)
    if options.capture:
        payload = {
            "schema": "fixed-prone-light-contract-v1",
            "source_blend": str(Path(bpy.data.filepath).resolve()),
            "lights": [{
                "name": item.name, "type": item.data.type,
                "matrix_world": rows(item.matrix_world), "energy": float(item.data.energy),
                "color": [float(value) for value in item.data.color],
                "size": float(getattr(item.data, "size", 0.0)),
            } for item in lights],
        }
        options.capture.parent.mkdir(parents=True, exist_ok=True)
        options.capture.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        contract = json.loads(options.apply.read_text(encoding="utf-8-sig"))
        actual = {item.name: item for item in lights}
        expected = {item["name"] for item in contract["lights"]}
        if set(actual) != expected:
            raise RuntimeError(f"light set mismatch: actual={sorted(actual)}, expected={sorted(expected)}")
        for definition in contract["lights"]:
            item = actual[definition["name"]]
            if item.data.type != definition["type"]:
                raise RuntimeError(f"light type mismatch for {item.name}")
            item.matrix_world = Matrix(definition["matrix_world"])
            item.data.energy = float(definition["energy"])
            item.data.color = definition["color"]
            if hasattr(item.data, "size"):
                item.data.size = float(definition["size"])
        bpy.context.view_layer.update()
        if not options.save:
            raise ValueError("--save is required with --apply")
        bpy.ops.wm.save_as_mainfile(filepath=str(options.save.resolve()), check_existing=False)
    print("ACU_FIXED_SCENE_LIGHTS=PASS")


if __name__ == "__main__":
    main()
