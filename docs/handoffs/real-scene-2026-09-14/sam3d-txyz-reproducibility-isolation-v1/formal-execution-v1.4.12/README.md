# SAM3D → Txyz reproducibility formal execution V1.4.12

## Final decision

The formal execution completed with `PASS_REPRODUCIBILITY_ISOLATION_EXECUTION`. Runtime assets, controlled inputs, pointcloud binding, reviewed delivery, and post-execution integrity all passed.

The controlled SAM B–F cohort is exactly reproducible when each run uses the same frozen input, environment, seed, and frame order: all 450 pairwise comparisons have zero vertex, anchor, and camera-translation drift and exact hashes.

A separate seven-frame order test detected floating-point frame-order dependence in 6 of 21 pairwise frame comparisons across three frames. The largest vertex displacement is 0.000999 mm and the largest anchor displacement is 0.000919 mm. Inputs and model state hashes are equal, so this is an extremely small numerical order effect rather than input substitution or model mutation. It is reported as a registered scientific result and does not invalidate the B–F fixed-order reproducibility result.

All 27 preregistered downstream Txyz features were classified STABLE; none were CAUTION or UNSTABLE.

## Requested artifacts

- `execution_ledger.json`: final execution ledger.
- `reviewed_delivery_integrity_pre.json` and `reviewed_delivery_integrity_resume_pre.json`: reviewed-delivery pre/resume gates.
- `runtime_asset_verification.json`: frozen runtime assets.
- `model_unseeded.json` and `model_controlled.json`: five fresh-process model-load audits for each mode.
- `pointcloud.json` and `pointcloud_manifest_frozen.json`: pointcloud reproducibility and formal binding.
- `txyz_same.json` and `txyz_fresh.json`: 45 frames × 20 repeats in each execution mode; no divergence.
- `sam/RUN_B.json` through `sam/RUN_F.json`, `sam/coordinator.json`, and `sam/analysis.json`: controlled cohort metadata and B–F analysis.
- `sam_cohort_txyz.json`: SAM→Txyz diagnostic propagation.
- `frame_order/*.json`: three execution orders and comparison analysis.
- `feature_stability.json`: full 27-feature stability characterization.
- `post_execution_integrity.json`: reviewed delivery, assets, Run A, inputs, and pointcloud post-run gate.
- `resume_completed_artifacts_sha256.json`: hashes binding completed stages before continuation.
- `SHA256SUMS.json`: hashes of this Git delivery.

Large per-frame NPZ arrays remain on the server and are bound by hashes recorded in the JSON metadata. They are excluded from Git because the JSON audit package is sufficient to reproduce identity and review the conclusions.

## Execution identity

- Reviewed code tag: `sam3d-txyz-repro-v1.4.12`
- Reviewed code commit: `25d3d40a`
- Server result root: `/raid5/xuhd/sam3d_txyz_repro_v147_formal_20260914/results`
- Server metadata archive: `/raid5/xuhd/sam3d_txyz_repro_v1412_metadata.tgz`
- Metadata archive SHA256: `70e417de411cc34a363655ef3d379f9baeac9518af325be1afc829d63ff1756a`
- Formal cohort: 45 frames.
- SAM controlled runs: B–F, 225 inferences.
- Pointcloud reconstruction: 5 fresh processes.
- Txyz same-process: 45 × 20.
- Txyz fresh-process: 45 × 20.
- Frame-order test: 3 orders × 7 frames.

