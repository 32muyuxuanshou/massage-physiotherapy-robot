# PUBLIC RGB-D MHR fitability code

This directory contains the minimum reproducible path for the frozen-network
HuMMan Point experiment. It does not train SAM 3D Body. It fits only per-frame
MHR/camera variables and never enables `vertex_offsets`.

## Contract

- HuMMan `R,T` are used as `X_camera = R @ X_world + T`.
- Depth PNGs are interpreted as uint16 millimetre Z-depth, matching the HuMMan
  Open3D example (`depth_scale=1000`).
- The 640x576 person mask is in the paired depth-camera pixel frame. It selects
  person depth before those points are transformed to the color camera.
- SAM MHR vertices are multiplied by `[1,-1,-1]` exactly as in the official
  wrapper, then `pred_cam_t` is added.
- Camera A supplies RGB initialization and the only fitting depth. Camera B is
  held out until optimization finishes.
- The metric direction is visible observed surface to the full MHR surface.
  It is intentionally one-sided because visibility-aware mesh rasterization is
  not part of this first sanity test.
- Person masks include clothing. Results describe clothed/person-surface
  fitability and cannot establish bare-back skin accuracy.

## Environment

Use the same CUDA environment that already runs the official SAM 3D Body
repository. Extra runtime packages are `opencv-python`, `numpy`, `scipy`, and
PyTorch. The fitter loads the official checkpoint only to obtain the frozen MHR
module; V2 differences enter through separately cached initialization parameters.

## Run

The executed five-subject split is frozen in `approved_subset.json` after RGB
and registration-overlay review. `example_subset.json` is only a schema example.

```bash
python prepare_observations.py \
  --data-root /data/humman_subset \
  --manifest approved_subset.json \
  --output-dir /run/public_rgbd/prepared

python validate_registration.py \
  --observation /run/public_rgbd/prepared/p000823_a000035_f000016.npz \
  --view a \
  --output-image /run/public_rgbd/registration_a.png \
  --output-json /run/public_rgbd/registration_a.json

python cache_sam_predictions.py \
  --sam-repo /raid5/xuhd/sam3d_s01_pilot_20260906/sam-3d-body \
  --checkpoint /raid5/xuhd/sam3d_s01_pilot_20260906/weights/model.ckpt \
  --mhr /raid5/xuhd/sam3d_s01_pilot_20260906/weights/assets/mhr_model.pt \
  --prepared-manifest /run/public_rgbd/prepared/prepared_manifest.json \
  --output-dir /run/public_rgbd/predictions --model-tag official

python cache_sam_predictions.py \
  --sam-repo /raid5/xuhd/sam3d_s01_pilot_20260906/sam-3d-body \
  --checkpoint /raid5/xuhd/sam3d_s01_pilot_20260906/weights/model.ckpt \
  --mhr /raid5/xuhd/sam3d_s01_pilot_20260906/weights/assets/mhr_model.pt \
  --prepared-manifest /run/public_rgbd/prepared/prepared_manifest.json \
  --output-dir /run/public_rgbd/predictions --model-tag v2_e5 \
  --v2-heads /raid5/xuhd/nlf_pilot_20260908/visible_ab_v2/heads_epoch5.pt

python fit_mhr.py \
  --sam-repo /raid5/xuhd/sam3d_s01_pilot_20260906/sam-3d-body \
  --checkpoint /raid5/xuhd/sam3d_s01_pilot_20260906/weights/model.ckpt \
  --mhr /raid5/xuhd/sam3d_s01_pilot_20260906/weights/assets/mhr_model.pt \
  --observation /run/public_rgbd/prepared/p000823_a000035_f000016.npz \
  --prediction /run/public_rgbd/predictions/p000823_a000035_f000016__official.npz \
  --output /run/public_rgbd/results/p000823__official__combined.json \
  --model-tag official --group combined
```

Run `fit_mhr.py` freshly for each of `camera`, `pose`, `shape_scale`, and
`combined`, for both `official` and `v2_e5`. It reinitializes parameters from the
cached feed-forward result each time. Then summarize all result JSONs:

```bash
python summarize_results.py /run/public_rgbd/results/*.json \
  --output /run/public_rgbd/MHR_FITABILITY_DECISION_V1.json
```

The automatic summary can issue PASS only from a majority of at least three
combined-fit subjects whose held-out median improves by at least 10% while all
pre-registered parameter limits pass. An inconclusive result must be diagnosed;
this code deliberately does not convert it directly into a representation failure.

## Required manual checks before accepting a run

1. Inspect both registration overlays and reject visibly misregistered pairs.
2. Confirm Camera A and B are distinct synchronized devices at one timestamp.
3. Confirm the selected torso/back is visible and depth is not dominated by loose clothing.
4. Inspect refined meshes and parameter deltas; low distance alone is insufficient.
5. Aggregate by subject. Depth pixels are observations, not independent subjects.

Current limitation: point-to-plane and region-specific back metrics are deferred
until reliable normals/body-part labels are verified. That limitation should remain
explicit in the final decision rather than being hidden by a looser gate.
