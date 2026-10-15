"""Known geometry checks for the actual diagnostic transformations."""
import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from analyze_cached import rigid_align
from rigid_diagnostic import matched_fit


class GeometryChecks(unittest.TestCase):
    def setUp(self):
        self.points=np.random.default_rng(20261015).normal(size=(400,3))

    def test_kabsch_recovers_known_rigid_without_scale(self):
        R=Rotation.from_euler('xyz',[.2,-.1,.3]).as_matrix()
        q=self.points@R.T+np.array([.08,.04,-.02])
        aligned,row_R=rigid_align(self.points,q)
        np.testing.assert_allclose(aligned,q,atol=2e-15)
        np.testing.assert_allclose(row_R,R.T,atol=2e-15)
        self.assertAlmostEqual(np.linalg.det(row_R),1)

    def test_matched_translation_recovers_known_small_motion(self):
        shift=np.array([.002,-.003,.001])
        fit=matched_fit(self.points+shift,self.points,self.points.mean(0),False)
        np.testing.assert_allclose(fit['d'],shift,atol=1e-14)
        self.assertFalse(fit['fallback'])

    def test_matched_rigid_recovers_known_small_motion(self):
        R=Rotation.from_euler('xyz',[.001,-.002,.001]).as_matrix()
        pivot=self.points.mean(0);shift=np.array([.002,-.003,.001])
        q=(self.points-pivot)@R.T+pivot+shift
        fit=matched_fit(q,self.points,pivot,True)
        np.testing.assert_allclose(fit['R'],R,atol=2e-14)
        np.testing.assert_allclose(fit['d'],shift,atol=2e-14)


if __name__=='__main__':unittest.main()
