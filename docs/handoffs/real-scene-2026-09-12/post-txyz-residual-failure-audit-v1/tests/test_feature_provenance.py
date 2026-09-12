import unittest
from post_txyz_audit.leakage_audit import assert_no_leakage
class TestProvenance(unittest.TestCase):
    def test_heldout_deployment_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'FAIL_HELDOUT_LEAKAGE'):assert_no_leakage([{'name':'bad','source_camera':'K1','deployment_available':True,'uses_heldout_information':False}])
