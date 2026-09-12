import unittest,numpy as np
from post_txyz_audit.txyz_replay_instrumentation import replay,ITERATIONS
class TestReplay(unittest.TestCase):
    def test_frozen_six_iteration_trace_and_features(self):
        anchors=np.array([[0,0,0],[.1,0,0],[0,.1,0],[0,0,.1],[.1,.1,.1]])
        out=replay(anchors+np.array([.01,-.02,.03]),anchors);self.assertEqual(len(out['trace']),ITERATIONS);self.assertEqual(len(out['features']['iteration_step_norms_mm']),ITERATIONS);self.assertTrue({'residual_p95_mm','inlier_ratio'}<=set(out['features']))
