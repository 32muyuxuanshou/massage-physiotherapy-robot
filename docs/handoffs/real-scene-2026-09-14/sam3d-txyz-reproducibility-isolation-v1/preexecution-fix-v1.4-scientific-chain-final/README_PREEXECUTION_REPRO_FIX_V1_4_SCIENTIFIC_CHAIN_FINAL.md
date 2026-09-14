# PREEXECUTION_FIX_REPRO_ISOLATION_V1_4_SCIENTIFIC_CHAIN_FINAL

Status: `HOLD_FOR_WEB_REVIEW_REVIEWED_DELIVERY_INTEGRITY_V1_4_1`.

This is a complete review snapshot based on V1.3. It repairs the four final scientific-chain blockers and the three related execution protections identified in the review of commit `08e5d87`. It contains code, contracts, tests, preflight evidence and file hashes. It does not contain or claim a formal experiment result.

V1.4.1 adds the one execution-integrity patch requested after commit `9061f0d`. The master now requires Git `HEAD` to equal the commit referenced by the fixed tag `sam3d-txyz-repro-v1.4.4`, and requires this entire delivery directory to have no tracked, staged or untracked changes. The same check runs again inside post-execution integrity. This binds the reviewed Python, all JSON scientific contracts, freezes, reports and `FILES_MANIFEST.json` without changing any algorithm, feature, threshold, sample or statistic.

## Review assessment

All four blocking findings were correct.

1. V1.3 trusted hash strings in the replay manifest instead of reopening the 45 points NPZ and 45 anchors NPZ files. The formal gate now hashes all 90 files and stops with `RUN_A_ACTUAL_ASSET_HASH_MISMATCH` on any difference.
2. The point-cloud manifest was an independent, unfrozen configuration input. V1.4 removes it from the configuration. The master derives it from the frozen formal 45-frame manifest, the sequence root and frozen K0 calibration assets, then freezes exact frame IDs, canonical paths and file hashes.
3. V1.3 characterized repeated Cheap Txyz execution on exact historical inputs. That establishes exact-input determinism but does not establish diagnostic stability under SAM reruns. V1.4 adds `sam_cohort_txyz`: identical verified K0 points are fit separately with anchors from controlled runs B, C, D, E and F. Run A is retained only as a historical reconstructed reference.
4. V1.3 implemented only part of the registered feature contract. V1.4 computes every registered translation, iteration, convergence, direction, oscillation, residual, depth-support, count and provenance feature. The runner requires exact equality between the contract feature set and extractor feature set before it can return `PASS_FEATURE_STABILITY_CHARACTERIZATION`.

The three related findings were also correct and are included: complete SAM input identity comparison, post-execution integrity verification, and a new-or-empty output-root gate.

## Historical evidence boundary

Historical reconstructed Run A from `d0ce44c` contains only points and anchors. It does not contain historical full MHR vertices, `pred_cam_t`, prepared tensors, `cam_int`, model-state fingerprints, or the original six-iteration V2.3 Txyz trace. No code can recover data that was not saved.

Run A is therefore used as an anchors-only SAM comparison and a separately reported reconstructed Txyz reference. Primary feature stability is computed only across the new controlled B-F cohort. No new run replaces Run A, and this delivery makes no claim of byte identity with unsaved V2.3 internals.

## Formal execution chain

The only recognized formal entry remains `python -m repro_fix.run_reproducibility_isolation_v1` with the exact GO token. The output directory must be outside this reviewed delivery and must be new or empty. The fail-closed sequence is:

1. Verify the complete reviewed delivery against the fixed Git tag and clean path-scoped worktree.
2. Verify external runtime assets and the delivered reproducibility code tree.
3. Reopen and hash all 45 Run A points NPZ and 45 anchors NPZ files.
4. Freeze 45 K0 RGB/mask inputs.
5. Derive and freeze the 45-frame K0 point-cloud manifest.
6. Run model-load, point-cloud, exact-input Txyz, controlled SAM and SAM pairwise gates.
7. Pass B-F anchors through frozen Txyz with identical K0 points.
8. Run frame-order execution and analysis.
9. Characterize every registered diagnostic feature across B-F.
10. Reverify runtime assets, Run A files, controlled inputs, formal manifest, point-cloud binding and start/end snapshot hashes.
11. Reverify the reviewed Git commit and clean delivery directory before granting final PASS.

Any nonzero child process, unexpected stage status, feature-contract coverage gap or post-execution integrity mismatch stops the chain.

The V1.4.1 verification suite contains 88 tests. It includes the requested mutation checks for the feature contract, frame-order spec and Run A freeze, a normal reviewed-delivery PASS case, a wrong-HEAD rejection, and an output-inside-delivery rejection.

## Diagnostic definitions

The added Txyz diagnostics do not change the fitted translation. They record values already produced by the frozen six-iteration process: initial raw residual median; final retained residual MAD, P90 and P95; step convergence ratio; consecutive-step cosine consistency; sign-reversal oscillation; step vectors; trim threshold and correspondence counts. K0 depth-support fields use the frozen person mask and depth image. Left/right and top/bottom balance are signed ratios in `[-1, 1]`, corrected from the earlier incorrect `[0, 1]` type label.

## Scientific boundary

This remains dataset-mask-assisted BEHAVE RGB-D evaluation. It is not raw RGB-D deployment validation. Back-region, DMD37 and medical acupoint conclusions remain outside this experiment. V2.3 (`230d91b`), historical evidence (`d0ce44c`) and the frozen Cheap Txyz algorithm are unchanged.
