# Review index

Start with [README_PREEXECUTION_REPRO_FIX_V1_3_INTEGRATION_FINAL.md](README_PREEXECUTION_REPRO_FIX_V1_3_INTEGRATION_FINAL.md).

## The five reviewed fixes

1. Historical/new evidence separation: `SAM_REPRODUCIBILITY_EVIDENCE_BOUNDARY_V1_3.json`, `SAM3D_REPRODUCIBILITY_SPEC_V1_3.json`, `repro_fix/sam_repro_analyzer_v2.py`.
2. Frame-order integration: `FRAME_ORDER_EXECUTION_SPEC_V1_3.json`, `repro_fix/frame_order_execution_runner.py`, `repro_fix/frame_order_analyzer.py`, and per-frame fingerprints in `repro_fix/sam_repro_runner.py`.
3. Master Gate: `MASTER_ORCHESTRATION_SPEC_V1_3.json`, `EXECUTION_CONFIG_SCHEMA_V1_3.json`, `EXECUTION_CONFIG_TEMPLATE_V1_3.json`, `repro_fix/run_reproducibility_isolation_v1.py`.
4. Runtime assets: `RUNTIME_ASSET_FREEZE_V1_3.json`, `repro_fix/runtime_asset_verifier.py`, `repro_fix/input_source_snapshot.py`.
5. Environment evidence: `repro_fix/environment_fingerprint.py` and embedded `environment_fingerprint` in every SAM child output.

## Inherited core contracts

The V1.2 Feature Stability, Txyz, point-cloud, model-load and environment contracts are included unchanged except where the V1.3 integration requires a stricter formal entry. The 45-frame Run A freeze is `RUN_A_ASSET_FREEZE_V1.json`.

## Verification

Read `PURE_CODE_TEST_REPORT_V1_3_INTEGRATION_FINAL.txt`, `PREFLIGHT_RESULT_V1_3_INTEGRATION_FINAL.json`, and `FILES_MANIFEST.json`. No formal experiment outputs are present because this delivery remains pre-execution.
