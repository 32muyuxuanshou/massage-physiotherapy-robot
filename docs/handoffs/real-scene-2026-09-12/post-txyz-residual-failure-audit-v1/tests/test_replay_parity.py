import unittest
from post_txyz_audit.replay_parity import compare,assert_all
class TestParity(unittest.TestCase):
 def test_matching_translation_and_fallback_pass(self):
  row=compare('x',{'translation_m':[.1,.2,.3],'fallback':False},{'Txyz_m':[.1,.2,.3],'fallback':False});self.assertTrue(row['parity_pass']);self.assertEqual(assert_all([row])['status'],'PASS_45_OF_45_TXYZ_REPLAY_PARITY')
 def test_translation_or_fallback_mismatch_fails(self):
  for replay in ({'translation_m':[.100002,.2,.3],'fallback':False},{'translation_m':[.1,.2,.3],'fallback':True}):
   with self.assertRaisesRegex(RuntimeError,'PARITY_FAILED'):assert_all([compare('x',replay,{'Txyz_m':[.1,.2,.3],'fallback':False})])
