import tempfile,unittest
from pathlib import Path
from post_txyz_audit.io_v23 import assert_unchanged,sha256
class TestReadOnly(unittest.TestCase):
    def test_mutation_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'x';path.write_text('before');before=[{'path':str(path),'bytes':6,'sha256':sha256(path)}];assert_unchanged(before);path.write_text('after')
            with self.assertRaisesRegex(RuntimeError,'READ_ONLY_V23_VIOLATION'):assert_unchanged(before)
