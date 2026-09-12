import unittest,numpy as np
from repro_isolation.txyz_exact import fit,repeat,bitwise_equal,digest
class TestTxyz(unittest.TestCase):
 def test_exact_repeat(self):
  a=np.arange(60,dtype=float).reshape(20,3)/100;self.assertTrue(bitwise_equal(repeat(a+.01,a,20)))
 def test_anchor_hash_changes(self):
  a=np.zeros((3,3));h=digest(a);a[0,0]=1;self.assertNotEqual(h,digest(a))
 def test_point_order_contract(self):
  a=np.arange(60,dtype=float).reshape(20,3)/100;self.assertEqual(fit(a+.01,a)['translation_m'],fit((a+.01)[::-1],a)['translation_m'])
