import subprocess,tempfile,unittest
from pathlib import Path
from repro_fix.reviewed_delivery_integrity import verify

TAG='test-reviewed-v1.4.1'
CRITICAL=('FEATURE_STABILITY_CONTRACT_V1_4.json','FRAME_ORDER_TEST_SPEC_V1_2.json','RUN_A_ASSET_FREEZE_V1.json','RUNTIME_ASSET_FREEZE_V1_4.json')

def git(repo,*args):return subprocess.run(['git','-C',str(repo),*args],check=True,text=True,capture_output=True).stdout.strip()

def repository(root):
 git(root,'init');git(root,'config','user.email','test@example.invalid');git(root,'config','user.name','Integrity Test');delivery=root/'delivery';delivery.mkdir()
 for name in CRITICAL:(delivery/name).write_text('{"frozen":true}\n')
 (delivery/'repro_fix.py').write_text('VALUE = 1\n');git(root,'add','.');git(root,'commit','-m','reviewed delivery');git(root,'tag','-a',TAG,'-m','reviewed test tag');return delivery

class ReviewedDeliveryIntegrityV141(unittest.TestCase):
 def test_01_normal_reviewed_delivery_passes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);delivery=repository(root);result=verify(delivery,root,TAG);self.assertEqual(result['status'],'PASS_REVIEWED_DELIVERY_INTEGRITY');self.assertTrue(result['working_tree_clean'])

 def assert_contract_mutation_rejected(self,name):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);delivery=repository(root);(delivery/name).write_text('{"frozen":false}\n')
   with self.assertRaisesRegex(RuntimeError,'REVIEWED_DELIVERY_WORKTREE_DIRTY'):verify(delivery,root,TAG)

 def test_02_modified_feature_contract_rejected(self):self.assert_contract_mutation_rejected('FEATURE_STABILITY_CONTRACT_V1_4.json')
 def test_03_modified_frame_order_spec_rejected(self):self.assert_contract_mutation_rejected('FRAME_ORDER_TEST_SPEC_V1_2.json')
 def test_04_modified_run_a_freeze_rejected(self):self.assert_contract_mutation_rejected('RUN_A_ASSET_FREEZE_V1.json')

 def test_05_head_other_than_reviewed_tag_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);delivery=repository(root);(root/'outside.txt').write_text('new head\n');git(root,'add','outside.txt');git(root,'commit','-m','different head')
   with self.assertRaisesRegex(RuntimeError,'REVIEWED_DELIVERY_COMMIT_MISMATCH'):verify(delivery,root,TAG)

if __name__=='__main__':unittest.main()
