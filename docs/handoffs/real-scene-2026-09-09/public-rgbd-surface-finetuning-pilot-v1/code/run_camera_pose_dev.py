"""Run only the missing Camera+Pose DEV ablation via the sealed V1 fitter.

This wrapper does not read any sealed-test manifest. It extends the already executed
V1 parameter groups in memory and invokes a fresh per-frame fit.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v1-fit-script", type=Path, required=True)
    ap.add_argument("--sam-repo", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--mhr", type=Path, required=True)
    ap.add_argument("--prepared-dir", type=Path, required=True)
    ap.add_argument("--predictions-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=100)
    args = ap.parse_args()
    # Generate a temporary source beside outputs, leaving the committed V1 script unchanged.
    source = args.v1_fit_script.read_text(encoding="utf-8")
    needle = '"camera": ("camera",),'
    if needle not in source:
        raise RuntimeError("V1 fitter group contract changed")
    source = source.replace(needle, needle + '\n    "camera_pose": ("camera", "global_rot", "body_pose"),', 1)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    patched = args.output_dir / "fit_mhr_camera_pose_runtime.py"
    patched.write_text(source, encoding="utf-8")
    observations = sorted(args.prepared_dir.glob("*.npz"))
    if len(observations) != 5:
        raise RuntimeError(f"DEV contract requires exactly 5 observations, found {len(observations)}")
    for observation in observations:
        for model_tag in ("official", "v2_e5"):
            prediction = args.predictions_dir / f"{observation.stem}__{model_tag}.npz"
            output = args.output_dir / f"{observation.stem}__{model_tag}__camera_pose.json"
            command = [sys.executable, str(patched), "--sam-repo", str(args.sam_repo),
                       "--checkpoint", str(args.checkpoint), "--mhr", str(args.mhr),
                       "--observation", str(observation), "--prediction", str(prediction),
                       "--output", str(output), "--model-tag", model_tag,
                       "--group", "camera_pose", "--steps", str(args.steps)]
            subprocess.run(command, check=True)
            print("DONE", output.name, flush=True)


if __name__ == "__main__":
    main()
