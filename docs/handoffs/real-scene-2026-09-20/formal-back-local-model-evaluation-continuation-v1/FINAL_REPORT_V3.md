# Corrected formal back/local evaluation V3

**Status: COMPLETE — corrected input and O2 contracts.**

This run restores the historical FULL contract (original RGB, historical padded bbox, original K), keeps original image geometry for UPPER and LOCAL_TORSO while masking RGB outside the dataset-derived ROI, uses ROI-only K0 depth for correction, restores the frozen O2 optimizer, shares held-out sensor samples across methods, and aggregates K1/K2/K3 → frame → sequence → subject.

| Input | Official | Txyz | T+Pose |
|---|---:|---:|---:|
| FULL | 30.77 mm | 16.53 mm | 13.27 mm |
| UPPER | 35.21 mm | 16.52 mm | 13.93 mm |
| LOCAL_TORSO | 35.49 mm | 21.76 mm | 21.66 mm |

Txyz fallback: 0/54.
T+Pose final translation delta: median 17.95 mm; maximum 82.20 mm.

## Interpretation

The corrected FULL baseline returns to the historical error scale. Txyz provides a substantial held-out improvement after fallback is removed. T+Pose adds a smaller additional gain; it is not valid to call this pure pose gain because the joint optimization also updates translation. The saved per-condition NPZ files contain Official, Txyz and T+Pose vertices, faces and final cam_t; JSON rows contain final translation delta, global rotation and body pose.

This result supports continuing with corrected evaluation and visualization. It does not by itself justify fine-tuning; the next analysis should inspect per-frame overlays and translation-versus-pose changes.
