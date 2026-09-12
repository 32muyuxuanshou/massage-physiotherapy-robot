import unittest
from repro_isolation.frame_order import build
class TestOrder(unittest.TestCase):
 def test_three_frozen_orders(self):self.assertEqual(set(build(['a','b','c'])['orders']),{'ORDER_ORIGINAL','ORDER_REVERSED','ORDER_RANDOM_FIXED_SEED'})
