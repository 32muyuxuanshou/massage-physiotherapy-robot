# Mesh fit metric audit

## Finding

The previous “GOOD / MIXED / BAD” group names are withdrawn. They classified samples using the same-source 3D point-to-triangle metric, which was too strong an interpretation. Use `visual_review_groups_v2` instead.

The code computes a one-sided exact distance: for each observed point, distance to its nearest mesh triangle; then summarizes median/P95. It does not check mesh-to-point coverage, image silhouette, corresponding anatomical regions, or whether the mesh remains visually aligned. Cheap Txyz uses the full point cloud; T+Pose optimizes 1,024 points; evaluation samples 10,000 points from the same pool without a disjoint split. Therefore a lower score is expected when the mesh is optimized against those points and is not evidence of independent accuracy.

## Diagnostic comparison

Across all 20 subjects, T+Pose reduced the reported 3D median relative to Txyz in 20/20 subjects. A separate 2D support diagnostic compared rendered silhouettes to the projected K0 filtered person cloud (3-pixel dilation; not manual segmentation): T+Pose IoU was worse than Txyz in 14/20 subjects and better in 6/20.

| 2D support metric | Official median / mean | Txyz median / mean | T+Pose median / mean |
|---|---:|---:|---:|
| Projected support IoU (3px dilation) | 0.692 / 0.692 | 0.763 / 0.760 | 0.774 / 0.748 |
| Projected depth-point coverage | 0.771 / 0.772 | 0.854 / 0.843 | 0.871 / 0.843 |

The 2D diagnostic still uses the same filtered point cloud and camera calibration, so it is supporting evidence only. It does, however, show why the 3D score alone is insufficient: 14 subjects have lower 3D residual but worse projected support IoU after T+Pose.

## Correct conclusion

The reported 3D number is mathematically valid for one-sided point-to-surface fit, but the experiment design is not a valid held-out accuracy evaluation and the number cannot justify “good alignment.” The visual concern is credible. The next evaluation should freeze optimizer inputs, score strictly disjoint depth points, add per-region/landmark or manually reviewed image-space alignment, and report symmetric surface coverage. Do not use the old “good” label as a conclusion.
