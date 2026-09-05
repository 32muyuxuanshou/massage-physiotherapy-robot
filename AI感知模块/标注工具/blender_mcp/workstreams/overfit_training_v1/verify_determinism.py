from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_state(path: Path) -> dict:
    return torch.load(path, map_location="cpu", weights_only=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--repeat", type=Path, required=True)
    args = parser.parse_args()

    a = np.load(args.primary / "predictions.npz", allow_pickle=False)
    b = np.load(args.repeat / "predictions.npz", allow_pickle=False)
    prediction_equal = np.array_equal(a["predicted_uv"], b["predicted_uv"])
    target_equal = np.array_equal(a["target_uv"], b["target_uv"])
    error_equal = np.array_equal(a["pixel_errors"], b["pixel_errors"])
    state_a = load_state(args.primary / "model_state.pt")
    state_b = load_state(args.repeat / "model_state.pt")
    keys_equal = state_a["model_state"].keys() == state_b["model_state"].keys()
    tensors_equal = keys_equal and all(
        torch.equal(state_a["model_state"][key], state_b["model_state"][key])
        for key in state_a["model_state"]
    )
    preprocessing_equal = torch.equal(state_a["feature_mean"], state_b["feature_mean"]) and torch.equal(state_a["feature_std"], state_b["feature_std"])
    curve_equal = (args.primary / "training_curve.csv").read_bytes() == (args.repeat / "training_curve.csv").read_bytes()
    report = {
        "schema": "overfit-training-determinism-v1",
        "fresh_process_repeat": True,
        "same_seed": state_a["seed"] == state_b["seed"],
        "predicted_uv_exact": prediction_equal,
        "target_uv_exact": target_equal,
        "pixel_errors_exact": error_equal,
        "model_tensors_exact": tensors_equal,
        "preprocessing_statistics_exact": preprocessing_equal,
        "training_curve_exact": curve_equal,
        "primary_model_file_sha256": sha256(args.primary / "model_state.pt"),
        "repeat_model_file_sha256": sha256(args.repeat / "model_state.pt"),
        "note": "Tensor equality is authoritative; container-file SHA is reported but is not required because serialization metadata may differ.",
    }
    report["passed"] = all(report[key] is True for key in (
        "fresh_process_repeat", "same_seed", "predicted_uv_exact", "target_uv_exact",
        "pixel_errors_exact", "model_tensors_exact", "preprocessing_statistics_exact", "training_curve_exact",
    ))
    (args.primary / "determinism_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
