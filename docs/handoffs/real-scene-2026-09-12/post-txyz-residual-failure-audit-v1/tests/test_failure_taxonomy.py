import unittest
from post_txyz_audit.failure_taxonomy import empty_assessment,validate_assessment
class TestTaxonomy(unittest.TestCase):
    def test_empty_requires_review(self):self.assertTrue(validate_assessment(empty_assessment('x'))['requires_visual_review'])
    def test_automatic_conclusion_rejected(self):
        value=empty_assessment('x');value['automatic_causal_conclusion']=True
        with self.assertRaises(ValueError):validate_assessment(value)
