"""Recalculate transfer metrics from the delivered NPZs without models or refitting."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def span(values):
    return np.max([np.linalg.norm(values[i] - values[j], axis=1)
                   for i, j in [(0, 1), (0, 2), (1, 2)]], axis=0) * 1000


def main(root):
    manifests = {name: read(root / f"{name}_MANIFEST.json")
                 for name in ["INPUT", "CURVE", "BINDING"]}
    hashed = 0
    for rows in manifests.values():
        for row in rows:
            remote = Path(row["path"])
            path = root / remote.parent.name / remote.name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], path
            hashed += 1
    results = read(root / "RESULTS.json")
    binding = manifests["BINDING"]
    cache = {row["path"]: dict(np.load(root / "bindings" / Path(row["path"]).name))
             for row in binding}
    differences = []
    metrics = ["query_span_median_mm", "bound_span_median_mm", "projection_median_mm"]
    for row in results["per_model"]:
        group = sorted([r for r in binding if all(r[k] == row[k] for k in
                        ["subject", "strategy", "mesh_method", "model_seed"])],
                       key=lambda r: r["split_seed"])
        points = [cache[r["path"]] for r in group]
        values = [np.median(span([p["query_m"] for p in points])),
                  np.median(span([p["xyz_m"] for p in points])),
                  np.mean([np.median(p["projection_distance_m"]) * 1000 for p in points])]
        differences.extend(abs(float(v) - row[k]) for k, v in zip(metrics, values))
    for row in results["initialization"]:
        group = sorted([r for r in binding if all(r[k] == row[k] for k in
                        ["subject", "strategy", "mesh_method", "split_seed"])],
                       key=lambda r: r["model_seed"])
        values = span([cache[r["path"]]["xyz_m"] for r in group])
        differences.append(abs(float(np.median(values)) - row["initialization_bound_span_median_mm"]))
    for row in results["per_subject"]:
        group = [r for r in results["per_model"] if all(r[k] == row[k] for k in
                 ["subject", "strategy", "mesh_method"])]
        differences.extend(abs(float(np.mean([r[k] for r in group])) - row[k]) for k in metrics)
    for row in results["aggregate"]:
        group = [r for r in results["per_subject"] if all(r[k] == row[k] for k in
                 ["role", "strategy", "mesh_method"])]
        assert len(group) == row["subjects"]
        differences.extend(abs(float(np.median([r[k] for r in group])) - row[k]) for k in metrics)
    for row in results["paired_12"]:
        if row["method"] == "GROOVE_DP":
            continue  # Historical baseline lives in the linked, unchanged prior delivery.
        group = [r for r in results["per_subject"] if r["subject"] in results["paired_subjects"]
                 and r["strategy"] == row["method"] and r["mesh_method"] == row["mesh_method"]]
        assert len(group) == 12
        differences.extend(abs(float(np.median([r[k] for r in group])) - row[k]) for k in metrics)
    maximum = max(differences)
    assert maximum < 1e-9, maximum
    receipt = dict(status="PASS", hashed_inputs_curves_bindings=hashed,
                   bindings_reopened=len(cache), numerical_checks=len(differences),
                   maximum_difference_mm=maximum, models_rerun=False, mesh_refit=False,
                   historical_baseline_recomputed=False,
                   scope="Delivered metric consistency; anatomical accuracy not validated")
    (root / "CACHE_REPLAY_VERIFICATION.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    main(parser.parse_args().root)
