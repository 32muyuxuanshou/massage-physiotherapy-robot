"""Blender probe: retain BVH pairs, add exact metrics and spatial clusters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


TARGET = "SKEL-skin-female"


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--qa-root", required=True, type=Path)
    parser.add_argument("--epsilon", type=float, default=1e-7)
    parser.add_argument("--cluster-radius", type=float, default=0.025)
    return parser.parse_args(argv)


def evaluated_mesh(object_name: str):
    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "MESH":
        raise RuntimeError(f"Mesh object not found: {object_name}")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        mesh.calc_loop_triangles()
        local = np.asarray([tuple(vertex.co) for vertex in mesh.vertices], dtype=np.float64)
        matrix = evaluated.matrix_world.copy()
        world = np.asarray([tuple(matrix @ vertex.co) for vertex in mesh.vertices], dtype=np.float64)
        triangles = np.asarray([tuple(triangle.vertices) for triangle in mesh.loop_triangles], dtype=np.int64)
    finally:
        evaluated.to_mesh_clear()
    return obj, matrix, local, world, triangles


def region(point: np.ndarray, minimum: np.ndarray, maximum: np.ndarray) -> tuple[str, float]:
    height = max(float(maximum[1] - minimum[1]), 1e-12)
    normalized_y = float((point[1] - minimum[1]) / height)
    lateral = abs(float(point[0]))
    if normalized_y >= 0.86:
        name = "HEAD_NECK"
    elif normalized_y >= 0.67:
        name = "UPPER_LIMB_SHOULDER" if lateral >= 0.17 else "SHOULDER_UPPER_TORSO"
    elif normalized_y >= 0.48:
        name = "UPPER_LIMB_LOWER" if lateral >= 0.17 else "MID_LOWER_TORSO"
    elif normalized_y >= 0.38:
        name = "PELVIS"
    elif normalized_y >= 0.20:
        name = "UPPER_LEG"
    else:
        name = "LOWER_LEG_FOOT"
    return name, normalized_y


class UnionFind:
    def __init__(self, count: int):
        self.parent = list(range(count))

    def find(self, index: int) -> int:
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, first: int, second: int) -> None:
        a, b = self.find(first), self.find(second)
        if a != b:
            self.parent[b] = a


def build_clusters(records: list[dict], radius: float) -> list[dict]:
    if not records:
        return []
    union = UnionFind(len(records))
    face_sets = [{record["faces"][0], record["faces"][1]} for record in records]
    centers = [np.asarray(record["midpoint_world_m"], dtype=np.float64) for record in records]
    for first in range(len(records)):
        for second in range(first + 1, len(records)):
            shared_face = bool(face_sets[first].intersection(face_sets[second]))
            spatial = records[first]["coarse_region"] == records[second]["coarse_region"] and float(np.linalg.norm(centers[first] - centers[second])) <= radius
            if shared_face or spatial:
                union.union(first, second)
    groups: dict[int, list[int]] = {}
    for index in range(len(records)):
        groups.setdefault(union.find(index), []).append(index)

    clusters = []
    for cluster_index, indices in enumerate(sorted(groups.values(), key=lambda values: min(values)), start=1):
        items = [records[index] for index in indices]
        all_points = [np.asarray(point, dtype=np.float64) for item in items for point in item["intersection_points_world_m"]]
        if not all_points:
            all_points = [np.asarray(item["midpoint_world_m"], dtype=np.float64) for item in items]
        points = np.asarray(all_points)
        local_centers = np.asarray([item["midpoint_local_m"] for item in items], dtype=np.float64)
        faces = sorted({face for item in items for face in item["faces"]})
        region_counts: dict[str, int] = {}
        for item in items:
            region_counts[item["coarse_region"]] = region_counts.get(item["coarse_region"], 0) + 1
        dominant_region = max(region_counts, key=region_counts.get)
        clusters.append({
            "cluster_id": f"CL{cluster_index:03d}",
            "confirmed_pair_count": len(items),
            "pairs": [item["faces"] for item in items],
            "face_indices": faces,
            "center_world_m": points.mean(axis=0).tolist(),
            "center_local_m": local_centers.mean(axis=0).tolist(),
            "bbox_world_min_m": points.min(axis=0).tolist(),
            "bbox_world_max_m": points.max(axis=0).tolist(),
            "coarse_region": dominant_region,
            "region_counts": region_counts,
            "intersects_ring2": any(item["intersects_ring2"] for item in items),
            "intersects_ring3": any(item["intersects_ring3"] for item in items),
            "noncoplanar_pair_count": sum(item["classification"] == "NONCOPLANAR_SEGMENT" for item in items),
            "coplanar_pair_count": sum(item["classification"] == "COPLANAR_AREA" for item in items),
            "total_segment_length_m": float(sum(item["intersection_segment_length_m"] for item in items)),
            "max_segment_length_m": float(max(item["intersection_segment_length_m"] for item in items)),
            "total_coplanar_area_m2": float(sum(item["coplanar_intersection_area_m2"] for item in items)),
            "max_crossing_depth_proxy_m": float(max(max(item["crossing_depth_proxy_a_m"], item["crossing_depth_proxy_b_m"]) for item in items)),
            "max_centroid_distance_m": float(max(item["triangle_centroid_distance_m"] for item in items)),
        })
    return clusters


def main() -> None:
    args = arguments()
    sys.path.insert(0, str(args.qa_root.resolve()))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from self_intersection_probe import anchor_neighborhood, nonadjacent_overlaps  # noqa: PLC0415
    from triangle_narrow_phase import analyze_triangle_pair  # noqa: PLC0415

    atlas = json.loads(args.atlas.read_text(encoding="utf-8-sig"))
    obj, matrix, local_vertices, world_vertices, triangles = evaluated_mesh(TARGET)
    overlaps, raw_count, adjacent_filtered = nonadjacent_overlaps(
        [tuple(vertex) for vertex in world_vertices], [tuple(int(value) for value in triangle) for triangle in triangles], args.epsilon
    )
    anchor_faces = {int(item["face_index"]) for item in atlas["annotations"]}
    triangle_rows = [tuple(int(value) for value in triangle) for triangle in triangles]
    ring2 = anchor_neighborhood(triangle_rows, anchor_faces, 2)
    ring3 = anchor_neighborhood(triangle_rows, anchor_faces, 3)
    minimum, maximum = local_vertices.min(axis=0), local_vertices.max(axis=0)
    inverse = matrix.inverted()

    pair_records = []
    classification_counts: dict[str, int] = {}
    for first, second in overlaps:
        world_a, world_b = world_vertices[triangles[first]], world_vertices[triangles[second]]
        local_a, local_b = local_vertices[triangles[first]], local_vertices[triangles[second]]
        result = analyze_triangle_pair(world_a, world_b, args.epsilon)
        classification_counts[result.classification] = classification_counts.get(result.classification, 0) + 1
        centroid_world_a, centroid_world_b = world_a.mean(axis=0), world_b.mean(axis=0)
        if result.points:
            midpoint_world = np.asarray(result.points, dtype=np.float64).mean(axis=0)
        else:
            midpoint_world = (centroid_world_a + centroid_world_b) * 0.5
        midpoint_local = np.asarray(tuple(inverse @ Vector(tuple(midpoint_world))), dtype=np.float64)
        region_name, normalized_y = region(midpoint_local, minimum, maximum)
        record = {
            "faces": [int(first), int(second)],
            **result.as_dict(),
            "triangle_centroid_a_world_m": centroid_world_a.tolist(),
            "triangle_centroid_b_world_m": centroid_world_b.tolist(),
            "triangle_centroid_distance_m": float(np.linalg.norm(centroid_world_a - centroid_world_b)),
            "midpoint_world_m": midpoint_world.tolist(),
            "midpoint_local_m": midpoint_local.tolist(),
            "coarse_region": region_name,
            "normalized_height": normalized_y,
            "intersects_ring2": first in ring2 or second in ring2,
            "intersects_ring3": first in ring3 or second in ring3,
            "triangle_area_a_m2": float(np.linalg.norm(np.cross(world_a[1] - world_a[0], world_a[2] - world_a[0])) * 0.5),
            "triangle_area_b_m2": float(np.linalg.norm(np.cross(world_b[1] - world_b[0], world_b[2] - world_b[0])) * 0.5),
        }
        pair_records.append(record)

    confirmed = [record for record in pair_records if record["confirmed_overlap"]]
    contacts = [record for record in pair_records if record["contact_only"]]
    unconfirmed = [record for record in pair_records if not record["confirmed_overlap"] and not record["contact_only"]]
    clusters = build_clusters(confirmed, args.cluster_radius)
    payload = {
        "schema": "skel-overlap-narrow-phase-cluster-v1",
        "medical_truth": False,
        "medical_validated": False,
        "object_name": obj.name,
        "vertex_count": int(len(local_vertices)),
        "triangle_count": int(len(triangles)),
        "epsilon_m": args.epsilon,
        "cluster_radius_m": args.cluster_radius,
        "object_matrix_world": [[float(value) for value in row] for row in matrix],
        "body_local_bounds_m": {"minimum": minimum.tolist(), "maximum": maximum.tolist()},
        "bvh": {
            "raw_pair_count": raw_count,
            "adjacent_pair_count_filtered": adjacent_filtered,
            "nonadjacent_candidate_pair_count": len(overlaps),
            "candidate_pairs": [list(pair) for pair in overlaps],
        },
        "narrow_phase": {
            "classification_counts": classification_counts,
            "confirmed_overlap_pair_count": len(confirmed),
            "contact_only_pair_count": len(contacts),
            "unconfirmed_candidate_pair_count": len(unconfirmed),
            "confirmed_ring2_pair_count": sum(record["intersects_ring2"] for record in confirmed),
            "confirmed_ring3_pair_count": sum(record["intersects_ring3"] for record in confirmed),
            "confirmed_pairs": confirmed,
            "contact_only_pairs": contacts,
            "unconfirmed_pairs": unconfirmed,
        },
        "clusters": clusters,
        "cluster_count": len(clusters),
        "limitations": [
            "BVH pairs remain the raw first-layer evidence.",
            "Narrow-phase segment/area metrics are deterministic geometric proxies, not physical soft-tissue penetration depth.",
            "Point-only contact is reported separately and is not promoted to confirmed overlap by this probe.",
            "Coarse body regions and spatial clusters are QA aids, not medical anatomy labels.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_NARROW_PHASE_CLUSTER_PROBE=PASS")


if __name__ == "__main__":
    main()
