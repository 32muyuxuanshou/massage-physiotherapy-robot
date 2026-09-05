"""Negative controls for the additional 3 mm dataset acceptance gate."""
import array
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from PIL import Image
import build_qc_dataset_30 as dataset


class StrictDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = {"resolution": [4, 4], "qc_thresholds": {
            "visible_point_depth_error_m": .003,
            "visible_point_backprojection_error_m": .003}}
        self.profile = {"betas": [0.0]*10, "pose_degrees": {"head_twist": 18.0}}
        anchors = [{"point_id": f"E{i:02d}", "face_index": i,
                    "vertex_indices": [i*3, i*3+1, i*3+2],
                    "barycentric": [1/3]*3, "side": "MIDLINE"} for i in range(1, 21)]
        self.atlas = {"anchors": anchors}
        self.labels = {"scene": {"native_shape_betas": [0.0]*10,
                                 "native_pose_parameters_degrees": {"head_twist": 18.0}},
                       "camera": {"intrinsics": {"fx": 10., "fy": 10., "cx": 1.5, "cy": 1.5}},
                       "points": [dict(copy.deepcopy(a), uv_pixel_opencv=[1.5, 1.5],
                            xyz_camera_opencv_m=[0., 0., 2.], visible=True,
                            ray_hit_object="SKEL-skin-female") for a in anchors]}
        Image.new("L", (4,4), 255).save(self.root / "skin_mask.png")
        self.write_depth(2.)

    def write_depth(self, value):
        header = repr({"descr": "<f4", "fortran_order": False, "shape": (4,4)}).encode("ascii")
        header += b" " * ((64 - (10+len(header)+1) % 64) % 64) + b"\n"
        payload = array.array("f", [value]*16).tobytes()
        (self.root / "scene_depth_z.npy").write_bytes(b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + payload)

    def check(self):
        (self.root / "labels.json").write_text(json.dumps(self.labels), encoding="utf-8")
        return dataset.strict_qc(self.root, self.atlas, self.profile, self.cfg)["passed"]

    def test_valid(self):
        self.assertTrue(self.check())

    def test_reject_depth_over_3mm(self):
        self.write_depth(2.004)
        self.assertFalse(self.check())

    def test_reject_reselected_binding(self):
        self.labels["points"][0]["face_index"] += 1
        self.assertFalse(self.check())

    def test_reject_invisible(self):
        self.labels["points"][0]["visible"] = False
        self.assertFalse(self.check())

    def test_reject_wrong_shape(self):
        self.labels["scene"]["native_shape_betas"][0] = .1
        self.assertFalse(self.check())

    def test_reject_wrong_mask(self):
        Image.new("L", (4,4), 0).save(self.root / "skin_mask.png")
        self.assertFalse(self.check())

    def test_reject_missing_point(self):
        self.labels["points"].pop()
        self.assertFalse(self.check())

    def test_reject_out_of_frame(self):
        self.labels["points"][0]["uv_pixel_opencv"] = [-.1, 1.5]
        self.assertFalse(self.check())

    def test_reject_nan_depth(self):
        self.write_depth(float("nan"))
        self.assertFalse(self.check())


if __name__ == "__main__":
    unittest.main()
