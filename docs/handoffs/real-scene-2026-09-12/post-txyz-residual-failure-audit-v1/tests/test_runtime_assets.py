import hashlib,json,tempfile,unittest
from pathlib import Path
from post_txyz_audit.runtime_assets import CALIBRATION_FILES,calibration_bundle_sha,verify
class TestRuntimeAssets(unittest.TestCase):
 def test_all_frozen_assets_verified_and_mutation_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cal=root/'cal';
   for rel in CALIBRATION_FILES:p=cal/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(rel.encode())
   paths={n:root/n for n in ('manifest','txyz','anchors')}
   for n,p in paths.items():p.write_text(n)
   sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();req=root/'r.json';req.write_text(json.dumps({'formal_runtime_gate':{'formal_manifest_sha256':sha(paths['manifest']),'txyz_implementation_sha256':sha(paths['txyz']),'surface_anchors_sha256':sha(paths['anchors']),'camera_calibration_bundle_sha256':calibration_bundle_sha(cal)}}));self.assertEqual(verify(req,paths['manifest'],paths['txyz'],paths['anchors'],cal)['status'],'PASS_RUNTIME_ASSET_REVERIFICATION');paths['anchors'].write_text('changed')
   with self.assertRaisesRegex(RuntimeError,'ASSET_FREEZE_MISMATCH'):verify(req,paths['manifest'],paths['txyz'],paths['anchors'],cal)
