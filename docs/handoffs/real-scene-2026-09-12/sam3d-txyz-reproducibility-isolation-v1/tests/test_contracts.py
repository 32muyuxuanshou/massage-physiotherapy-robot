import unittest
from repro_isolation.contracts import classify_numeric,classify_bool,heldout,hierarchical,matched,deployment_provenance
class TestContracts(unittest.TestCase):
 def test_stability_and_flip(self):
  self.assertEqual(classify_numeric([1,1.0005],{'absolute_tolerance':.001,'caution_tolerance':.01})['status'],'STABLE');self.assertEqual(classify_bool([True,False],{'max_flip_rate':0})['status'],'UNSTABLE')
 def test_outcomes(self):
  c={k:{'official':{'median_mm':10},'txyz':{'median_mm':v}} for k,v in zip(('K1','K2','K3'),(8,11,9))};self.assertEqual(heldout(c)['number_cameras_improved'],2)
 def test_hierarchy(self):
  o=hierarchical([{'subject':'s','sequence':'q','x':1},{'subject':'s','sequence':'q','x':3}],'x');self.assertFalse(o['iid_inference_allowed']);self.assertEqual(o['subject_level']['s'],2)
 def test_matched_rule(self):
  t={'subject':'s','sequence':'q','frame_index':10};rows=[{'subject':'s','sequence':'q','frame_index':8,'group':'GROUP_A'},{'subject':'s','sequence':'q','frame_index':12,'group':'GROUP_A'}];self.assertEqual(matched(t,rows)['frame_index'],8)
 def test_mask_provenance(self):self.assertFalse(deployment_provenance('dataset','mask_bbox')['deployment_ready'])
