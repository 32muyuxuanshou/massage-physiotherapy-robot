"""Deterministic rule-to-surface projection for the provisional back pipeline.

This module deliberately requires an explicit landmark frame.  It does not infer
vertebral levels from pixels and it does not return clinical confidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def _closest_point_triangle(point: np.ndarray, tri: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return closest point and barycentric coordinates (Ericson-style regions)."""
    a, b, c = tri
    ab, ac, ap = b - a, c - a, point - a
    d1, d2 = float(np.dot(ab, ap)), float(np.dot(ac, ap))
    if d1 <= 0.0 and d2 <= 0.0:
        return a.copy(), np.array([1.0, 0.0, 0.0])
    bp = point - b
    d3, d4 = float(np.dot(ab, bp)), float(np.dot(ac, bp))
    if d3 >= 0.0 and d4 <= d3:
        return b.copy(), np.array([0.0, 1.0, 0.0])
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return a + v * ab, np.array([1.0 - v, v, 0.0])
    cp = point - c
    d5, d6 = float(np.dot(ab, cp)), float(np.dot(ac, cp))
    if d6 >= 0.0 and d5 <= d6:
        return c.copy(), np.array([0.0, 0.0, 1.0])
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return a + w * ac, np.array([1.0 - w, 0.0, w])
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return b + w * (c - b), np.array([0.0, 1.0 - w, w])
    denom = 1.0 / (va + vb + vc)
    v, w = vb * denom, vc * denom
    return a + ab * v + ac * w, np.array([1.0 - v - w, v, w])


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise ValueError("zero-length landmark axis")
    return vector / norm


def load_mesh(vertices_path: Path, faces_path: Path) -> tuple[np.ndarray, np.ndarray]:
    vertices = np.asarray(np.load(vertices_path), dtype=np.float64)
    faces = np.asarray(np.load(faces_path), dtype=np.int64)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or faces.ndim != 2 or faces.shape[1] != 3:
        raise ValueError("mesh arrays must have shapes [N,3] and [F,3]")
    return vertices, faces


def project_rules(vertices: np.ndarray, faces: np.ndarray, posterior_face_ids: list[int], rules: list[dict[str, Any]], landmark_frame: dict[str, Any]) -> dict[str, Any]:
    levels = landmark_frame["levels"]
    candidate_ids = np.asarray(posterior_face_ids, dtype=np.int64)
    candidate_faces = faces[candidate_ids]
    results = []
    for rule in rules:
        level = rule["reference_level"]
        lm = levels[level]
        base = np.asarray(lm["point"], dtype=np.float64)
        lateral = _unit(np.asarray(lm["lateral_axis"], dtype=np.float64))
        native_per_b_cun = float(lm["native_per_b_cun"])
        side = {"left": -1.0, "right": 1.0, "midline": 0.0}[rule["laterality"]]
        target = base + side * float(rule["lateral_b_cun"]) * native_per_b_cun * lateral
        best_dist = float("inf")
        best = None
        for local_idx, face in enumerate(candidate_faces):
            tri = vertices[face]
            closest, bary = _closest_point_triangle(target, tri)
            dist = float(np.linalg.norm(closest - target))
            if dist < best_dist:
                best_dist = dist
                best = (int(candidate_ids[local_idx]), closest, bary, tri)
        if best is None:
            raise ValueError(f"no posterior faces available for {rule['id']}")
        face_id, point, bary, tri = best
        normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        normal = _unit(normal)
        results.append({
            "id": rule["id"], "name": rule["name"], "reference_level": level,
            "laterality": rule["laterality"], "lateral_b_cun": rule["lateral_b_cun"],
            "rule_target": target.tolist(), "surface_xyz": point.tolist(),
            "face_index": face_id, "barycentric": bary.tolist(),
            "surface_normal": normal.tolist(),
            "projection_distance_native": best_dist,
            "confidence": None, "confidence_status": "UNCALIBRATED_ENGINEERING_ONLY",
            "medical_truth": False, "provenance": "rule_engine_v1 + explicit_landmark_frame"
        })
    return {
        "schema": "RULE_ENGINE_OUTPUT_V1", "status": "ENGINEERING_PROXY",
        "medical_truth": False, "landmark_frame_status": landmark_frame["status"],
        "coordinate_frame": landmark_frame.get("coordinate_frame", "mesh_native"),
        "rules": results
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertices", type=Path, required=True)
    parser.add_argument("--faces", type=Path, required=True)
    parser.add_argument("--posterior-mask", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    vertices, faces = load_mesh(args.vertices, args.faces)
    mask = json.loads(args.posterior_mask.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    landmarks = json.loads(args.landmarks.read_text(encoding="utf-8"))
    output = project_rules(vertices, faces, mask["face_ids"], config["rules"], landmarks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
