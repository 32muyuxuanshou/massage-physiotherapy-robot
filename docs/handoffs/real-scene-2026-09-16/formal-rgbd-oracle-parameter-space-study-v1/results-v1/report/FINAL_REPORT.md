# FORMAL RGB-D ORACLE PARAMETER-SPACE STUDY V1

## Decision
**STRUCTURED_PARAMETER_SPACE: STRONG_GO**

The study uses BEHAVE dataset person masks and K0 RGB-D for optimization. K1/K2/K3 are held out until Stage A outputs are frozen.

## O2/O3/O4 vs O1

| Method | Held-out improvement | Absolute delta | Aligned improvement | Subjects improved |
|---|---:|---:|---:|---:|
| O2 | 10.62% | -1.98 mm | 7.84% | 5/5 |
| O3 | -1.29% | +0.24 mm | 2.10% | 3/5 |
| O4 | 7.92% | -1.47 mm | 8.04% | 5/5 |

## Interpretation

O2 tests translation + pose, O3 tests translation + identity shape and skeletal scale, and O4 tests all three parameter groups. The Oracle result establishes parameter-space utility only; it does not prove unique residual factorization.

Regional anatomical metrics are NOT_YET_AVAILABLE because no frozen canonical MHR anatomical partition exists. Whole-body and translation-aligned held-out metrics remain the formal evidence.
