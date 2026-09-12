import unittest
from post_txyz_audit.leakage_audit import assert_no_leakage
class TestWhitelist(unittest.TestCase):
    def test_unknown_deployment_camera_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'FAIL_HELDOUT_LEAKAGE'):assert_no_leakage([{'name':'bad','source_camera':'MULTICAM','deployment_available':True,'uses_heldout_information':False}])
    def test_k0_allowed(self):self.assertEqual(assert_no_leakage([{'name':'ok','source_camera':'K0','deployment_available':True,'uses_heldout_information':False}])['status'],'PASS')
