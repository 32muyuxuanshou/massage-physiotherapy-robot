# PREEXECUTION_FIX_REPRO_ISOLATION_V1_3_INTEGRATION_FINAL

Status: `HOLD_FOR_WEB_REVIEW_SAM3D_TXYZ_REPRODUCIBILITY_ISOLATION_V1_3_INTEGRATION_FINAL`.

This delivery repairs five integration gaps found in `ba5fb55`. It contains the complete V1.2 contracts and implementation plus the V1.3 evidence boundary, runtime asset verification, formal master orchestrator, official-output adapters, tests, reports and hashes. It does not run the formal experiment.

## Historical evidence boundary

Historical reconstructed Run A from `d0ce44c` contains only frozen points and anchors. It does not contain historical full MHR vertices, `pred_cam_t`, prepared tensors, `cam_int`, model-state fingerprints, or the original six-iteration V2.3 Txyz trace. No code can recover data that was not saved.

Accordingly, Run A is used only as the historical anchor and reconstructed-Txyz reference. `sam_repro_analyzer_v2.py` compares its verified anchors with new runs. A new controlled `RUN_B` through `RUN_F` cohort is compared pairwise for vertices, camera translation, anchors, prepared tensors, `cam_int`, model state and environment. A new run can never replace historical Run A.

The final claim is limited to stability of the reconstructed Run A diagnostic features. It cannot claim that those features are byte-identical to the internal state of the 2026-09-11 V2.3 execution.

## Integrated formal path

`run_reproducibility_isolation_v1.py` is the only recognized formal entry. It requires the exact GO token and enforces this fail-closed order:

1. Runtime asset hashes and Run A freeze.
2. Controlled input snapshot for all RGB/mask sources.
3. Unseeded and controlled model-load audits.
4. Five-process point-cloud gate.
5. Same-process and fresh-process exact-input Txyz gates.
6. Controlled SAM B-F cohort and two-layer analysis.
7. Three-process frame-order execution and analysis.
8. Outcome-blind feature-stability characterization.

Every stage writes an execution ledger entry. Any nonzero process result or unexpected Gate status stops later stages.

The parent fixes `CUBLAS_WORKSPACE_CONFIG`, `PYTHONHASHSEED`, `OMP_NUM_THREADS`, and `MKL_NUM_THREADS` before child startup. Each SAM child embeds a full environment fingerprint. Each frame records model-state fingerprints before and after inference, allowing the analyzer to distinguish input mismatch, model-state mutation and frame-order dependence.

## Scientific boundary

V2.3 remains a **dataset-mask-assisted RGB-D evaluation** because BEHAVE person masks provide both the K0 depth filter and SAM bbox. It is not raw RGB-D deployment validation. Target-sensor depth scale, noise, holes, calibration, segmentation and bed/contact effects remain pending.

Back work remains `BLOCKED_PENDING_BACK_REGION_DEFINITION`. Whole-body 17.8 mm is not back accuracy, DMD37 accuracy, or medical acupoint accuracy.

V2.3 (`230d91b`), frozen Cheap Txyz, parity-failed evidence (`d0ce44c`) and the old parity threshold are unchanged.
