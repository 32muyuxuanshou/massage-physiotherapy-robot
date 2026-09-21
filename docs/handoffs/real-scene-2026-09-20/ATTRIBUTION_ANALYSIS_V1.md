# Mesh correction attribution V1

The benchmark uses the corrected V3 input contract, the same 18 frozen BEHAVE frames, the same K1/K2/K3 sensor samples for every method, and the nesting K1/K2/K3 → frame → subject. Each learned correction starts from the same frozen Txyz state; therefore the branches measure incremental effects after Txyz, not independent replacements for Txyz.

| Input | Official | Txyz | T only | T + global rot | T + body pose | T + Pose |
|---|---:|---:|---:|---:|---:|---:|
| FULL | 30.77 | 16.57 | 14.32 | 14.19 | 14.06 | 13.93 |
| UPPER | 29.23 | 15.47 | 16.29 | 15.24 | 14.57 | 14.30 |
| LOCAL_TORSO | 32.26 | 22.07 | 22.42 | 22.87 | 21.58 | 20.88 |

## Interpretation

1. **FULL:** most of the gain is translation. Adding global rotation or body pose after Txyz gives only a small further reduction. This is a geometric alignment problem more than a strong pose-completion problem for these frames.
2. **UPPER:** body pose contributes more consistently than translation-only, but the total improvement remains modest. Global rotation alone is not the main factor.
3. **LOCAL_TORSO:** body pose is the useful component. Global rotation alone slightly worsens the aggregate, while body pose improves the result and the joint T+Pose is best. This supports a visibility-aware body-pose completion method more than a global rigid correction method.

## Research consequence

The paper method should not be framed as “better T+Pose.” The stronger hypothesis is a visibility-conditioned RGB-D body-pose completion module that learns which unobserved body parameters should be inferred from the visible torso and depth evidence, with uncertainty on completed regions. Txyz remains a baseline and initialization/teacher.

This attribution is still a three-subject engineering diagnosis. Before a training claim, repeat it on Sub06/Sub07 and natural occlusion/cross-sensor data, report confidence intervals and subject-level paired tests, and connect mesh completion to 3D acupoint error.
