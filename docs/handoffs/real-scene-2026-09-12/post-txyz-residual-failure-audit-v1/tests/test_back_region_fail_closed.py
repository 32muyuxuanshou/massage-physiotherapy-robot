import unittest
from post_txyz_audit.back_metrics import compute_placeholder
class TestBack(unittest.TestCase):
    def test_absent_definition_blocks(self):
        with self.assertRaisesRegex(RuntimeError,'BLOCKED_PENDING'):compute_placeholder({'status':'BLOCKED_PENDING_BACK_REGION_DEFINITION'})
