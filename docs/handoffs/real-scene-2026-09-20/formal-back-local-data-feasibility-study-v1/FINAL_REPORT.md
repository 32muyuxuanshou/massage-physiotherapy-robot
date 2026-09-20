# FORMAL_BACK_LOCAL_DATA_FEASIBILITY_STUDY_V1

## Decision

**REFERENCE_NOT_READY — NO_TRAINING.**

The task design is scientifically sound, but the current local assets do not satisfy its own minimum execution gate. We therefore completed the data/crop feasibility portion and stopped before producing model comparisons that would lack a valid regional/reference contract.

## What was actually executed

- Audited BEHAVE and HuMMan assets from disk.
- Froze an outcome-blind subset of **5 subjects / 24 timestamps**: 18 BEHAVE timestamps across Sub03–05 and 6 HuMMan timestamps across p000823/p001088.
- Generated synchronized FULL, UPPER and provisional BACK_LOCAL RGB/depth/mask files for one BEHAVE and one HuMMan sample.
- Recomputed effective crop intrinsics and passed numeric projection equivalence for all six crop cases.
- Preserved the held-out camera role in the frozen subset.

## Why the formal model experiment stopped

HuMMan SMPL parameter NPZ files are available, but the licensed SMPL body-model files needed to instantiate source vertices are absent. The official MHR conversion workflow is also not installed locally. TEST 3 therefore cannot run, and TEST 4 cannot compute a conversion surface error. Separately, the project has no independently validated canonical posterior surface mapping that can be frozen as BACK_REGION_V1; prior polygons remain provisional engineering annotations.

The BACK_LOCAL images produced here only prove crop and camera-coordinate handling. They are not evidence that the cropped person is posterior-facing, and they cannot support a scientific back-region metric.

## Answers to the requested questions

1. Existing datasets can construct synchronized local torso RGB-D inputs: **yes, at smoke-test level**.
2. FULL/UPPER/BACK_LOCAL model errors: **not measured; gate stopped before model evaluation**.
3. Whether local input degrades SAM 3D Body: **not yet knowable from this run**.
4. Cheap Txyz on local input: **not evaluated after gate failure**.
5. T+Pose on local input: **not evaluated after gate failure**.
6. Whole-body versus back-region trend: **not comparable until BACK_REGION_V1 is valid**.
7. Current reference labels: BEHAVE whole-body fitted reference is available; the cross-dataset back-local reference is **not ready**.
8. SMPL→MHR error: **not computable with current licensed assets**.
9. Single-view fitting pseudo-label quality: **not started because the stronger-reference prerequisite is missing**.
10. Training decision: **NO_TRAINING; repair reference generation first**.

## Smallest valid next step

Provide the official licensed SMPL model files on the server, install the upstream MHR conversion tool, run the prescribed five-sample conversion smoke, and independently freeze a posterior surface mapping before viewing model error maps. After those gates pass, the frozen 24-timestamp subset can be used for Official/O1/O2 comparisons without changing sample selection.

## Reproducibility

Run `code/run_stage0_smoke.py` with the recorded server paths. Exact audit records are under `audit/`; crop images and contact sheets are under `inputs/` and `visualizations/`.
