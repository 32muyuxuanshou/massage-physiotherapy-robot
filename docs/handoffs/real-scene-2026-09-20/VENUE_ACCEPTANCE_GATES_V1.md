# Strong-acceptance gates for the RGB-D mesh and acupoint project

## Venue reading

MICCAI 2026 asks reviewers to assess clinical significance, data collection and division, label quality, sufficient performance measures with uncertainty, statistical analysis, substantial contribution, limitations, and clinical translation. Its author guidelines distinguish methodological papers, which need clear innovation over the state of the art, from application/translation papers, which need rigorous evidence of clinical value and viability.

CVPR 2026 emphasizes a technically sound contribution, a meaningful knowledge advance, novelty and impact, and self-contained evidence within the submission. A method that is only a small optimizer around an existing mesh model is unlikely to be a strong CVPR contribution without a broader algorithmic idea and compelling generalization.

For this project, MICCAI is the more natural first target because the robot, RGB-D sensing, acupoint localization, uncertainty and clinical workflow form a coherent medical/CAI story. 3DV is a strong alternative if the contribution becomes a general partial-body mesh problem. CVPR/ICCV should be considered only if the visibility-aware RGB-D model is demonstrably general beyond massage and acupuncture.

## Strong-acceptance hypothesis

The paper should test one clear claim:

> Explicit visibility reasoning and depth-conditioned geometric supervision improve partial-body human mesh completion and downstream 3D acupoint localization under real occlusion, truncation and sensor variation.

The claim is stronger than “Txyz improves SAM3D.” Txyz/T+Pose remain important baselines and teachers, but they are not the paper's central novelty.

## Non-negotiable evidence gates

### Method gate

- A trainable visibility/depth adapter or equivalent new architecture is required.
- The deployed path must produce mesh and uncertainty in one forward pass; iterative fitting may be a teacher or fallback.
- Ablations must remove visibility modeling, depth supervision, uncertainty and landmark supervision one at a time.
- The method must preserve the official SAM3D camera contract and use identical input geometry across comparisons.

### Data gate

- Subject-disjoint train/validation/test splits.
- BEHAVE for controlled multi-view geometry and held-out sensor evaluation.
- Additional real RGB-D or phone/depth data for the actual back/landmark setting.
- Natural occlusion, truncation, clothing and pose variation; synthetic masks only as augmentation.
- Landmark labels with a documented protocol, annotator agreement and uncertainty where possible.

### Evaluation gate

Primary sensor evidence:

- held-out depth-to-surface error;
- visible-region and completed-region error separately;
- 3D acupoint error in millimetres;
- failure/abstention calibration and uncertainty coverage;
- temporal jitter for video or repeated frames.

Supporting evidence:

- fitted SMPL/MHR reference;
- 2D reprojection and anatomical plausibility;
- clinical landmark consistency.

Report subject-level confidence intervals, paired tests against the strongest baseline, effect sizes, and failure cases. Do not rely on a single median over frames.

### Translation gate

- Demonstrate an end-to-end robot-relevant output: mesh → surface acupoint → 3D target with confidence.
- Measure whether uncertainty can trigger abstention or a safer fallback.
- Show at least a small real-scene feasibility study with the intended sensor and operating geometry.
- State clinical limitations and do not call a fitted mesh ground truth.

## Decision thresholds before submission

Do not write the paper around the method until all of the following are true:

1. The proposed model beats frozen SAM3D, Txyz/T+Pose and RGB-D fine-tuning baselines on held-out sensor error and landmark error.
2. Improvement is consistent across subjects, actions and observation regimes, with confidence intervals.
3. The uncertainty or abstention mechanism reduces dangerous high-error landmark predictions.
4. The result survives a cross-dataset or cross-sensor test.
5. The ablation table shows that visibility reasoning and depth supervision each contribute.
6. The full pipeline is reproducible from a frozen manifest and contains no post-hoc sample selection.

If these gates are not met, publish the engineering/feasibility result at a more suitable venue or continue data collection; do not inflate a post-processing study into a methods paper.

## Immediate next experiment

Run the corrected V3 attribution benchmark on the same frozen 18 frames:

- Official;
- Txyz;
- translation-only;
- translation + global rotation;
- translation + body pose;
- proposed visibility/depth adapter prototype.

The first five conditions identify the residual error mechanism. Only the last condition is the candidate paper method. After that, expand to Sub06/Sub07 and real sensor scenes before any broad training run.
