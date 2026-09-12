import hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
from post_txyz_audit.replay_feature_export import export
class TestReplayProvenance(unittest.TestCase):
 def test_hash_and_provenance_are_required(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);np.savez(root/'p.npz',points=np.zeros((5,3)));np.savez(root/'a.npz',anchors=np.zeros((5,3)))
   sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();item={'frame_id':'f','points_npz':str(root/'p.npz'),'points_sha256':sha(root/'p.npz'),'anchors_npz':str(root/'a.npz'),'anchors_sha256':sha(root/'a.npz'),'points_source':{'camera':'K0','depth':'d','mask':'m','calibration':'c'},'anchors_source':{'system':'OFFICIAL_SAM3D_V2_3','surface_anchor_hash':'h','source_mesh_provenance':'mesh'}};manifest=root/'m.json';manifest.write_text(json.dumps({'rows':[item]}));out=export(manifest,root/'o.json');self.assertEqual(out['rows'][0]['input_provenance']['points_sha256'],item['points_sha256'])
   item['points_sha256']='bad';manifest.write_text(json.dumps({'rows':[item]}))
   with self.assertRaisesRegex(RuntimeError,'HASH_MISMATCH'):export(manifest,root/'o.json')
