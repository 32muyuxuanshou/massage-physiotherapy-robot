# POST_TXYZ_RESIDUAL_AND_FAILURE_AUDIT_V1 — Pre-execution

Current gate: `HOLD_FOR_WEB_REVIEW_POST_TXYZ_AUDIT_V1_2`.

The immutable V2.3 baseline passed on 45 frames from five fresh BEHAVE subjects: subject-equal median surface error changed from 31.17 mm to 17.80 mm after frozen all-points Cheap Txyz. This new package prepares a descriptive residual and failure audit. It does not modify V2.3, tune Txyz, run SAM3D, replay Txyz, run the formal 45-frame audit, or train a confidence model.

Deployment candidate features are restricted to K0. K1/K2/K3 appear only as offline outcome labels. `leakage_audit.py` rejects any held-out source marked deployment-available. Missing features remain explicitly unavailable or replay-required; no missing value is silently replaced by zero.

The repository does not contain a frozen, independently justified MHR back vertex/face region suitable for formal back-only accuracy. Existing DMD37 and torso assets are engineering/model-linked definitions and are not independent medical or back-surface ground truth. Back metrics therefore fail closed with `BLOCKED_PENDING_BACK_REGION_DEFINITION`.

The formal manifest covers 45 frames, five subjects, 15 sequences and all four camera roles, and explicitly retains `Date06_Sub07_stool_sit/t0038.000`. Runtime preflight requires exact equality between this manifest, the frozen V2.3 manifest, and V2.3 per-frame results.

V1.1 keeps formal execution locked. `--dry-run` cannot be combined with `--execute-formal`; formal execution additionally requires the exact token `GO_POST_TXYZ_RESIDUAL_FAILURE_AUDIT_V1`, an explicit BEHAVE sequence root, and a complete 45-frame replay-feature file. No token is included in routine dry-run commands.

The 17 diagnostic fields now have executable acquisition paths. Six depth/support fields read only K0 depth and person masks. Eleven convergence/residual fields are emitted by `replay_feature_export.py`, which instruments the frozen six-iteration, 20%-trimmed Cheap Txyz update without changing its parameters. Formal execution rejects missing frame IDs or missing diagnostic values. Failure bundles resolve actual K0 files beneath the supplied sequence root and never invent repository-relative data paths.

The immutable guard hashes every file under `results-v2.3/` before and after preflight/formal execution. Deployment features use a fail-closed camera whitelist: their source must equal `K0`.

V1.2 binds every replay input to SHA256-verified point/anchor NPZ files and records K0 depth, mask and calibration provenance plus Official SAM3D mesh/anchor provenance. Formal execution rechecks these sources, then requires replay translation to match the frozen V2.3 `Txyz_m` within `<1e-6 m` per component and fallback to match exactly for all 45 frames.

Before any formal output, the runtime gate rehashes the frozen formal manifest, original V2.3 `run_generalization_v2.py`, 16,384-anchor asset and the 20 calibration files used by Date03/05/06. The calibration bundle hash was obtained read-only from server `172.18.18.151`; it covers four intrinsic JSON files, four pointcloud tables and twelve date-specific extrinsic JSON files. Any mismatch stops with `ASSET_FREEZE_MISMATCH`.

The replay diagnostics additionally expose the final trim threshold, retained count and raw correspondence count. Group summaries now aggregate six-step vectors per iteration and report rates for boolean features such as oscillation and fallback.
