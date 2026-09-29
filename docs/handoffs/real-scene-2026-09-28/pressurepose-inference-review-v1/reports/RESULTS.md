# PressurePose prone three-method inference results

Status: COMPLETE (20/20 participants). Training: False.

**Evaluation meaning:** fit consistency between each participant’s mesh and the same K0 depth-derived person point cloud used in the input. It is not independent sensor validation, ground-truth mesh accuracy, or acupoint accuracy. Each participant contributes one `p_sel_prn` frame. Summary uses participants equally.

| Method | Median of participant medians (mm) | Mean of participant medians (mm) | Median participant P95 (mm) | Median coverage ≤50 mm |
|---|---:|---:|---:|---:|
| Official | 124.55 | 126.19 | 187.89 | 6.7% |
| Official+Txyz | 17.28 | 64.87 | 62.81 | 90.5% |
| Official+Txyz+Pose | 9.76 | 35.81 | 48.08 | 95.5% |

Txyz improved participant median versus Official for 15/20 participants. T+Pose improved versus Txyz for 20/20. Cheap Txyz hit the frozen total-translation fallback for 5/20: S104, S134, S140, S141, S187.

Per-participant results are in `per_subject_metrics.csv`; raw JSON and mesh parameters remain under `subjects/`. Contact sheets show RGB followed by the three predictions. No subjects were dropped.

## Frozen settings

Txyz: `{"iterations": 6, "step_m": 0.05, "total_bound_m": 0.17788820176363326, "trim_fraction": 0.2}`
T+Pose: `{"anchor_stride": 2, "huber_beta_m": 0.02, "iterations": 25, "lambda_pose": 0.01, "lambda_translation": 0.01, "lr_pose": 0.001, "lr_translation": 0.003, "observed_points": 1024}`

## Limits

This is an inference-only engineering comparison on 20 prone images. All methods use the same single-view K0 input and the same K0-derived point cloud for both fitting and evaluation. Txyz uses the full point cloud for correction; T+Pose optimizes on 1,024 sampled points; evaluation draws 10,000 points from the same point-cloud pool, with no disjoint split enforced. The reported fit metrics therefore measure same-source fit consistency and are not independent accuracy estimates. The result cannot establish performance with independent depth, across cameras, across time, or clinical/acupoint localization. Five subjects hit the frozen Txyz translation fallback (S104, S134, S140, S141, S187); these cases remain in all summaries. T+Pose also optimizes translation, global rotation, and body pose, so its gain cannot be attributed to pose alone.

Runtime: Python 3.10.20, PyTorch 2.4.0+cu121, CUDA 12.1, NVIDIA RTX 2080 Ti (GPU 0). The SAM 3D Body source folder did not contain Git metadata; its full tree SHA256 and file count are recorded in `EXECUTION_MANIFEST.json`.
