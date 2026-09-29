# T+Pose alignment discrepancy review

All 20 participants are included. Every row shows RGB and the three mesh overlays. Grouping compares T+Pose against Txyz using a projected point-cloud support diagnostic: `TPOSE_2D_WORSE` contains cases where 3D median improved but 2D support IoU fell; `TPOSE_2D_BETTER` contains cases where both improved. Numbers are printed above every row; ¦¤3D = T+Pose minus Txyz (mm), ¦¤IoU = T+Pose minus Txyz.

The 2D mask is the projected official filtered K0 person point cloud dilated by 3 px, not manual GT. It is a diagnostic only. The 3D residual uses same-source points and is not independent accuracy. Full method and limitations: see `../full_run/EVALUATION_AUDIT.md`. Per-subject values: `INDEX.csv`.
