# R5.2b reproduction

Compute root: `/raid5/xuhd/rgbd_sam3d/r52b_projective_plane_diagnostic_v1` on218.
Runtime: `/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python`; CUDA11.8/PyTorch2.5.1, nvdiffrast0.4.0. Set `LD_LIBRARY_PATH=/raid5/xuhd/rgbd_sam3d/runtime218/env/lib`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

`run.py` is the exact original executed master, retained byte-for-byte for the pre-run freeze. Its pilot cache linkage was repaired in this execution by `refresh_pilot.py`, documented in REFRESH_PILOT_EVALUATION.json. For a **future fresh execution**, use `python code/run_reproduction.py`: the same master additionally moves completed pilot evaluations to `pilot_evaluation/` before full fitting, so the formal evaluator cannot reuse stale timing-bearing fit hashes. This is an orchestration fix only; no scientific operator changes. Do not rerun into an existing completed scientific directory; use a separately named root for a new execution and document its identity.

Code `common.py` explicitly lists dependencies on the prior R52 directory, previous frozen geometry and original A caches. `projection.py` imports the unmodified R51 renderer whose hash is captured before execution. No new backbone, checkpoint, dataset split or model training is involved.

After completion:

```
python code/query_summary.py
python code/replay_cached.py --tag real_s11_<saved-key> --method proj_plane3
```

`replay_cached.py` reconstructs a selected endpoint from the new compressed A grids and saved body/Coarse, without the original backbone cache. Supply the original MHR faces/anchors and frozen renderer at their documented paths. It never opens B/GT.

Each final Mesh is reconstructed with **the evaluator's exact arithmetic**:

- original Fine: original stored `vertices_camera_A` from frozen G prediction;
- Official+Txyz: `(body_m+original_camera_m).astype(float64)+applied_delta_m`;
- all Coarse methods: `(body_m+coarse_camera_m).astype(float64)+applied_delta_m`.

Faces are the original MHR `assets/faces.npy`. Body and camera remain separate to avoid storing18 duplicate full meshes per frame. `fits/*.json` preserves every endpoint, trace, visible anchor IDs, cap/fallback and source SHA; `fits/*.npz` preserves body and endpoint arrays. `inputs/*.npz` preserves depth, mask, rays, K, affine and original image size. `evaluation/*.npz` preserves exact fixed-B per-point distances. The previous frozen geometry archive preserves original reference, B points/calibration, GT and Fine mesh. No refit is required to redraw or recompute metrics.

Reference identity: R52 Git39358367; its POST_INTEGRITY fit hashes are checked before copying references. New source A cache SHA must match the earlier frozen INPUT_FREEZE; all original G files, new input files, prediction files and results are rechecked at completion. Descriptive reporting/replay utilities added after the pre-run science freeze are identified separately; they cannot change fitting or checkpoint selection.

`backup_local.py` reuses the established8-range direct-SFTP backup. Supply the password only through process environment `ROBOT_SSH_PASSWORD`; no proxy, credential files, shutdown commands or raw data in Git.

After local figures/reports have been reviewed and copied to218, `python code/package_final.py` includes inputs, fits, evaluation, reports, A-query review arrays and retained pilot evidence. `backup_local.py` transfers that volume and verifies its actual SHA. `package218.py` is the original frozen packaging helper retained as execution evidence; the expanded final helper is used for delivery.

Local reporting sequence: `fetch_local.py --review`; `reference_check_local.py --root <output>`; `analyze_local.py --root <output>`; `query_plot_local.py --root <output>`; `visualize_local.py --root <output>`; `report_local.py --root <output>`. Query-review inputs and QUERY_DIAGNOSTICS are separately fetched from218. The final Git manifest binds actual index bytes; scoped `.gitattributes` preserves the original mixed LF/CRLF runtime code bytes instead of silently normalizing them.
