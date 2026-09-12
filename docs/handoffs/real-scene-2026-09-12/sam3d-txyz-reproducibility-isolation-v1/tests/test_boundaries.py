import unittest
from pathlib import Path
class TestBoundaries(unittest.TestCase):
 def test_back_and_leakage_contracts(self):
  root=Path(__file__).parents[1];self.assertIn('BLOCKED_PENDING_BACK_REGION_DEFINITION',(root/'README_PREEXECUTION_REPRODUCIBILITY.md').read_text(encoding='utf-8-sig'));self.assertIn('K1/K2/K3', (root/'FAILURE_AUDIT_STATISTICAL_CONTRACT_V2.json').read_text())
