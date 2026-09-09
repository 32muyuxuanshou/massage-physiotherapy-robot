"""Subject-macro summary; refuses to issue PASS from fit-view improvement alone."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", type=Path, nargs="+")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--minimum-subjects", type=int, default=3)
    ap.add_argument("--minimum-relative-heldout-improvement", type=float, default=0.10)
    args = ap.parse_args()
    rows = []
    for path in args.results:
        result = json.loads(path.read_text(encoding="utf-8"))
        held = result["metrics"]["camera_b_held_out"]
        before, after = held["initial"]["median_mm"], held["refined"]["median_mm"]
        rows.append({"path": str(path.resolve()), "model_tag": result["model_tag"],
                     "subject_id": result["subject_id"],
                     "observation_id": result["observation_id"],
                     "group": result["group"], "initial_heldout_median_mm": before,
                     "refined_heldout_median_mm": after,
                     "relative_improvement": (before - after) / max(before, 1e-9),
                     "parameter_sanity": result["parameter_sanity"]["within_all_limits"]})
    combined = [r for r in rows if r["group"] == "combined"]
    subject_model = []
    for model_tag in sorted({r["model_tag"] for r in combined}):
        model_rows = [r for r in combined if r["model_tag"] == model_tag]
        for subject_id in sorted({r["subject_id"] for r in model_rows}):
            sr = [r for r in model_rows if r["subject_id"] == subject_id]
            subject_model.append({
                "model_tag": model_tag, "subject_id": subject_id,
                "frame_count": len(sr),
                "relative_improvement_median_across_frames": float(np.median(
                    [r["relative_improvement"] for r in sr])),
                "all_parameter_sanity": all(r["parameter_sanity"] for r in sr),
            })
    per_model = {}
    for model_tag in sorted({r["model_tag"] for r in subject_model}):
        sr = [r for r in subject_model if r["model_tag"] == model_tag]
        passing = [r for r in sr if r["relative_improvement_median_across_frames"] >=
                   args.minimum_relative_heldout_improvement and r["all_parameter_sanity"]]
        per_model[model_tag] = {
            "independent_subject_count": len(sr), "passing_subject_count": len(passing),
            "majority_consistent": len(sr) >= args.minimum_subjects and len(passing) > len(sr) / 2,
            "subject_macro_relative_improvement_mean": None if not sr else float(np.mean(
                [r["relative_improvement_median_across_frames"] for r in sr])),
            "subject_macro_relative_improvement_median": None if not sr else float(np.median(
                [r["relative_improvement_median_across_frames"] for r in sr])),
        }
    if any(v["majority_consistent"] for v in per_model.values()):
        decision = "PASS_PUBLIC_MHR_FITABILITY_SANITY"
        reason = "at least one initialization improves held-out geometry for a majority of independent subjects with sane parameters"
    else:
        decision = "INCONCLUSIVE_DATA_OR_OPTIMIZATION_LIMITED"
        reason = "no model has enough independent subjects with consistent held-out improvement; representation failure is not isolated"
    out = {"decision": decision, "reason": reason,
           "gate": {"minimum_subjects": args.minimum_subjects,
                    "minimum_relative_heldout_improvement": args.minimum_relative_heldout_improvement,
                    "requires_parameter_sanity": True, "fit_view_alone_can_pass": False},
           "per_model_subject_macro": per_model, "subject_model_rows": subject_model,
           "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
