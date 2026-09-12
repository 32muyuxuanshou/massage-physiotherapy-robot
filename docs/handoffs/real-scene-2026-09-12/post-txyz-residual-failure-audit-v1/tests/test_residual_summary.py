import unittest
from post_txyz_audit.residual_summary import describe
class TestSummary(unittest.TestCase):
 def test_list_and_bool_features_are_summarized(self):
  row={'cameras':{k:{'official':{'median_mm':2},'txyz':{'median_mm':1}} for k in ('K1','K2','K3')}};features={'steps':{'value':[1,2,3,4,5,6]},'oscillation':{'value':True},'fallback':{'value':False}};out=describe([row],[features])['GROUP_A']['features'];self.assertEqual(out['steps']['per_iteration_median'],[1,2,3,4,5,6]);self.assertEqual(out['oscillation']['true_rate'],1)
