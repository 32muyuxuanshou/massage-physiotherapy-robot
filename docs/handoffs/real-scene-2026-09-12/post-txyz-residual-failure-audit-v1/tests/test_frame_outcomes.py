import unittest
from post_txyz_audit.frame_outcomes import classify_frame
def row(n):
    cams={};
    for i,k in enumerate(('K1','K2','K3')):cams[k]={'official':{'median_mm':10},'txyz':{'median_mm':9 if i<n else 11}}
    return {'cameras':cams}
class TestOutcomes(unittest.TestCase):
    def test_all_groups(self):
        self.assertEqual([classify_frame(row(n))['frame_outcome_class'] for n in range(4)],['GROUP_D','GROUP_C','GROUP_B','GROUP_A'])
