"""Read-only probe of the canonical female SKEL scene."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    output = Path(argv[0])
    target = bpy.data.objects.get("SKEL-skin-female")
    if target is None:
        raise RuntimeError("SKEL-skin-female not found")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        coords = [vertex.co.copy() for vertex in mesh.vertices]
        payload = {
            "target": target.name,
            "matrix_world": [[float(value) for value in row] for row in target.matrix_world],
            "bounds_local": {
                "min": [min(float(point[i]) for point in coords) for i in range(3)],
                "max": [max(float(point[i]) for point in coords) for i in range(3)],
            },
            "vertex_count": len(mesh.vertices),
            "polygon_count": len(mesh.polygons),
            "modifiers": [modifier.type for modifier in target.modifiers],
            "parent": target.parent.name if target.parent else None,
            "objects": [
                {
                    "name": obj.name,
                    "type": obj.type,
                    "parent": obj.parent.name if obj.parent else None,
                    "role": str(obj.get("skel_role") or ""),
                    "hide_render": bool(obj.hide_render),
                }
                for obj in bpy.context.scene.objects
            ],
        }
    finally:
        evaluated.to_mesh_clear()
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ACU_INSPECT_CANONICAL=PASS")


if __name__ == "__main__":
    main()
