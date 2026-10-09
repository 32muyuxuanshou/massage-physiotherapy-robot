# R3 enlarged synthetic multi-seed results

500 synthetic parameter identities × 2 fixed poses × 4 shared physical cameras = 4,000 images. TRAIN 400 / VAL 50 / TEST 50 identities. TEST sealed.
30 epochs, batch 16; three training seeds per existing model. One learning rate chosen by the frozen six-cell synthetic-VAL-only screen. Best and last both retained.

| Model | VAL camera-frame vertex mean ± seed sample SD (mm) |
|---|---:|
| rgb_only | 79.29 ± 0.68 |
| residual | 90.08 ± 0.20 |
| cross_attention | 86.57 ± 1.93 |

Read PAIRED_SEED_COMPARISONS.json, every per-seed RESULTS.json and DEPTH_ABLATIONS.json together. Missing-depth degradation alone is not proof of geometry use: this architecture falls back to Official when depth is missing.

Real transfer: HuMMan 192 TRAIN + 40 VAL timestamps; K000 inputs, K001 independent measured points. Exact point-to-triangle distance is primary. Report TRAIN and VAL separately. No real training and no TEST evaluation.

These are synthetic geometry and real transfer development results, not prone clinical/acupoint accuracy or a guarantee of medical deployment. R2 data/camera distribution differs; its numbers are not direct matched comparisons.

Full raw outputs, metrics, best/last checkpoints and runtime source identity are in the server run directory. The static figures are generated from cached final meshes.