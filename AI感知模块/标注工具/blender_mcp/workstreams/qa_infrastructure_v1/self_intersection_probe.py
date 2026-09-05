from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


SCHEMA = "bvh-nonadjacent-triangle-overlap-v1"


def evaluated_triangles(object_name: str):
    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "MESH":
        raise RuntimeError(f"Mesh object not found: {object_name}")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        mesh.calc_loop_triangles()
        matrix = evaluated.matrix_world
        vertices = [tuple(matrix @ vertex.co) for vertex in mesh.vertices]
        triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
    finally:
        evaluated.to_mesh_clear()
    return vertices, triangles


def nonadjacent_overlaps(vertices, triangles, epsilon: float):
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True, epsilon=epsilon)
    raw_pairs = tree.overlap(tree)
    unique_pairs = set()
    adjacent_filtered = 0
    for first, second in raw_pairs:
        if first >= second:
            continue
        first_vertices = set(triangles[first])
        second_vertices = set(triangles[second])
        if first_vertices.intersection(second_vertices):
            adjacent_filtered += 1
            continue
        unique_pairs.add((first, second))
    return sorted(unique_pairs), len(raw_pairs), adjacent_filtered


def anchor_neighborhood(triangles, anchor_faces: set[int], rings: int) -> set[int]:
    vertex_to_faces: dict[int, set[int]] = {}
    for face_index, triangle in enumerate(triangles):
        for vertex_index in triangle:
            vertex_to_faces.setdefault(vertex_index, set()).add(face_index)
    neighborhood = set(anchor_faces)
    frontier = set(anchor_faces)
    for _ in range(rings):
        expanded: set[int] = set()
        for face_index in frontier:
            for vertex_index in triangles[face_index]:
                expanded.update(vertex_to_faces[vertex_index])
        frontier = expanded - neighborhood
        neighborhood.update(expanded)
    return neighborhood


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--object", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epsilon", type=float, default=1e-7)
    parser.add_argument("--max-pairs", type=int, default=200)
    parser.add_argument("--anchor-atlas", type=Path)
    parser.add_argument("--anchor-rings", type=int, default=2)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    vertices, triangles = evaluated_triangles(args.object)
    overlaps, raw_pair_count, adjacent_filtered = nonadjacent_overlaps(
        vertices, triangles, args.epsilon
    )
    anchor_faces: set[int] = set()
    neighborhood: set[int] = set()
    anchor_overlap_pairs = []
    if args.anchor_atlas:
        atlas = json.loads(args.anchor_atlas.read_text(encoding="utf-8-sig"))
        anchor_faces = {int(item["face_index"]) for item in atlas["annotations"]}
        if any(index < 0 or index >= len(triangles) for index in anchor_faces):
            raise RuntimeError("Atlas face_index is outside evaluated triangle range")
        neighborhood = anchor_neighborhood(triangles, anchor_faces, args.anchor_rings)
        anchor_overlap_pairs = [
            pair for pair in overlaps if pair[0] in neighborhood or pair[1] in neighborhood
        ]

    if not overlaps:
        status = "GLOBAL_CLEAR"
    elif args.anchor_atlas and not anchor_overlap_pairs:
        status = "KNOWN_GLOBAL_OVERLAPS_OUTSIDE_ANCHOR_NEIGHBORHOOD"
    elif args.anchor_atlas:
        status = "ANCHOR_NEIGHBORHOOD_OVERLAP"
    else:
        status = "GLOBAL_OVERLAPS_UNSCOPED"

    scoped_pass = not anchor_overlap_pairs if args.anchor_atlas else not overlaps
    report = {
        "schema": SCHEMA,
        "passed": scoped_pass,
        "status": status,
        "global_self_intersection_clear": not overlaps,
        "object_name": args.object,
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
        "epsilon_m": args.epsilon,
        "raw_overlap_pair_count": raw_pair_count,
        "adjacent_pair_count_filtered": adjacent_filtered,
        "nonadjacent_intersection_pair_count": len(overlaps),
        "nonadjacent_intersection_pairs_truncated": [list(pair) for pair in overlaps[: args.max_pairs]],
        "pair_list_truncated": len(overlaps) > args.max_pairs,
        "anchor_scope": {
            "enabled": bool(args.anchor_atlas),
            "atlas_path": str(args.anchor_atlas) if args.anchor_atlas else None,
            "anchor_face_count": len(anchor_faces),
            "neighborhood_rings": args.anchor_rings if args.anchor_atlas else None,
            "neighborhood_face_count": len(neighborhood),
            "overlap_pair_count": len(anchor_overlap_pairs),
            "overlap_pairs_truncated": [list(pair) for pair in anchor_overlap_pairs[: args.max_pairs]],
        },
        "limitations": [
            "This checks evaluated triangle geometry in world coordinates.",
            "Triangles sharing any vertex are excluded as normal mesh adjacency.",
            "The predicate is a geometry QA gate, not soft-tissue or physiological plausibility.",
            "When an anchor Atlas is supplied, passed only means its frozen N-ring surface neighborhood is clear; global overlaps remain separately reported.",
            "A nonzero global count in the frozen baseline prevents any claim that the complete body mesh is self-intersection-free.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
