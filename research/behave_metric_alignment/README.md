# MHR → SMPL PVE evaluator and fixed BEHAVE comparison

Read the [metric contract and evidence](../../docs/research/2026-10-13-behave-metric-alignment/README.md) before running a benchmark.

`metrics.py` performs fixed official MHR LOD1 barycentric mapping and reports corresponding-vertex mean L2 in millimeters. It does not run SAM3D, Txyz, or body fitting.

`sanity.py` verifies analytic metric behavior and an existing prediction cache. `check_official_mapping.py` checks the NumPy mapping against the pinned official method on CPU.

Input prediction vertices must already be in camera coordinates in meters. A BEHAVE fitted reference can be converted using its own sequence/date/camera calibration. Always declare reference space explicitly; preserve PLY vertex order with `process=False`.

The optional joint regressor must use the same SMPL topology. Its joint definition is not assumed to match M³. Centroid-centered PVE is never labeled pelvis-centered PVE.

Mapping files and licensed body assets stay outside Git. No scientific BEHAVE benchmark has been executed by these QA checks.

The new comparison preparation is documented in [the 2026-10-13 handoff](../../docs/handoffs/real-scene-2026-10-13/behave-r5-comparison-v1/README.md). `inspect_archive.py` freezes a structural test subsample, `download_subset.py` downloads it via direct HTTP Range, `qa_real_coordinates.py` checks real-frame transforms, and `prepare_inputs_cpu.py` stores K0 inputs separately from fitted reference and held-out sensors.

`cache_official_gpu.py`, `predict_existing_gpu.py`, and `run_benchmark.py` require an explicitly available GPU. They use existing frozen weights without training. GPU forward execution has not yet been verified. `evaluate_cached_cpu.py` reuses the historical R4.1 Txyz/triangle evaluator; `summarize_benchmark.py` freezes aggregation and requires every model/seed/checkpoint cell before publishing a complete numeric summary.
