# Audit specification V1

For each frame, recompute the held-out label from K1/K2/K3 median point-to-triangle errors. A/B/C/D mean 3/2/1/0 cameras improved. These labels support descriptive comparisons only and can never enter deployment logic.

K0 candidates cover frozen translation and runtime fields already saved. Six support/depth fields are read directly from K0 depth and person masks. Eleven convergence/residual fields come from instrumentation of the frozen Txyz replay. Object contamination remains unavailable until a reliable frozen source exists. A formal audit requires complete K0 data and replay features for the exact 45-frame identity set; partial diagnostic output is rejected. The single D-group frame makes all candidate indicators hypothesis-generating. No classifier, statistical-significance claim, or threshold chosen on these 45 frames is allowed.

Root-cause output is a list of candidates with evidence, qualitative confidence and mandatory visual review. Code must not assert pose, shape, local surface, interaction or contamination as a causal fact automatically.

Back-only metrics require an approved frozen MHR back vertex and face definition with source, version, topology and hash. Until then the back path fails closed. DMD37-neighborhood error may later be described as an engineering surface metric, never medical acupoint error without independent clinician ground truth.

Formal outputs, once separately approved, belong in a new `formal_audit/` directory. BEHAVE RGB stays on the server; public Git may contain numbers, non-identifying plots, manifests and hashes.

Formal execution is authorized only by the exact CLI token `GO_POST_TXYZ_RESIDUAL_FAILURE_AUDIT_V1`. Dry-run and formal execution are mutually exclusive. V2.3 is protected by a complete recursive file-tree snapshot, and frame identity must exactly match the V2.3 frozen manifest and per-frame result set.
