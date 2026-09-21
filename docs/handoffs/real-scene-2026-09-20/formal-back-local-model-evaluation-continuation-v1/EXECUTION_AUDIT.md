# Execution audit: scientific conclusions withdrawn

Status: INVALID_FOR_CONTROLLED_SCIENTIFIC_COMPARISON. No new inference or large experiment was run for this audit. Existing raw numbers are retained for debugging; they do not establish crop robustness, Cheap Txyz efficacy, pose-specific gain, or a fine-tuning decision.

## 1. FULL is not the historical baseline

Historical oracle_stage_a.py passes original RGB, mask bbox padded by 25 pixels and original K to prepare_batch. The new runner externally crops, non-uniformly resizes to 512x512, uses bbox [0,0,511,511], and supplies effective K before another internal transform. FULL uses 5% padding rather than the historical 25 pixels.

Effective K scales fx and fy separately, which is a valid general pinhole transform. However, the installed official camera_head.py lines 85–96 derives tz and both lateral center corrections using only fx and a scalar bbox size. sam3d_body.py lines 245–281 also normalizes both CLIFF coordinates using fx. Non-uniform resize therefore violates the scalar-focal assumptions in these branches; supplying an algebraically correct effective K does not make the model pipeline equivalent. FULL sx/sy ranges from 1.124 to 3.733 across these frames. The image appearance and bbox metadata are also changed.

This is a concrete preprocessing/decoder contract mismatch and the leading explanation for large FULL errors. Its exact contribution to 486.72 mm has NOT been measured by a controlled replay. Do not attribute the entire difference to one cause yet.

Both implementations set cam_int after prepare_batch and before _initialize_batch, and both add pred_cam_t once to pred_vertices. No new double-addition is evident. V2 camera/world formulas match the official local2world/world2local convention; correcting those formulas alone did not validate the external crop path. The historical 31.36/16.82/13.76 mm figures supplied by the reviewer have not been independently recomputed for the exact 18-frame subset in this audit.

## 2. Txyz fallback is confirmed

| Condition | Fallback | Correction actually applied | Median proposed norm |
|---|---:|---:|---:|
| FULL | 15/18 | 3/18 | 323.02 mm |
| UPPER | 12/18 | 6/18 | 238.75 mm |
| LOCAL_TORSO | 15/18 | 3/18 | 353.90 mm |

Above 177.88820176363325 mm the runner applies zero translation. This is 42/54 condition cases. For these cases Official and Txyz vertices are identical. Yet method-dependent evaluation seeds choose different observed sensor samples and fitted-reference vertices. Their reported metric differences can therefore be sampling artifacts, not geometric improvements. The earlier 3/3 LOCAL Txyz subject improvement claim is not trustworthy.

## 3. O2 was changed without preserving the frozen configuration

| Setting | Historical O2 | New run |
|---|---:|---:|
| Observed K0 points | 1024 | 5000 |
| Anchor stride | 2 | 4 |
| Huber beta | 0.02 m | 0.01 m |
| Translation learning rate | 0.003 | 0.01 |
| Pose learning rate | 0.001 | 0.003 |
| Translation prior coefficient | 0.01 | missing |
| Pose prior coefficient | 0.01 | 0.01 |
| Iterations | 25 | 25 |

The parameter group remained translation + global_rot + body_pose, but the optimizer/objective and discretization did not. These are substantive experimental deviations, not merely memory optimizations. The prior statement that only a memory implementation changed was incorrect.

## 4. Translation rescue cannot be separated from pose gain

The new output stores proposed Txyz and two scalar O2 losses, but neither initial/final O2 cam_t nor final vertices or pose parameters. Consequently the final O2 translation delta cannot be recovered from existing metrics. A translation-only contribution cannot be numerically reported. Large recovery is confounded by zero Txyz application in most cases, a higher translation learning rate, and the missing translation prior. Even saved translation delta alone would not causally isolate pose benefit; controlled matched translation-only and joint updates or fixed-parameter counterfactual evaluation would be needed.

## Additional demonstrated reporting deviation

aggregate_formal.py takes frame medians directly within each subject and omits the required sequence aggregation step. Equal frame counts do not make nested medians equivalent. The reported P95 is a percentile of three subject medians, not a sensor residual P95. The K0-improvement/held-out-degradation count also uses method-dependent samples and should not support the previous overfit conclusion.

## Recommended next diagnostic, not executed here

Use one preselected FULL frame to replay the historical original-RGB/bbox/K path and compare it with a uniform-scale or letterbox crop path. Capture the actual prepared image, bbox center/scale, original image size, intrinsics, CLIFF condition, pred_cam_t and vertices. Validate old baseline recovery first. Restore the frozen O2 configuration, use identical evaluation points across methods, restore sequence aggregation, and retain parameters/vertices before another formal batch. Keep the same timestamps and K0/held-out split. No training decision is warranted by this run.
