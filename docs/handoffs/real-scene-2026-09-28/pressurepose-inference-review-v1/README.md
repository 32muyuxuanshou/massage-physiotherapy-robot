# PressurePose inference review V1

## Scope

This handoff records the inference-only comparison on 20 real PressurePose participants. The compared methods are official SAM3D Body output, Official + Cheap Txyz, and Official + Txyz + Pose. No model was trained in this run.

## Main finding

The previous `GOOD / MIXED / BAD` visual labels are withdrawn. The reported 3D metric is one-sided distance from observed K0 depth points to the nearest predicted-mesh triangle. Txyz and T+Pose are fitted using this same K0 point-cloud source; the evaluation points were sampled from that same pool without a disjoint split. The lower residual therefore means a closer fit to the optimization source, not independent mesh accuracy.

Visual review also found clear local misalignment in multiple cases. The separate 2D support diagnostic is only supporting evidence: it compares the mesh silhouette with projected filtered K0 points, dilated by 3 px, and is not manual ground truth. T+Pose's projected support IoU was worse than Txyz in 14/20 participants and better in 6/20. PressurePose real captures do not provide a ground-truth human mesh for this evaluation.

Txyz is a translation-only correction estimated from depth-point-to-mesh distances. It shifts the predicted mesh in camera-space Tx/Ty/Tz; it does not predict or recover a true mesh from ground-truth mesh supervision. The detailed implementation and limitations are in `reports/EVALUATION_AUDIT.md` and `code/`.

## Files

- `reports/RESULTS.md`, `results.json`, `summary.json`, `per_subject_metrics.csv`: run-level and per-subject results.
- `reports/EVALUATION_AUDIT.md`: metric validity and interpretation.
- `reports/DIRECTIONAL_ERROR_REPORT.md`, JSON/CSV: observed translation-correction directions, not independent ground-truth error vectors.
- `reports/alignment_diagnostic_v1.json`: projected support diagnostic.
- `reports/EXECUTION_MANIFEST.json`, `INTEGRITY_CHECK.json`: execution identity and integrity records.
- `visuals/contact_sheet_01.jpg`–`contact_sheet_04.jpg`: all-subject method overlays.
- `visuals/tpose_2d_*.jpg`: visual groups by T+Pose vs Txyz projected support diagnostic; see `visuals/README.md` and `visuals/INDEX.csv`.
- `code/`: inference and diagnostic scripts used for this run.

Individual mesh parameter NPZ files and the downloaded dataset pickle are intentionally not included in this handoff. The source outputs remain in the local/server experiment directories; the compact reports and visual summaries here are intended for web review.

## Interpretation boundary

This is an engineering inference review, not a validated accuracy claim. A credible next accuracy test needs a disjoint held-out depth set and/or independent reference annotations, plus regional/silhouette checks. Do not describe same-source point-cloud fitting scores as ground-truth mesh error.
