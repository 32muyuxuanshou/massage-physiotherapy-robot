# PressurePose directional error audit

## Main result

The dominant consistent component is camera-depth Z. Proposed Txyz has median (Tx, Ty, Tz) = (-3.9, -3.0, -135.7) mm; mean = (-2.7, -0.7, -126.3) mm. Tz is negative for 18/20 subjects (positive for 2/20). Under the OpenCV camera convention (+Z points into the scene), a negative Tz moves the mesh toward the camera. X/Y medians are small, so there is no common lateral image-plane translation direction.

Before correction, trimmed nearest-anchor residual medians are (-1.7, -1.2, -106.8) mm. This is still nearest-anchor residual, not anatomical correspondence.

After T+Pose, the projected mesh silhouette centroid relative to projected cloud pixels has median image offset (dx, dy)=(1.1, 0.1) px (right/down positive). This coarse centroid does not show a single global 2D shift, but it cannot detect limb-specific or local pose errors.

## The five Txyz fallback subjects

All five proposed corrections exceeded the 177.9 mm norm limit, so Txyz applied zero translation. Their proposed correction is dominated by negative Z; they remain visibly difficult. T+Pose then moves translation in all five by approximately -74 mm in Z, close to 25 iterations × 3 mm/step Adam learning-rate scale, while residual error remains large. This looks like a constrained optimization path, not proof that the required correction was recovered.

| Subject | Proposed Txyz (Tx,Ty,Tz) mm | Norm mm | T+Pose delta from Txyz (Tx,Ty,Tz) mm | T+Pose median / P95 mm |
|---|---:|---:|---:|---:|
| S104 | (8.8, 44.6, -300.0) | 303.4 | (56.6, 79.9, -74.7) | 219.3 / 301.3 |
| S134 | (-5.8, -7.7, -198.3) | 198.5 | (25.6, -77.7, -74.4) | 95.8 / 157.8 |
| S140 | (-10.3, -11.4, -182.3) | 183.0 | (-29.3, -71.4, -74.2) | 85.4 / 135.7 |
| S141 | (-12.0, -19.7, -178.7) | 180.2 | (-43.6, -69.3, -74.2) | 75.3 / 122.4 |
| S187 | (12.7, 14.8, -223.5) | 224.4 | (20.1, 79.3, -74.4) | 102.3 / 178.9 |

## Why the visuals can still look wrong

Txyz only changes global translation. It cannot fix body orientation, joint pose, local geometry, or visible-limb correspondence. The residual metric is one-way nearest point-to-surface and was optimized and evaluated on the same K0 point-cloud pool. T+Pose lowers that 3D residual in 20/20 cases, but the separate projected point-support IoU is worse than Txyz in 14/20. Thus the current 3D score is not a reliable mesh-alignment score.

A projected silhouette centroid can be nearly centered while an arm, shoulder, torso or leg is locally misplaced. The contour images and local-region review matter; we do not yet have manually annotated image masks or a real GT mesh for this dataset.

## Recommendation

Do not interpret the current PressurePose T+Pose metric as accuracy. Inspect the images using `visual_review_groups_v2` and treat Txyz as depth-direction initialization only. The next quantitative evaluation should use depth points excluded from all fitting, compare image-space masks/landmarks by body region, and separately audit camera calibration and mesh pose. The T+Pose optimizer must be judged on these independent measures before being retained.

## Files

- `directional_error_by_subject.csv`: signed translation and projection offsets for every participant.
- `directional_error_audit_v1.json`: nearest-anchor residual directions and mesh/cloud centroid/bbox offsets.
- `alignment_diagnostic_v1.json`: point support projection metrics.
- `alignment_diagnostic_summary.json`: cohort summary.
