import tempfile,unittest
from pathlib import Path
from post_txyz_audit.io_v23 import snapshot_tree,assert_tree_unchanged
class TestReadOnlyTree(unittest.TestCase):
    def test_any_tree_mutation_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'nested').mkdir();(root/'nested/x').write_text('before');before=snapshot_tree(root);(root/'other').write_text('new')
            with self.assertRaisesRegex(RuntimeError,'READ_ONLY_V23_TREE_VIOLATION'):assert_tree_unchanged(root,before)
