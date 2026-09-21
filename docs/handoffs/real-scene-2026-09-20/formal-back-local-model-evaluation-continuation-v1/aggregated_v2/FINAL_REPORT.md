> **AUDIT CORRECTION: INVALID_FOR_CONTROLLED_SCIENTIFIC_COMPARISON.** The prior scientific interpretations are withdrawn. See [execution audit](../EXECUTION_AUDIT.md) for preprocessing, optimizer, evaluation-sampling and aggregation deviations. Raw results below are historical debugging evidence only.

# FORMAL_BACK_LOCAL_MODEL_EVALUATION_CONTINUATION_V1

## Execution status

**COMPLETE — BEHAVE primary evaluation, 18 timestamps, 3 subjects, 3 input conditions, 3 methods.**

The first single-card attempt was discarded after an independently detected camera transform direction bug. It is not included in these results. The reported v2 run uses the BEHAVE contract `camera_to_world = points @ R.T + t` and `world_to_camera = (points - t) @ R`.

## Evidence contract

Primary evidence is K1/K2/K3 held-out sensor depth to predicted MHR surface. K0 is used only for RGB/mask/depth input and correction. BEHAVE `person_fit.ply` is supporting fitted multi-view SMPL evidence, not absolute ground truth. The fitted-reference metric uses 2,000 deterministic sampled reference vertices per camera; it is supporting evidence only.

All 18 frozen timestamps were retained. No detector was used: all three conditions use dataset-mask-derived crops and known bbox prompts. LOCAL_TORSO is a fixed torso-localized crop, not an anatomical back ROI.

## Primary held-out results

| Input | Method | Held-out median (mm) | P95 of subject medians (mm) | coverage <=50mm | fitted-SMPL supporting median (mm) |
|---|---:|---:|---:|---:|---:|
| FULL | Official | 486.72 | 545.99 | 0.003 | 577.97 |
| FULL | Txyz | 487.50 | 548.55 | 0.004 | 576.72 |
| FULL | T+Pose | 186.61 | 236.80 | 0.124 | 264.23 |
| UPPER | Official | 205.04 | 238.35 | 0.140 | 283.11 |
| UPPER | Txyz | 202.99 | 240.07 | 0.143 | 281.38 |
| UPPER | T+Pose | 63.76 | 99.20 | 0.414 | 89.40 |
| LOCAL_TORSO | Official | 538.79 | 599.96 | 0.000 | 526.70 |
| LOCAL_TORSO | Txyz | 539.86 | 604.03 | 0.000 | 528.12 |
| LOCAL_TORSO | T+Pose | 237.40 | 280.31 | 0.078 | 264.29 |

## Direct answers

### A. FULL → UPPER → LOCAL_TORSO

For Official SAM3D, the subject-aware held-out median is FULL **486.72 mm**, UPPER **205.04 mm**, LOCAL_TORSO **538.79 mm**. In this frozen sample, LOCAL_TORSO is **52.07 mm worse than FULL**, while UPPER is **281.69 mm lower**. This is a factual result, not evidence that UPPER is universally better; the three subjects and action mix are small.

For T+Pose, the corresponding medians are FULL **186.61 mm**, UPPER **63.76 mm**, LOCAL_TORSO **237.40 mm**. LOCAL_TORSO remains **50.79 mm worse than FULL** after pose correction.

### B. Cheap Txyz

Txyz changes the subject-aware held-out median by **+0.77 mm** on FULL, **−2.05 mm** on UPPER, and **+1.07 mm** on LOCAL_TORSO relative to Official. It therefore provides little rescue in this experiment. The subject-direction counts are 2/3 improved on FULL, 2/3 on UPPER and 3/3 on LOCAL_TORSO, but the aggregate gains are small.

### C. T+Pose after Txyz

T+Pose improves held-out median by **−300.88 mm** on FULL, **−139.23 mm** on UPPER and **−302.46 mm** on LOCAL_TORSO relative to Txyz. Subject-level improvement is 3/3 for FULL and LOCAL_TORSO, and 2/3 for UPPER. The pre-registered K0-overfit audit found **1/54 condition-method rows** where K0 improved but held-out worsened; this is a rare observed case, not a general pattern in this subset.

## Interpretation

The current evidence supports two simultaneous statements:

1. **LOCAL_INPUT_IS_HARD:** LOCAL_TORSO is worse than FULL for Official, Txyz and T+Pose in the subject-aware held-out median.
2. **RGBD_POSE_RESCUES_LOCAL_INPUT:** T+Pose still gives a large held-out improvement over Txyz on LOCAL_TORSO, with 3/3 subject directions improving.

This does not yet justify fine-tuning. The primary evidence is sensor depth, and the sample is only 3 subjects / 18 timestamps. The fitted-SMPL support follows the broad T+Pose improvement direction but is not a second sensor ground truth.

- Historical aligned metric was not recomputed in this run because the raw contract stored held-out sensor metrics and fitted-reference support, not post-hoc translation-aligned meshes. No aligned number is silently substituted.
- Fitted-reference values use deterministic surface samples and are supporting evidence only.
- HuMMan targeted audit is `SMPL_PARAMS_ONLY`; it remains outside the primary result.
- The current visualization package contains metric plots and crop contact sheets; raw mesh overlays require retaining per-method vertices in a future rerun.
