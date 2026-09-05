"""Build a canonical SKEL-skin -> SMPL-X-vertex correspondence map.

This is a project fitting map, not the official SMPL-X parameter-transfer data.
It is intentionally identified as such in every output so it cannot be mistaken
for an official or medically validated correspondence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import torch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--gender", choices=("female", "male"), required=True)
    parser.add_argument("--loader-root", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    loader_root = Path(args.loader_root).resolve()
    sys.path.insert(0, str(loader_root))
    os.environ["SKEL_LOADER_ROOT"] = str(loader_root)
    from skel.skel_model import SKEL

    target_payload = np.load(args.target)
    target = np.asarray(target_payload["vertices"], dtype=np.float32)
    model = SKEL(args.gender, model_path=str(loader_root / "data" / "skel")).to("cpu")
    with torch.no_grad():
        output = model(
            torch.zeros(1, model.num_q_params),
            torch.zeros(1, model.num_betas),
            torch.zeros(1, 3),
            skelmesh=False,
        )
    source = output.skin_verts[0].detach().cpu().numpy().astype(np.float32)

    translation = np.median(target, axis=0) - np.median(source, axis=0)
    tree = cKDTree(target)
    for _ in range(12):
        distances, indices = tree.query(source + translation, k=1)
        cutoff = np.quantile(distances, 0.75)
        keep = distances <= max(float(cutoff), 0.02)
        update = np.median(target[indices[keep]] - (source[keep] + translation), axis=0)
        translation += update
        if float(np.linalg.norm(update)) < 1e-7:
            break

    distances, indices = tree.query(source + translation, k=1)
    valid = distances < 0.065
    if int(valid.sum()) < 5000:
        raise RuntimeError(f"Too few reliable canonical correspondences: {int(valid.sum())}/6890")

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        schema="project-smplx-skel-surface-map-v1",
        method="nearest-canonical-vertex-with-robust-translation",
        gender=args.gender,
        target_indices=indices.astype(np.int32),
        valid_mask=valid.astype(np.bool_),
        canonical_distances_m=distances.astype(np.float32),
        initial_translation=translation.astype(np.float32),
        skel_skin_faces=model.skin_f.detach().cpu().numpy().astype(np.int32),
        skel_skeleton_faces=model.skel_f.detach().cpu().numpy().astype(np.int32),
    )
    report = {
        "schema": "project-smplx-skel-surface-map-v1",
        "method": "nearest-canonical-vertex-with-robust-translation",
        "official_transfer_correspondence": False,
        "medical_validation": False,
        "gender": args.gender,
        "valid_vertices": int(valid.sum()),
        "total_vertices": int(len(valid)),
        "canonical_rmse_m": float(np.sqrt(np.mean(np.square(distances[valid])))),
        "canonical_p95_m": float(np.quantile(distances[valid], 0.95)),
        "initial_translation": translation.tolist(),
    }
    output_path.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("SMPLX_SKEL_MAPPING_BUILD=PASS")
    print(json.dumps(report, ensure_ascii=False))


main()
