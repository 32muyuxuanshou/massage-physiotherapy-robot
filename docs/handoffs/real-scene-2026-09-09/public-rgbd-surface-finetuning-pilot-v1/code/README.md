# Geometry and gradient audit code

This code implements the DEV-only geometry checks for
`PUBLIC_RGBD_SURFACE_FINETUNING_PILOT_V1`. It does not open a sealed test and it
does not claim that surface fine-tuning has completed.

`SURFACE_FINETUNING_READINESS_INPUT_V1.json` is an input to the main task's
readiness decision. Its `READY_FOR_PROTOCOL_FREEZE_NOT_TRAINED` state does not
mean the project has reached final `READY_TO_TRAIN`: the subject split, loss
weights, optimizer budget, validation selection rule and all sealed-test rules
must still be reconciled and frozen by the main task.

`surface_metrics.py` provides three parallel held-out metrics: the V1 nearest
vertex metric, exact nearest triangle-surface distance, and OpenCV-calibrated
rendered depth with overlap coverage. `test_surface_metrics_toy.py` tests triangle
interiors, a 10 mm offset, degenerate faces, and a synthetic plane rendered at
exactly 2 m. These tests use no HuMMan observation.

`audit_surface_gradient_chain.py` runs a read-only forward/backward pass on the
existing five DEV observations. Only `head_pose.proj` and `head_camera.proj` have
`requires_grad=True`; it calls `torch.autograd.grad`, constructs no optimizer,
performs no step and writes no checkpoint. Camera B is never read. A nonzero
gradient proves that a real surface objective can reach the proposed trainable
heads, but does not prove that training will improve held-out subjects.

`run_camera_pose_dev.py` adds the missing Camera+Pose group to the already sealed
V1 per-image fitter without editing its source. It requires exactly five prepared
DEV observations and produces ten fits: Official and V2-E5 for each subject.

`evaluate_dev_ablation.py` evaluates Camera, Pose, Camera+Pose, Shape/Scale and
Combined results using all three metric definitions. It requires exactly five
observations and marks every row `DEV5_ONLY`.

The runtime environment used for verification is the existing SAM 3D Body CUDA
environment on `172.18.18.151`. It contains PyTorch, SciPy, trimesh, pyrender and
OpenCV. The exact point-to-triangle implementation is self-contained and does not
depend on `rtree` or PyTorch3D. EGL is used only for evaluation rendering.

## Governed surface fine-tuning entrypoint

`train_rgbd_surface.py` is the formal pilot entrypoint. It loads the Official
checkpoint only, freezes the full network, and enables exactly
`head_pose.proj` and `head_camera.proj`. Camera-A person-mask depth supplies the
only new supervision. Detached Official predictions preserve the previously
stable 2D and pelvis-relative 3D joints, and an initialization penalty limits
head drift. `vertex_offsets` is unavailable.

The primary checkpoint-selection metric is Camera-B exact point-to-triangle
distance aggregated by subject, with rendered depth and coverage reported as a
secondary diagnostic. Optimizer updates, observation exposures, wall time, peak
CUDA memory and checkpoint hashes are written to `training_report.json`.

The checked-in `../TRAINING_PROTOCOL_V1.json` is frozen for the one-epoch
engineering smoke after final subject split, cache checksum and workset QA
verification. `--mode smoke` is hard-capped to one epoch;
its gate is defined in `../ONE_EPOCH_SMOKE_GATE_V1.json`. A passing smoke proves
execution integrity only and is not evidence of efficacy, deployment readiness,
or SEALED generalization.

## MHR-native synthetic geometry smoke

`generate_mhr_native_synthetic.py` calls the licensed, actual MHR TorchScript
through the current SAM 3D Body head. It saves every input parameter, the shared
36,874-face topology, 18,439 camera-space vertices, RGB, metric Z-depth, mask,
308 keypoints, 127 skeleton joints, visibility, camera K/R/T, seeds and hashes.
Shape and scale are shared by identity; pose and camera vary per sample.

`validate_mhr_native_synthetic.py` independently reloads parameters and regenerates
the mesh. It then backprojects deterministic interior depth pixels and intersects
the corresponding `(u+0.5,v+0.5)` rays with front-facing MHR triangles. The
accepted `smoke100_v2` run passed 100/100 samples: parameter replay maximum was
`4.7684e-7 m`, mesh/depth/backprojection maximum was `0.004506 m` under the
fixed `0.005 m` gate, and reprojection maximum was `2.8422e-14 px`.

`make_mhr_smoke_contact_sheet.py` builds the required RGB | inverse-depth | mask
visual sheet. The smoke validates generator geometry only. Its bounded random
parameters are dominated by near-neutral upright bodies and are not a realistic
complex-pose source; no formal training or 1,000-sample production is authorized
by this result alone. See `../MHR_NATIVE_SYNTHETIC_PROTOCOL_V1.json` and
`../MHR_NATIVE_SYNTHETIC_SMOKE100_V1.json`.

## Non-SEALED RGB-D QA and cache

`qa_cache_nonsealed_workset.py` consumes the selective-extraction plan and the
server `workset_v1`. It refuses SEALED or unplanned subject directories, imports
the preceding handoff's `humman_geometry.py`, computes cam008/cam009 registration
and body-core support metrics, writes server-only NPZ caches, and creates paged
RGB/mask/depth contact sheets. The reported torso region is a geometric body-core
proxy for QA, not an anatomical or clinical label. See
`../NONSEALED_RGBD_QA_CACHE_PROTOCOL_V1.json`.

The final non-SEALED run cached 78 candidate subject/frame pairs and passed all
automatic gates. Six contact-sheet pages covering 156 views passed gross
registration review with minor sensor boundary/floor noise retained in the
record. `FINAL_FROZEN_WORKSET_MANIFEST_V1.json` exposes only TRAIN 45 and VAL 15
samples to the trainer; DEV and SEALED are excluded. The governed dry-run passed
with zero optimizer steps. See `../NONSEALED_RGBD_QA_CACHE_SUMMARY_V1.json` and
`../TRAINING_DRY_RUN_V1.json`.

## Frozen-checkpoint evaluation

`evaluate_official_vs_checkpoint.py` compares Official with one frozen
pose/camera-head checkpoint on a VAL-only or SEALED-only evaluation manifest. It
accepts no TRAIN rows, verifies observation and checkpoint hashes, constructs no
optimizer, and performs no backward pass. In addition to exact point-to-triangle
and rendered-depth subject-macro metrics, it reports bbox-normalized MHR70 2D
joint NME/PCK05 change, pelvis-relative 3D joint change, and camera/pose parameter
sanity. Joint changes are stability proxies against Official predictions, not
ground-truth pose accuracy.
