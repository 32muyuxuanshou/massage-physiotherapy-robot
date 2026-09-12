import unittest
from post_txyz_audit.cli import GO_TOKEN,authorize_execution
class TestAuthorization(unittest.TestCase):
    def test_dry_run_blocks_execution(self):
        with self.assertRaisesRegex(RuntimeError,'DRY_RUN_FORBIDS'):authorize_execution(True,True,GO_TOKEN)
    def test_formal_requires_exact_token(self):
        for token in (None,'GO','wrong'):
            with self.assertRaisesRegex(RuntimeError,'APPROVAL_REQUIRED'):authorize_execution(False,True,token)
    def test_exact_token_allows(self):authorize_execution(False,True,GO_TOKEN)
