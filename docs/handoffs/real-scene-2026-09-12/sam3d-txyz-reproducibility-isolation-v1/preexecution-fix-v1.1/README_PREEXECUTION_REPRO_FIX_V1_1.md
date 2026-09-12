# PREEXECUTION_FIX_REPRODUCIBILITY_ISOLATION_V1_1

Status: `HOLD_FOR_WEB_REVIEW_SAM3D_TXYZ_REPRODUCIBILITY_ISOLATION_V1_1`.

This delivery repairs the reproducibility-isolation implementation without running the formal 45-frame experiment. V2.3 at commit `230d91b`, Cheap Txyz, and the failed parity evidence at `d0ce44c` are unchanged.

The feature contract separates distance, ratio, count, boolean, vector, and byte-identity features. Continuous features report per-frame min/max/range/mean/SD/median/MAD, between-frame SD, within/between variance ratio, and a real ICC(A,1) using the documented McGraw-Wong absolute-agreement formula. Classification rejects held-out outcome input. Only `STABLE` features may later enter failure-indicator analysis.

The Txyz, model-load, SAM, and point-cloud runners use new Python subprocesses. Txyz records real contiguous ndarray SHA256 values for translation and every iteration's nearest indices, distances, keep mask, retained residual, and step. `workers=-1` remains the baseline; `workers=1` is diagnostic only. The model auditor loads a real model object, inspects parameters/buffers, classifies missing keys from those objects, fingerprints the complete state, and hard-blocks unexplained missing trainable state or cross-process fingerprint changes.

The SAM runner freezes Run A as reconstructed canonical evidence and creates Run B-E in independent processes. It hashes raw and decoded RGB/mask, exact bbox bytes, actual prepared tensor data, vertices, camera translation, and anchors. Canonical reselection is prohibited. The point-cloud runner reconstructs from depth, mask, table and calibration provenance in five independent processes and requires byte-identical output.

The frame-order contract contains 7/7 unique frames and three frozen orders. `RUN_A_ASSET_FREEZE_V1.json` freezes the 45-frame replay manifest plus per-frame and aggregate points/anchors hashes.

Scientific boundaries remain unchanged: V2.3 is a **dataset-mask-assisted RGB-D evaluation**, because the BEHAVE person mask supplies the K0 depth filter and SAM bbox. It is not a raw RGB-D deployment result. Real target-sensor intrinsics, depth scale, holes, edge noise, temporal noise, segmentation, bed and contact remain pending under the existing real-sensor validation specification. Back-specific work remains `BLOCKED_PENDING_BACK_REGION_DEFINITION`; whole-body 17.8 mm is not back, DMD37, or medical acupoint accuracy.

No formal 45-frame SAM B-E run, five-process formal point-cloud run, 20-run formal Txyz experiment, feature characterization, or frame-order experiment was executed in this delivery.
