from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--repeat", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    left = np.load(args.primary / "predictions.npz", allow_pickle=False)
    right = np.load(args.repeat / "predictions.npz", allow_pickle=False)
    array_checks = {key: bool(np.array_equal(left[key], right[key])) for key in left.files}
    left_state = torch.load(args.primary / "model_state.pt", map_location="cpu", weights_only=False)
    right_state = torch.load(args.repeat / "model_state.pt", map_location="cpu", weights_only=False)
    tensor_checks = {
        key: bool(torch.equal(left_state["model_state"][key], right_state["model_state"][key]))
        for key in left_state["model_state"]
    }
    config_equal = read_json(args.primary / "training_config.json") == read_json(args.repeat / "training_config.json")
    curve_equal = (args.primary / "training_curve.csv").read_bytes() == (args.repeat / "training_curve.csv").read_bytes()
    metrics_left = read_json(args.primary / "metrics.json")
    metrics_right = read_json(args.repeat / "metrics.json")
    metrics_left.pop("elapsed_seconds", None)
    metrics_right.pop("elapsed_seconds", None)
    metrics_equal_except_elapsed = metrics_left == metrics_right
    checks = {
        "prediction_arrays_exact": all(array_checks.values()),
        "model_tensors_exact": all(tensor_checks.values()),
        "training_config_exact": config_equal,
        "training_curve_exact": curve_equal,
        "metrics_exact_except_elapsed": metrics_equal_except_elapsed,
    }
    payload = {
        "schema": "engineering-pilot-training-determinism-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "prediction_arrays": array_checks,
        "model_tensors": tensor_checks,
        "primary_model_file_sha256": sha256(args.primary / "model_state.pt"),
        "repeat_model_file_sha256": sha256(args.repeat / "model_state.pt"),
        "model_file_hash_required_equal": False,
        "note": "Tensor equality is the hard gate; torch container byte hashes are recorded but not required.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"DETERMINISM": "PASS" if payload["passed"] else "FAIL", **checks}, ensure_ascii=False))
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
