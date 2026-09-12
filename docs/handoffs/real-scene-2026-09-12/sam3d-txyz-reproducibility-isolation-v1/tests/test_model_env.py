import unittest
from repro_isolation.model_load import classify_missing,validate,REQUIRED
class TestModel(unittest.TestCase):
 def test_missing_classes(self):
  x=classify_missing(['w','b','x.mhr.foo','z'],{'w'},{'b'});self.assertEqual(list(x.values()),['TRAINABLE_PARAMETER','BUFFER','STATIC_MHR_ASSET','OTHER'])
 def test_env_complete(self):
  with self.assertRaises(ValueError):validate({})
  self.assertTrue(validate({k:'x' for k in REQUIRED}))
