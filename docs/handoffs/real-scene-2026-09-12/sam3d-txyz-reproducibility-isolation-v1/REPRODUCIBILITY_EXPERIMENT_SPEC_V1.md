# Reproducibility experiment specification V1

The future execution order is fixed: verify immutable assets; run five-process K0 point-cloud reconstruction; run fresh-process model-load fingerprints; run exact-input Txyz twenty times with `workers=-1`; only if it differs run `workers=1` as diagnosis; run five fresh SAM processes; then execute frozen frame-order sentinels. Each stage writes hashes before numerical summaries and stops on its gate.

Sources are isolated as: raw Depth/Mask/calibration to points; Official SAM inference to vertices/anchors; exact arrays to Cheap Txyz; environment, dtype, threading, load state and frame order. Results must not be related to A/B/C/D outcomes until feature stability statuses are frozen.

Run A is canonical reconstructed evidence. B–E only define uncertainty envelopes. No rerun can be selected for being closest to V2.3.
