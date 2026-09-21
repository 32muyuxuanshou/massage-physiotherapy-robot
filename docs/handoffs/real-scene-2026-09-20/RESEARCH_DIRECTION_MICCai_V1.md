# From post-processing to a publishable method

## Current position

The corrected V3 pipeline shows that SAM 3D Body can recover a usable full-body mesh from BEHAVE RGB-D input when the original camera contract is preserved. Cheap Txyz improves held-out mesh-to-sensor error, and the joint T+Pose optimizer adds a smaller improvement. This is a strong engineering baseline, but it is not yet a research contribution: it is inference-time alignment plus a small optimization loop.

## Proposed research problem

**Visibility-aware partial-observation RGB-D human mesh recovery for clinically relevant landmark localization.**

The input is a real RGB-D frame with a known person mask or prompt. Only part of the body may be visible because of cropping, occlusion, clothing, posture, or sensor placement. The system must predict a full MHR mesh, estimate which body regions are actually supported by observations, and propagate that uncertainty to back-surface landmark/acupoint localization.

The key claim should be:

> A model that explicitly represents observation visibility and uses depth as a training-time geometric constraint is more reliable for partial-body mesh completion and downstream landmark localization than a monocular mesh model followed by unconstrained post-processing.

## Method direction

Keep SAM3D as the frozen initialization and introduce a trainable RGB-D adaptation module rather than rewriting the whole model:

1. **Region-conditioned prompt encoder**
   Encode the dataset-derived visible-region mask, RGB crop metadata, and sparse depth tokens. The mask is a visibility prompt, not a detector output.

2. **Visibility-aware mesh tokens**
   Predict per-anchor visibility/support weights. Observed anchors receive stronger RGB-D evidence; unobserved anchors are completed by the MHR prior. This prevents a local torso crop from forcing every body parameter to follow the same confidence level.

3. **Differentiable depth alignment head**
   Predict translation and global/body pose residuals from RGB-D tokens in one forward pass. The current Txyz/T+Pose optimizer becomes a teacher or initialization target during training, not the deployed method itself.

4. **Geometry and uncertainty losses**
   Use held-out sensor depth as the primary geometric supervision, with robust point-to-surface loss, visibility-weighted loss, parameter regularization, and calibrated uncertainty. BEHAVE fitted SMPL remains supporting evidence.

5. **Landmark propagation head**
   Map the canonical acupoint atlas onto the predicted MHR surface and output a 3D point plus uncertainty. This connects the mesh contribution to the robot task and gives a clinically meaningful downstream metric.

## Why this is stronger than post-processing

The deployed model would produce the corrected mesh and confidence in one pass. The method learns when depth is trustworthy, which regions are visible, and how much of the full body should be completed from the prior. The optimization loop is retained only as a training teacher, ablation baseline, or optional emergency fallback.

This is materially different from simply fine-tuning SAM3D on a small set of images. The novelty is the visibility-conditioned geometry pathway and its calibrated effect on partial-body mesh completion and landmark localization.

## Evidence needed for MICCAI

The paper should compare:

- Official SAM3D;
- Official + frozen Txyz/T+Pose;
- RGB-D fine-tuning without visibility modeling;
- Proposed visibility-aware RGB-D model;
- Proposed model without uncertainty or without landmark supervision.

All methods must use the same subjects, masks, depth points, cameras and aggregation order. Primary metrics should be held-out sensor mesh error, visible-region versus completed-region error, 3D landmark error, failure/abstention calibration, and temporal jitter when video is available.

The minimum credible dataset design is:

- BEHAVE for multi-view geometric training/evaluation and controlled ablations;
- additional real RGB-D or phone/depth captures with clinician-reviewed back landmarks for the final task;
- synthetic visibility masks only as augmentation, never as the only source of partial observations.

## Engineering-first implementation order

1. Finish V3 visualizations and translation/pose attribution.
2. Build a frozen partial-observation benchmark with natural and synthetic visibility masks.
3. Implement a small visibility/depth adapter around frozen SAM3D; keep the official model unchanged.
4. Train with BEHAVE K0 input and K1/K2/K3 held-out sensor supervision, subject-disjoint splits.
5. Add atlas-to-MHR landmark localization and uncertainty output.
6. Validate on additional real scenes and clinician-reviewed landmarks.

## Decision gate

Do not start broad fine-tuning until the attribution benchmark shows that the dominant residual is systematic partial-observation error rather than camera-contract, translation, or data-quality error. If the proposed adapter does not improve held-out depth and landmark localization together, retain the corrected SAM3D + Txyz baseline for engineering and change the research claim.

## Publication positioning

The method is naturally suitable for MICCAI if the clinical landmark endpoint and uncertainty are real and rigorously evaluated. With a stronger new architecture, larger cross-domain evaluation and a general partial-body mesh contribution, it could also target 3DV, CVPR or ICCV. The venue should follow the evidence; the engineering system should not be distorted to fit a venue label.
