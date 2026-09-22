# Doctor validation protocol V1

## Scope

This is a small feasibility pilot for surface correspondence. It is not a clinical study and does not evaluate therapeutic efficacy.

## Participants and capture

- 3–5 consenting healthy adults for the first pilot.
- Back-facing standing pose; one fixed RGB-D camera and recorded calibration.
- No robot contact and no diagnostic or treatment claim.

## Procedure

1. Two clinicians independently mark the selected 5–8 targets on the subject's posterior surface.
2. The same targets are transferred from canonical MHR to the fitted subject surface using the frozen face/barycentric records.
3. A reviewer checks visibility, anatomical plausibility, and whether the transfer lands on the posterior surface.

## Measurements

- 3D surface distance between transferred point and each clinician mark (mm).
- 2D reprojection error in the calibrated RGB image (px).
- Inter-rater agreement between clinicians.
- Transfer stability across subjects and small pose changes.
- Failure counts for occlusion, wrong side, anterior spill, or outside-surface placement.

## Reporting rule

Report per-point and per-subject distributions. Do not collapse to a single success number before inspecting failure modes. A successful canonical transfer alone is insufficient to claim medical validity.

## Decision

Only if the pilot shows stable posterior placement and acceptable clinician agreement should an acupoint prediction head, topology-aware loss, or larger annotation campaign be designed.

