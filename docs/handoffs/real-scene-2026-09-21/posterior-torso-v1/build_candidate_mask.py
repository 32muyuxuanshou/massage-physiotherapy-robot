"""Build a review-only posterior torso candidate from frozen MHR arrays.

This script intentionally does not freeze a medical or final mask. The candidate
is a visual-QA input and must be reviewed before its IDs enter the contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


EXPECTED = {
    "vertices": 18439,
    "faces": 36874,
    "faces_sha256": "f6748e290ef37fbb6877c4cc5bd7287105db9e98252b0ba170ae9ac3c45eacd6",
    "rest_vertices_sha256": "2b16a5d065c9dd8aeaf648d068a1ee2721c0068a6a0f97602be68a83a560e254",
}


def sha256_array(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    v = np.load(args.asset_dir / "mhr_rest_vertices.npy")
    f = np.load(args.asset_dir / "mhr_faces.npy")
    if v.shape != (EXPECTED["vertices"], 3) or f.shape != (EXPECTED["faces"], 3):
        raise SystemExit(f"shape mismatch: vertices={v.shape}, faces={f.shape}")
    if sha256_array(v) != EXPECTED["rest_vertices_sha256"]:
        raise SystemExit("rest vertex hash mismatch")
    if sha256_array(f) != EXPECTED["faces_sha256"]:
        raise SystemExit("face hash mismatch")

    # Candidate only: posterior is predominantly -Z in the frozen convention.
    # The bounds are deliberately conservative and must be reviewed visually;
    # they are not asserted as anatomical truth or written into the final contract.
    cent = v[f].mean(axis=1)
    candidate = (
        (cent[:, 2] < 0.0)
        & (cent[:, 1] > 72.0)
        & (cent[:, 1] < 145.0)
        & (np.abs(cent[:, 0]) < 25.0)
    )
    vertex_ids = np.unique(f[candidate].reshape(-1))
    payload = {
        "status": "CANDIDATE_REQUIRES_CANONICAL_VISUAL_QA",
        "candidate_rule": "face centroid z<0, 72<y<145, abs(x)<25 in frozen MHR coordinates",
        "face_ids": np.flatnonzero(candidate).tolist(),
        "vertex_ids": vertex_ids.tolist(),
        "mesh_hashes": {"faces_sha256": sha256_array(f), "rest_vertices_sha256": sha256_array(v)},
        "warning": "Do not use as final posterior truth before visual QA and exclusions review.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
