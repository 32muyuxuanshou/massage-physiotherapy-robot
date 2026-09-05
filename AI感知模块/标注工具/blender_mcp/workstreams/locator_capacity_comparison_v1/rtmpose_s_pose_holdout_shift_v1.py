"""RTMPose-S with one predeclared symmetric framing-shift augmentation.

The frozen Pose holdout remains unchanged. Only the training pipeline receives a
small bbox-center shift so visible points can occur closer to either image edge.
"""

from mmengine.config import read_base
from mmpose.datasets import RandomBBoxTransform

with read_base():
    from .rtmpose_s_pose_holdout import *

work_dir = f"{project_root}/outputs/rtmpose_s_pose_holdout_shift_v1"
train_pipeline.insert(
    2,
    dict(
        type=RandomBBoxTransform,
        shift_factor=0.025,
        shift_prob=1.0,
        scale_factor=(1.0, 1.0),
        scale_prob=0.0,
        rotate_factor=0.0,
        rotate_prob=0.0,
    ),
)
train_dataloader["dataset"]["pipeline"] = train_pipeline

del RandomBBoxTransform
