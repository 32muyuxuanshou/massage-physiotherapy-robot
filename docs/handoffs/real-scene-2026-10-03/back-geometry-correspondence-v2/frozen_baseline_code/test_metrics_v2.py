"""Targeted analytical checks for the two demonstrated evaluator bugs."""
import json
import unittest
import numpy as np
from metrics_v2 import ray_depth_residual, common_hit_mask


class CameraRayTests(unittest.TestCase):
    def test_perspective_point_on_triangle(self):
        v = np.array([[0,0,1], [2,0,2], [0,2,2]], float)
        d, hit = ray_depth_residual(np.array([[.5,.5,1.5]]), v, [[0,1,2]])
        self.assertTrue(hit[0]); self.assertAlmostEqual(d[0], 0, places=12)

    def test_large_triangle_not_dropped(self):
        big = np.array([[0,0,1], [2,0,2], [0,2,2]], float)
        tiny = np.array([[20,20,2], [20.0001,20,2], [20,20.0001,2]])
        v = np.vstack([big]+[tiny]*2000)
        f = np.arange(len(v)).reshape(-1,3)
        d, hit = ray_depth_residual(np.array([[.5,.5,1.5]]), v, f)
        self.assertTrue(hit[0]); self.assertAlmostEqual(d[0], 0, places=12)

    def test_front_intersection_and_no_hit(self):
        v = np.array([[-1,-1,2],[1,-1,2],[0,1,2],[-1,-1,1],[1,-1,1],[0,1,1]],float)
        d, hit = ray_depth_residual(np.array([[0,0,1.5],[10,10,1.]]),v,[[0,1,2],[3,4,5]])
        np.testing.assert_array_equal(hit,[True,False]); self.assertAlmostEqual(d[0],-.5)
        self.assertTrue(np.isnan(d[1]))

    def test_common_hits_preserve_point_identity(self):
        np.testing.assert_array_equal(common_hit_mask([[True,False,True],[True,True,False]]),[True,False,False])

if __name__ == '__main__':
    unittest.main()
