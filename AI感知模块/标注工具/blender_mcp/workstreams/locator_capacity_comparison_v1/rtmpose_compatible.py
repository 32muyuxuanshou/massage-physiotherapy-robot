from mmpose.models import TopdownPoseEstimator
from mmpose.registry import MODELS


@MODELS.register_module()
class RTMPoseCompatibleTopdown(TopdownPoseEstimator):
    """Adapt standard RTMCCHead loss output to the MedSapiens estimator fork."""

    def loss(self, inputs, data_samples):
        feats = self.extract_feat(inputs)
        result = self.head.loss(feats, data_samples, train_cfg=self.train_cfg)
        if isinstance(result, tuple):
            losses, predictions = result
        else:
            losses, predictions = result, None
        return losses, predictions
