# BEHAVE Cheap Txyz Generalization V2.3 — completed run

Status: `PASS_BEHAVE_CHEAP_TXYZ_GENERALIZATION_V2`

The frozen run completed all 45 formal frames: five fresh subjects, three sequences per subject, three distinct frames per sequence, with K0 used for inference/translation and K1/K2/K3 held out for evaluation. Camera geometry QA and the visualization file audit both passed. No fallback was triggered.

## Primary results

| Subject-equal metric | Official SAM 3D Body | + frozen all-points Txyz | Change |
|---|---:|---:|---:|
| Median surface error | 31.17 mm | 17.80 mm | -13.37 mm (-42.9%) |
| P90 surface error | 76.73 mm | 54.90 mm | -21.83 mm |
| P95 surface error | 94.58 mm | 71.26 mm | -23.32 mm |
| Coverage within 50 mm | 73.83% | 87.35% | +13.52 percentage points |

All five subjects improved. The median error also improved independently on K1, K2, and K3. Of 45 frames, 36 improved on all three held-out cameras, five improved on two cameras, three improved on one camera, and one degraded on all three cameras.

The single all-camera degradation was `Date06_Sub07_stool_sit/t0038.000`: frame-level held-out median increased from 24.15 mm to 36.58 mm. It remains in all reports and was not filtered.

## Translation and runtime

Median correction was Tx -2.37 mm, Ty -0.06 mm, Tz -51.47 mm, with median translation norm 52.84 mm. The P90 translation norm was 119.92 mm. This shows that the dominant recoverable error is camera-depth/global translation, especially depth-axis Tz.

On the RTX 2080 Ti server, P50 runtime was 320.6 ms for SAM 3D Body, 321.5 ms for all-points Txyz, and 654.8 ms total. P90 total runtime was 885.5 ms.

## Interpretation

This run supports the engineering claim that a frozen, depth-assisted global translation correction generalizes across five unseen BEHAVE subjects and three held-out cameras. It does not establish that pose, body shape, articulation, or local surface geometry is solved: Txyz changes only global translation. The remaining P95 of 71.26 mm and the retained degradation case identify the next work: diagnose non-translation mesh errors and define an abstention signal without changing this completed baseline.

BEHAVE images and visualizations containing dataset RGB are retained on the server because the dataset license restricts redistribution. Git contains the full numeric reports, manifests, QA, result hashes, and visualization inventory, but no raw BEHAVE RGB frames.
