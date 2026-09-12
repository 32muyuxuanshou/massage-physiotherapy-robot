# SAM3D–Txyz reproducibility isolation V1 — PRE-EXECUTION

Gate: `HOLD_FOR_WEB_REVIEW_SAM3D_TXYZ_REPRODUCIBILITY_ISOLATION_V1`.

This package designs four isolated reproducibility experiments without running them: K0 depth/mask point-cloud reconstruction, Official SAM3D model loading and output, exact-input Cheap Txyz, and environment/order effects. V2.3, preexecution V1.2 and the failed parity attempt remain read-only.

The first reconstructed run from commit `d0ce44c` is frozen as `RECONSTRUCTED_REPLAY_RUN_A`. It was a reconstructed rerun using frozen V2.3 Official SAM3D inputs/assets. Original V2.3 did not save complete MHR vertices, anchors or iteration diagnostics, so exact historical six-iteration identity cannot be established afterward. Run A remains canonical and later runs cannot replace it based on closeness to V2.3.

The model-load experiment captures the official `strict=False` missing/unexpected keys and classifies every missing key. Any unloaded trainable parameter that remains randomly initialized, or any varying model-state fingerprint, is a hard blocker.

No 45-frame experiment, repeated SAM inference, failure audit, mask experiment or sensor experiment was run. Cheap Txyz parameters were not changed. Back-specific analysis remains `BLOCKED_PENDING_BACK_REGION_DEFINITION`.
