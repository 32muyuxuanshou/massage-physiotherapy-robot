# V1.4 review index

Start with [README_PREEXECUTION_REPRO_FIX_V1_4_SCIENTIFIC_CHAIN_FINAL.md](README_PREEXECUTION_REPRO_FIX_V1_4_SCIENTIFIC_CHAIN_FINAL.md).

## Four blocking fixes

1. Actual Run A assets: `repro_fix/run_a_freeze.py`, `RUN_A_ASSET_FREEZE_V1.json`, `tests/test_scientific_chain_v14.py::test_01_run_a_actual_npz_mutation_stops`.
2. Formal point-cloud binding: `POINTCLOUD_FORMAL_BINDING_SPEC_V1_4.json`, `repro_fix/formal_identity.py`, `repro_fix/pointcloud_manifest.py`, `repro_fix/pointcloud_repro_runner.py`.
3. SAM-to-Txyz chain: `SAM_COHORT_TXYZ_SPEC_V1_4.json`, `repro_fix/sam_cohort_txyz_runner.py`, and the `sam_cohort_txyz` stage in `repro_fix/run_reproducibility_isolation_v1.py`.
4. Exact feature coverage: `FEATURE_STABILITY_CONTRACT_V1_4.json`, `repro_fix/txyz_fresh_process_runner.py`, `repro_fix/k0_data_features.py`, `repro_fix/feature_stability_runner.py`.

## Three execution protections

1. Full input identity: `SAM3D_REPRODUCIBILITY_SPEC_V1_4.json` and `repro_fix/sam_repro_analyzer_v2.py`.
2. Start/end integrity: `POST_EXECUTION_INTEGRITY_SPEC_V1_4.json` and `post_execution_integrity()` in the master.
3. Clean evidence directory: `require_clean_output_root()` in the master and `EXECUTION_CONFIG_SCHEMA_V1_4.json`.

## Formal contracts

- `MASTER_ORCHESTRATION_SPEC_V1_4.json`
- `EXECUTION_CONFIG_SCHEMA_V1_4.json`
- `EXECUTION_CONFIG_TEMPLATE_V1_4.json`
- `RUNTIME_ASSET_FREEZE_V1_4.json`
- `SAM_REPRODUCIBILITY_EVIDENCE_BOUNDARY_V1_4.json`
- `SAM3D_REPRODUCIBILITY_SPEC_V1_4.json`
- inherited model-load, point-cloud, exact-input Txyz, environment and frame-order contracts included in this directory

## Verification evidence

- `PURE_CODE_TEST_REPORT_V1_4_SCIENTIFIC_CHAIN_FINAL.txt`
- `PREFLIGHT_RESULT_V1_4_SCIENTIFIC_CHAIN_FINAL.json`
- `FILES_MANIFEST.json`
- `REVIEW_DIFF_SUMMARY_V1_4.json`

No formal 45-frame experiment was executed in this delivery.
