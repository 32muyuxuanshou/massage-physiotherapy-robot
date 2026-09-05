"""One-pass global/2-ring/3-ring overlap and frozen-scene probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


TARGET = "SKEL-skin-female"
CAMERA = "ACU_PRONE_BACK_CAMERA"
BED = "ACU_PRONE_BED"


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--qa-root", required=True, type=Path)
    parser.add_argument("--epsilon", type=float, default=1e-7)
    return parser.parse_args(argv)


def rows(matrix):
    return [[float(value) for value in row] for row in matrix]


def material_contract(obj):
    materials = []
    for slot in obj.material_slots:
        material = slot.material
        record = {"name": material.name if material else None}
        if material and material.use_nodes:
            bsdf = material.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                record["base_color"] = [float(value) for value in bsdf.inputs["Base Color"].default_value]
                record["roughness"] = float(bsdf.inputs["Roughness"].default_value)
        materials.append(record)
    return materials


def main() -> None:
    args = arguments()
    sys.path.insert(0, str(args.qa_root.resolve()))
    from self_intersection_probe import (  # noqa: PLC0415
        anchor_neighborhood,
        evaluated_triangles,
        nonadjacent_overlaps,
    )

    atlas = json.loads(args.atlas.read_text(encoding="utf-8-sig"))
    scene = bpy.context.scene
    target = bpy.data.objects.get(TARGET)
    camera = bpy.data.objects.get(CAMERA)
    bed = bpy.data.objects.get(BED)
    if target is None or camera is None or bed is None:
        raise RuntimeError("frozen target/camera/bed scene is incomplete")

    vertices, triangles = evaluated_triangles(TARGET)
    overlaps, raw_count, adjacent_filtered = nonadjacent_overlaps(
        vertices, triangles, args.epsilon
    )
    anchor_faces = {int(item["face_index"]) for item in atlas["annotations"]}
    ring2 = anchor_neighborhood(triangles, anchor_faces, 2)
    ring3 = anchor_neighborhood(triangles, anchor_faces, 3)
    ring2_pairs = [pair for pair in overlaps if pair[0] in ring2 or pair[1] in ring2]
    ring3_pairs = [pair for pair in overlaps if pair[0] in ring3 or pair[1] in ring3]

    lights = []
    for item in sorted((obj for obj in scene.objects if obj.type == "LIGHT"), key=lambda obj: obj.name):
        lights.append(
            {
                "name": item.name,
                "type": item.data.type,
                "matrix_world": rows(item.matrix_world),
                "energy": float(item.data.energy),
                "color": [float(value) for value in item.data.color],
                "size": float(getattr(item.data, "size", 0.0)),
            }
        )

    payload = {
        "schema": "shape-pose-geometry-scene-probe-v1",
        "medical_truth": False,
        "medical_validated": False,
        "geometry": {
            "vertex_count": len(vertices),
            "triangle_count": len(triangles),
            "epsilon_m": args.epsilon,
            "raw_overlap_pair_count": raw_count,
            "adjacent_pair_count_filtered": adjacent_filtered,
            "global_nonadjacent_overlap_pair_count": len(overlaps),
            "global_nonadjacent_overlap_pairs": [list(pair) for pair in overlaps],
            "pair_list_complete": True,
            "anchor_face_count": len(anchor_faces),
            "ring2_face_count": len(ring2),
            "ring2_overlap_pair_count": len(ring2_pairs),
            "ring2_overlap_pairs": [list(pair) for pair in ring2_pairs],
            "ring3_face_count": len(ring3),
            "ring3_overlap_pair_count": len(ring3_pairs),
            "ring3_overlap_pairs": [list(pair) for pair in ring3_pairs],
        },
        "scene_contract": {
            "frame": int(scene.frame_current),
            "unit_system": scene.unit_settings.system,
            "unit_scale_length": float(scene.unit_settings.scale_length),
            "render_engine": scene.render.engine,
            "resolution": [int(scene.render.resolution_x), int(scene.render.resolution_y)],
            "pixel_aspect": [float(scene.render.pixel_aspect_x), float(scene.render.pixel_aspect_y)],
            "camera": {"name": camera.name, "matrix_world": rows(camera.matrix_world)},
            "bed": {"name": bed.name, "matrix_world": rows(bed.matrix_world), "materials": material_contract(bed)},
            "target": {"name": target.name, "matrix_world": rows(target.matrix_world), "materials": material_contract(target)},
            "lights": lights,
            "world_color": [float(value) for value in scene.world.color] if scene.world else None,
        },
        "limitations": [
            "Global pairs are diagnostic because the frozen baseline is not globally clear.",
            "Ring-2 is the target-local hard gate; ring-3 is a caution zone.",
            "This is triangle geometry QA, not physiological or soft-bed validation.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_SHAPE_POSE_GEOMETRY_SCENE_PROBE=PASS")


if __name__ == "__main__":
    main()
