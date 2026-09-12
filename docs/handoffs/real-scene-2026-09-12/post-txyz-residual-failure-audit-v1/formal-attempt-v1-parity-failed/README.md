# Formal attempt V1 — stopped by replay parity gate

Status: `STOP_TXYZ_REPLAY_PARITY_FAILED`.

The approved formal execution reconstructed the frozen V2.3 K0 point clouds and 16,384 surface anchors for all 45 manifest frames using the frozen Official SAM3D assets. The replay parity gate passed 26 frames and failed 19. The maximum per-component translation difference was `1.80464947807657e-05 m` (`0.0180464947807657 mm`), above the frozen strict threshold `<1e-6 m` (`<0.001 mm`). Fallback matched, but the translation condition requires 45/45, so execution stopped before A/B/C/D failure analysis.

No threshold was relaxed, no frame was removed, and no Txyz parameter was changed. V2.3 remained read-only. No classifier was trained. The rerun used SAM3D only to reconstruct inputs that V2.3 had not preserved; this execution therefore cannot be be answer “SAM3D run: NO”.

Files:

- `TXYZ_REPLAY_PARITY_FAILURE_REPORT.json`: complete per-frame replay/V2.3 comparison.
- `replay_input_manifest.json`: points/anchors paths, hashes and provenance.
- `replay_features.json`: six-iteration diagnostic traces generated before the stop.
- `capture.log`: server execution log.
- `FAILURE_DELIVERY_MANIFEST.json`: transferred-file hashes.

BEHAVE RGB and generated visualizations remain on the server and are not included here. The numeric replay traces are retained as audit evidence only; they are not promoted to a scientific failure analysis because parity failed.
