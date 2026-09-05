from mmengine.config import read_base

with read_base():
    from mmpose.configs._base_.default_runtime import *

from mmengine.dataset import DefaultSampler
from mmengine.hooks import CheckpointHook
from mmengine.optim import CosineAnnealingLR, OptimWrapper
from torch.nn import SiLU
from torch.optim import AdamW

from mmdet.models import CSPNeXt
from mmpose.codecs import SimCCLabel
from mmpose.datasets import CocoDataset, GenerateTarget, GetBBoxCenterScale, LoadImage, PackPoseInputs, TopdownAffine
from mmpose.evaluation import PCKAccuracy
from mmpose.models import KLDiscretLoss, PoseDataPreprocessor, RTMCCHead, TopdownPoseEstimator
from rtmpose_compatible import RTMPoseCompatibleTopdown


project_root = "/raid5/xuhd/massage_ai_perception"
data_root = f"{project_root}/data/pose_holdout/"
work_dir = f"{project_root}/outputs/rtmpose_s_pose_holdout"
input_size = (160, 128)
max_epochs = 80
default_scope = "mmpose"
custom_imports = dict(imports=["rtmpose_compatible"], allow_failed_imports=False)

point_names = [
    "GV14_MIDLINE", "BL13_LEFT", "BL13_RIGHT", "GV9_MIDLINE", "BL17_LEFT",
    "BL17_RIGHT", "GV6_MIDLINE", "BL20_LEFT", "BL20_RIGHT", "GV4_MIDLINE",
    "BL23_LEFT", "BL23_RIGHT", "BL25_LEFT", "BL25_RIGHT", "BL28_LEFT",
    "BL28_RIGHT", "GB21_LEFT", "GB21_RIGHT", "SI15_LEFT", "SI15_RIGHT",
]
metainfo = dict(
    dataset_name="engineering_back20",
    keypoint_info={
        index: dict(name=name, id=index, color=[255, 0, 0], type="", swap="")
        for index, name in enumerate(point_names)
    },
    skeleton_info={},
    joint_weights=[1.0] * 20,
    sigmas=[0.05] * 20,
)

codec = dict(
    type=SimCCLabel,
    input_size=input_size,
    sigma=(4.0, 4.0),
    simcc_split_ratio=2.0,
    normalize=False,
    use_dark=False,
)

model = dict(
    type=RTMPoseCompatibleTopdown,
    data_preprocessor=dict(
        type=PoseDataPreprocessor,
        mean=[123.675, 116.28, 103.53],
        std=[58.395, 57.12, 57.375],
        bgr_to_rgb=True,
    ),
    backbone=dict(
        _scope_="mmdet",
        type=CSPNeXt,
        arch="P5",
        expand_ratio=0.5,
        deepen_factor=0.33,
        widen_factor=0.5,
        out_indices=(4,),
        channel_attention=True,
        norm_cfg=dict(type="BN"),
        act_cfg=dict(type=SiLU),
        init_cfg=None,
    ),
    head=dict(
        type=RTMCCHead,
        in_channels=512,
        out_channels=20,
        input_size=input_size,
        in_featuremap_size=(5, 4),
        simcc_split_ratio=codec["simcc_split_ratio"],
        final_layer_kernel_size=7,
        gau_cfg=dict(
            hidden_dims=256,
            s=128,
            expansion_factor=2,
            dropout_rate=0.0,
            drop_path=0.0,
            act_fn="SiLU",
            use_rel_bias=False,
            pos_enc=False,
        ),
        loss=dict(type=KLDiscretLoss, use_target_weight=True, beta=10.0, label_softmax=True),
        decoder=codec,
    ),
    test_cfg=dict(flip_test=False),
)

train_pipeline = [
    dict(type=LoadImage),
    dict(type=GetBBoxCenterScale, padding=1.0),
    dict(type=TopdownAffine, input_size=input_size),
    dict(type=GenerateTarget, encoder=codec),
    dict(type=PackPoseInputs),
]
test_pipeline = [
    dict(type=LoadImage),
    dict(type=GetBBoxCenterScale, padding=1.0),
    dict(type=TopdownAffine, input_size=input_size),
    dict(type=PackPoseInputs),
]


def dataset(bucket, test_mode=False):
    return dict(
        type=CocoDataset,
        data_root=data_root,
        data_mode="topdown",
        ann_file=f"annotations/{bucket}.json",
        data_prefix=dict(img="images/"),
        metainfo=metainfo,
        pipeline=test_pipeline if test_mode else train_pipeline,
        test_mode=test_mode,
    )


train_dataloader = dict(
    batch_size=32,
    num_workers=4,
    persistent_workers=True,
    sampler=dict(type=DefaultSampler, shuffle=True),
    dataset=dataset("train"),
)
val_dataloader = dict(
    batch_size=32,
    num_workers=4,
    persistent_workers=True,
    drop_last=False,
    sampler=dict(type=DefaultSampler, shuffle=False, round_up=False),
    dataset=dataset("val", test_mode=True),
)
test_dataloader = dict(
    batch_size=32,
    num_workers=4,
    persistent_workers=True,
    drop_last=False,
    sampler=dict(type=DefaultSampler, shuffle=False, round_up=False),
    dataset=dataset("test", test_mode=True),
)
del dataset

train_cfg = dict(by_epoch=True, max_epochs=max_epochs, val_interval=4)
val_cfg = dict()
test_cfg = dict()

optim_wrapper = dict(type=OptimWrapper, optimizer=dict(type=AdamW, lr=5e-4, weight_decay=1e-5))
param_scheduler = [
    dict(type=CosineAnnealingLR, eta_min=2e-5, begin=0, end=max_epochs, T_max=max_epochs, by_epoch=True)
]

val_evaluator = dict(type=PCKAccuracy, thr=0.05, norm_item="bbox")
test_evaluator = val_evaluator
default_hooks.update(
    checkpoint=dict(type=CheckpointHook, interval=4, save_best="PCK", rule="greater", max_keep_ckpts=1),
    logger=dict(interval=10),
)
randomness = dict(seed=20260831, deterministic=True)
auto_scale_lr = dict(enable=False, base_batch_size=32)
