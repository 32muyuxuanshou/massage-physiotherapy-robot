"""Freeze reproducible body-local measurement vertex sets from beta-zero SKEL.

Run inside Blender on the frozen natural-prone beta-zero snapshot.  The
contract deliberately uses the SKEL skin object's local frame, so the rigid
prone placement cannot leak into anthropometric proxies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


TARGET = "SKEL-skin-female"
EXPECTED_TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(values)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def topology_signature(mesh) -> str:
    digest = hashlib.sha256()
    digest.update(f"v={len(mesh.vertices)};p={len(mesh.polygons)};".encode("ascii"))
    for polygon in mesh.polygons:
        digest.update((",".join(str(int(v)) for v in polygon.vertices) + ";").encode("ascii"))
    return digest.hexdigest()


def point_local(mesh, annotation: dict) -> Vector:
    face = mesh.polygons[int(annotation["face_index"])]
    actual = [int(v) for v in face.vertices]
    expected = [int(v) for v in annotation["vertex_indices"]]
    if actual != expected:
        raise ValueError(f"Atlas topology mismatch for {annotation['point_id']}")
    weights = [float(v) for v in annotation["barycentric"]]
    return sum((mesh.vertices[index].co * weight for index, weight in zip(actual, weights)), Vector())


def main() -> None:
    args = arguments()
    atlas = read_json(args.atlas)
    target = bpy.data.objects.get(TARGET)
    if target is None or target.type != "MESH":
        raise RuntimeError(f"missing {TARGET}")
    if topology_signature(target.data) != EXPECTED_TOPOLOGY:
        raise RuntimeError("unexpected SKEL topology")
    annotations = {item["point_id"]: item for item in atlas["annotations"]}
    required = {
        "GB21_LEFT", "GB21_RIGHT", "BL13_LEFT", "BL13_RIGHT",
        "BL20_LEFT", "BL20_RIGHT", "BL23_LEFT", "BL23_RIGHT",
        "BL28_LEFT", "BL28_RIGHT",
    }
    missing = required - set(annotations)
    if missing:
        raise ValueError(f"Atlas lacks measurement reference points: {sorted(missing)}")

    mesh = target.data
    points = {point_id: point_local(mesh, annotations[point_id]) for point_id in required}
    vertices = [vertex.co.copy() for vertex in mesh.vertices]

    def level(left: str, right: str) -> float:
        return float((points[left].y + points[right].y) * 0.5)

    definitions = {
        "shoulder_width": {
            "axis": "body_left_right_x",
            "level_y_m": level("GB21_LEFT", "GB21_RIGHT"),
            "half_slab_m": 0.020,
            "max_abs_x_m": 0.36,
            "reference_points": ["GB21_LEFT", "GB21_RIGHT"],
        },
        "upper_torso_width": {
            "axis": "body_left_right_x",
            "level_y_m": level("BL13_LEFT", "BL13_RIGHT"),
            "half_slab_m": 0.018,
            "max_abs_x_m": 0.30,
            "reference_points": ["BL13_LEFT", "BL13_RIGHT"],
        },
        "lower_torso_width": {
            "axis": "body_left_right_x",
            "level_y_m": level("BL23_LEFT", "BL23_RIGHT"),
            "half_slab_m": 0.018,
            "max_abs_x_m": 0.32,
            "reference_points": ["BL23_LEFT", "BL23_RIGHT"],
        },
        "torso_thickness": {
            "axis": "body_ventral_dorsal_z",
            "level_y_m": level("BL20_LEFT", "BL20_RIGHT"),
            "half_slab_m": 0.018,
            "max_abs_x_m": 0.24,
            "reference_points": ["BL20_LEFT", "BL20_RIGHT"],
        },
        "pelvis_width": {
            "axis": "body_left_right_x",
            "level_y_m": level("BL28_LEFT", "BL28_RIGHT"),
            "half_slab_m": 0.020,
            "max_abs_x_m": 0.36,
            "reference_points": ["BL28_LEFT", "BL28_RIGHT"],
        },
    }
    for name, definition in definitions.items():
        indices = [
            index for index, coordinate in enumerate(vertices)
            if abs(float(coordinate.y) - definition["level_y_m"]) <= definition["half_slab_m"]
            and abs(float(coordinate.x)) <= definition["max_abs_x_m"]
        ]
        if len(indices) < 20:
            raise RuntimeError(f"measurement slice {name} contains only {len(indices)} vertices")
        definition["frozen_vertex_indices"] = indices
        definition["vertex_count"] = len(indices)
        definition["method"] = "extent of a beta-zero frozen vertex set; vertices are never reselected"

    payload = {
        "schema": "skel-body-measurement-contract-v1",
        "medical_truth": False,
        "template": "SKEL_FEMALE_TRUNK_LIMB_v2.3",
        "topology_signature_sha256": EXPECTED_TOPOLOGY,
        "body_local_frame": {
            "source": "SKEL skin object-local coordinates before frozen prone matrix_world",
            "origin": "SKEL model origin (only axis extents/distances are used)",
            "body_left_right_axis": {"vector": [1.0, 0.0, 0.0], "positive": "subject-left per project SKEL contract"},
            "body_longitudinal_axis": {"vector": [0.0, 1.0, 0.0], "positive": "headward"},
            "body_ventral_dorsal_axis": {"vector": [0.0, 0.0, 1.0], "notice": "signed direction is not given a clinical label; only extent is used"},
        },
        "measurements": {
            "body_longitudinal_length": {
                "axis": "body_longitudinal_y",
                "frozen_vertex_indices": list(range(len(vertices))),
                "vertex_count": len(vertices),
                "method": "full skin y-extent in body-local frame; engineering body length proxy, not standing stature",
            },
            **definitions,
            "shoulder_to_pelvis_length": {
                "axis": "body_longitudinal_y",
                "method": "absolute difference between current GB21 pair mean-y and BL28 pair mean-y",
                "reference_points": ["GB21_LEFT", "GB21_RIGHT", "BL28_LEFT", "BL28_RIGHT"],
            },
        },
        "limitations": [
            "These are reproducible engineering proxies, not clinical anthropometry.",
            "Slice vertex membership is frozen at beta zero to prevent per-shape reselection discontinuities.",
            "Current Atlas points are engineering references and are not doctor-confirmed acupoints.",
            "No valid SKEL joint-name-to-output-row contract was assumed for shoulder width.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ACU_BODY_MEASUREMENT_CONTRACT=PASS")


if __name__ == "__main__":
    main()
