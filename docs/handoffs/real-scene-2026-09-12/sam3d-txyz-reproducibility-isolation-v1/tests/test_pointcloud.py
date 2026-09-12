import unittest,numpy as np
from repro_isolation.pointcloud import reconstruct
class TestPointcloud(unittest.TestCase):
 def test_byte_identical(self):
  d=np.array([[1000,0],[1100,1200]],np.uint16);m=np.full((2,2),255,np.uint8);t=np.zeros((2,2,2),np.float32);self.assertEqual(reconstruct(d,m,t)[1]['sha256'],reconstruct(d,m,t)[1]['sha256'])
