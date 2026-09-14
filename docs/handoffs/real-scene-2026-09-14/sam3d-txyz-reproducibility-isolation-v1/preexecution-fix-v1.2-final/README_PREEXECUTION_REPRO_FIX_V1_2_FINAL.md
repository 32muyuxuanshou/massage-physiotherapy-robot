# PREEXECUTION_FIX_REPRO_ISOLATION_V1_2_FINAL

Status: `HOLD_FOR_WEB_REVIEW_SAM3D_TXYZ_REPRODUCIBILITY_ISOLATION_V1_2_FINAL`.

This delivery closes the remaining spec/code gaps before the formal reproducibility experiment. It does not run the 45-frame experiment and does not modify V2.3 (`230d91b`), frozen Cheap Txyz, canonical reconstructed Run A (`d0ce44c`), or the old parity threshold.

`VECTOR_MM` is evaluated component by component for every iteration: x, y, z and vector norm each receive the full scalar statistics and ICC(A,1), and the vector receives the worst component status. Stability classification cannot accept held-out K1/K2/K3 errors, A/B/C/D labels, or failure identities.

Txyz now has same-process and fresh-process runners plus first-divergence hash analysis. SAM Run B-E records complete input identity including `cam_int`, model-state fingerprints, numeric output arrays, and supports controlled and unseeded model-load modes. The analyzer freezes Run A and computes vertices, anchors and camera-translation drift. The frame-order runner launches three model processes; each loads one model and processes all seven unique sentinels sequentially. Point-cloud gating compares the complete raw/decoded/table/points chain.

The formal runners require an explicit post-review authorization flag. Pure/mock tests do not process the 45 real frames.

Scientific scope remains **dataset-mask-assisted RGB-D evaluation** because BEHAVE person masks drive depth filtering and the SAM bbox. It is not raw RGB-D deployment validation. Target-sensor depth scale, noise, holes, calibration, segmentation and bed/contact effects remain pending. Back work remains `BLOCKED_PENDING_BACK_REGION_DEFINITION`; the whole-body 17.8 mm result is not back, DMD37, or medical acupoint accuracy.
