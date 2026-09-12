# POST_TXYZ_RESIDUAL_AND_FAILURE_AUDIT_V1 — Pre-execution

Current gate: `HOLD_FOR_WEB_REVIEW_POST_TXYZ_AUDIT_V1`.

The immutable V2.3 baseline passed on 45 frames from five fresh BEHAVE subjects: subject-equal median surface error changed from 31.17 mm to 17.80 mm after frozen all-points Cheap Txyz. This new package prepares a descriptive residual and failure audit. It does not modify V2.3, tune Txyz, run SAM3D, replay Txyz, run the formal 45-frame audit, or train a confidence model.

Deployment candidate features are restricted to K0. K1/K2/K3 appear only as offline outcome labels. `leakage_audit.py` rejects any held-out source marked deployment-available. Missing features remain explicitly unavailable or replay-required; no missing value is silently replaced by zero.

The repository does not contain a frozen, independently justified MHR back vertex/face region suitable for formal back-only accuracy. Existing DMD37 and torso assets are engineering/model-linked definitions and are not independent medical or back-surface ground truth. Back metrics therefore fail closed with `BLOCKED_PENDING_BACK_REGION_DEFINITION`.

The formal manifest covers 45 frames, five subjects, 15 sequences and all four camera roles, and explicitly retains `Date06_Sub07_stool_sit/t0038.000`. Its presence is a completeness condition, not permission to tune around that frame.
