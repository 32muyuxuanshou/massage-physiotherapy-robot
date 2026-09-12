import unittest
from post_txyz_audit.k0_feature_extractor import extract_existing
class TestMissing(unittest.TestCase):
    def test_missing_is_explicit(self):
        row={'Txyz_m':[0,0,0],'fallback':False,'runtime_sam_ms':1,'runtime_txyz_ms':2,'runtime_total_ms':3};schema=[{'name':'depth_hole_ratio','availability_status':'REQUIRES_K0_DATA_READ'}];self.assertEqual(extract_existing(row,schema)['depth_hole_ratio'],{'status':'REQUIRES_K0_DATA_READ','value':None})
