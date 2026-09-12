import tempfile,unittest,cv2,numpy as np
from pathlib import Path
from post_txyz_audit.k0_data_features import extract
class TestK0Data(unittest.TestCase):
    def test_reads_depth_and_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);depth=np.array([[1000,1100],[0,1300]],np.uint16);mask=np.full((2,2),255,np.uint8);cv2.imwrite(str(root/'d.png'),depth);cv2.imwrite(str(root/'m.png'),mask);out=extract(root/'d.png',root/'m.png');self.assertEqual(out['valid_depth_pixels'],3);self.assertAlmostEqual(out['depth_hole_ratio'],.25)
