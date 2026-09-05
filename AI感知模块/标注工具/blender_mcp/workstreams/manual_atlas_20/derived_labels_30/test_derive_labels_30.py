from __future__ import annotations

import ast
import json
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import derive_labels_30 as subject


def valid_atlas() -> dict:
    annotations = []
    for index in range(20):
        annotations.append(
            {
                "id": f"annotation-{index:02d}",
                "point_id": f"SIM{index:02d}_{'MIDLINE' if index < 4 else 'LEFT'}",
                "code": f"SIM{index:02d}",
                "name_zh": f"工程点{index:02d}",
                "side": "MIDLINE" if index < 4 else "LEFT",
                "target_mesh": "SKEL-skin-female",
                "face_index": index,
                "vertex_indices": [index, index + 1, index + 2],
                "barycentric": [0.2, 0.3, 0.5],
            }
        )
    return {
        "schema_version": "smpl-acupoint-annotation-v5",
        "model": dict(subject.EXPECTED_MODEL),
        "annotations": annotations,
    }


def write_npy(path: Path, height: int, width: int, value: float) -> None:
    header = repr(
        {"descr": "<f4", "fortran_order": False, "shape": (height, width)}
    )
    prefix = b"\x93NUMPY\x01\x00"
    padding = (16 - ((len(prefix) + 2 + len(header) + 1) % 16)) % 16
    encoded = (header + " " * padding + "\n").encode("latin1")
    path.write_bytes(prefix + struct.pack("<H", len(encoded)) + encoded + struct.pack("<f", value) * (height * width))


class DeriveLabelsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write_atlas(self, payload: dict) -> Path:
        path = self.root / "atlas.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_validates_schema_v5_female_skel_20(self):
        _payload, annotations = subject.validate_atlas(self.write_atlas(valid_atlas()))
        self.assertEqual(20, len(annotations))

    def test_rejects_duplicate_code_side(self):
        payload = valid_atlas()
        payload["annotations"][1]["code"] = payload["annotations"][0]["code"]
        payload["annotations"][1]["side"] = payload["annotations"][0]["side"]
        with self.assertRaisesRegex(ValueError, "duplicate code\+side"):
            subject.validate_atlas(self.write_atlas(payload))

    def test_rejects_bad_barycentric(self):
        payload = valid_atlas()
        payload["annotations"][0]["barycentric"] = [0.2, 0.3, 0.6]
        with self.assertRaisesRegex(ValueError, "sum is not one"):
            subject.validate_atlas(self.write_atlas(payload))

    def test_invisible_points_are_valid_branches(self):
        sample = self.root / "sample"
        sample.mkdir()
        write_npy(sample / "scene_depth_z.npy", 4, 4, 0.0)
        Image.new("L", (4, 4), 0).save(sample / "depth_valid_mask.png")
        Image.new("L", (4, 4), 0).save(sample / "skin_mask.png")
        annotations = valid_atlas()["annotations"]
        points = []
        for annotation in annotations:
            points.append(
                {
                    **{key: annotation[key] for key in ("point_id", "face_index", "vertex_indices", "barycentric", "side")},
                    "visible": False,
                    "visibility_reason": "BEHIND_CAMERA",
                    "in_front": False,
                    "in_frame": False,
                    "front_facing": False,
                    "ray_hit_object": None,
                    "uv_pixel_opencv": [float("inf"), float("inf")],
                    "xyz_camera_opencv_m": [0.0, 0.0, -1.0],
                }
            )
        (sample / "labels.json").write_text(
            json.dumps(
                {
                    "camera": {"intrinsics": {"fx": 1.0, "fy": 1.0, "cx": 2.0, "cy": 2.0}},
                    "points": points,
                }
            ),
            encoding="utf-8",
        )
        report = subject.qc_sample(sample, annotations, {})
        self.assertTrue(report["passed"])
        self.assertEqual(0, report["visible_count"])

    def test_visible_point_uses_existing_depth_and_mask(self):
        sample = self.root / "sample"
        sample.mkdir()
        write_npy(sample / "scene_depth_z.npy", 4, 4, 1.0)
        Image.new("L", (4, 4), 255).save(sample / "depth_valid_mask.png")
        Image.new("L", (4, 4), 255).save(sample / "skin_mask.png")
        annotations = valid_atlas()["annotations"]
        points = []
        for annotation in annotations:
            points.append(
                {
                    **{key: annotation[key] for key in ("point_id", "face_index", "vertex_indices", "barycentric", "side")},
                    "visible": True,
                    "visibility_reason": "VISIBLE",
                    "in_front": True,
                    "in_frame": True,
                    "front_facing": True,
                    "ray_hit_object": "SKEL-skin-female",
                    "uv_pixel_opencv": [1.5, 1.5],
                    "xyz_camera_opencv_m": [0.0, 0.0, 1.0],
                }
            )
        (sample / "labels.json").write_text(
            json.dumps(
                {
                    "camera": {"intrinsics": {"fx": 1.0, "fy": 1.0, "cx": 1.5, "cy": 1.5}},
                    "points": points,
                }
            ),
            encoding="utf-8",
        )
        report = subject.qc_sample(sample, annotations, {})
        self.assertTrue(report["passed"])
        self.assertEqual(20, report["visible_count"])

    def test_blender_side_has_no_render_call_or_render_import(self):
        tree = ast.parse(subject.BLENDER_SIDE.read_text(encoding="utf-8"))
        forbidden = {"render_scene_buffers", "export_sample"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
                self.assertNotIn(called, forbidden)
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, {"training_export_core.render_buffers", "training_export_core.sample_export"})


if __name__ == "__main__":
    unittest.main()
