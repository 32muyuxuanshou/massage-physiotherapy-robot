"""Fit the licensed SKEL model to an evaluated SMPL-X surface.

The fit uses a project-generated surface correspondence.  It is a visual
biomechanical reference, not an official SMPL-X parameter conversion and not a
patient-specific bone estimate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
import trimesh


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--gender", choices=("female", "male"), required=True)
    parser.add_argument("--loader-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--initial-parameters")
    parser.add_argument("--steps", type=int, default=80)
    return parser.parse_args()


def load_initial(path: str | None, mapping) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    betas = np.zeros(10, dtype=np.float32)
    pose = np.zeros(46, dtype=np.float32)
    trans = np.asarray(mapping["initial_translation"], dtype=np.float32)
    if path and Path(path).is_file():
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        betas = np.asarray(payload.get("betas", betas), dtype=np.float32)
        pose = np.asarray(payload.get("pose", pose), dtype=np.float32)
        trans = np.asarray(payload.get("trans", trans), dtype=np.float32)
    return betas, pose, trans


def main() -> None:
    args = parse_args()
    loader_root = Path(args.loader_root).resolve()
    sys.path.insert(0, str(loader_root))
    os.environ["SKEL_LOADER_ROOT"] = str(loader_root)
    from skel.skel_model import SKEL

    torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))
    target_payload = np.load(args.target)
    mapping = np.load(args.mapping)
    target_vertices = np.asarray(target_payload["vertices"], dtype=np.float32)
    target_indices = np.asarray(mapping["target_indices"], dtype=np.int64)
    valid = np.asarray(mapping["valid_mask"], dtype=bool)
    mapped_target = torch.from_numpy(target_vertices[target_indices]).to("cpu")
    valid_tensor = torch.from_numpy(valid).to("cpu")

    beta0, pose0, trans0 = load_initial(args.initial_parameters, mapping)
    betas = torch.nn.Parameter(torch.from_numpy(beta0).reshape(1, 10))
    pose = torch.nn.Parameter(torch.from_numpy(pose0).reshape(1, 46))
    trans = torch.nn.Parameter(torch.from_numpy(trans0).reshape(1, 3))
    model = SKEL(args.gender, model_path=str(loader_root / "data" / "skel")).to("cpu")

    optimizer = torch.optim.Adam([betas, pose, trans], lr=0.035)
    initial_loss = None
    final_loss = None
    for step in range(max(1, args.steps)):
        optimizer.zero_grad()
        output = model(pose, betas, trans, poses_type="skel", skelmesh=False)
        delta = output.skin_verts[0][valid_tensor] - mapped_target[valid_tensor]
        surface_loss = delta.square().mean()
        beta_loss = 2.0e-5 * betas.square().mean()
        pose_loss = 1.0e-5 * pose.square().mean()
        loss = surface_loss + beta_loss + pose_loss
        if initial_loss is None:
            initial_loss = float(surface_loss.detach())
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            betas.clamp_(-3.0, 3.0)
            pose.clamp_(-2.4, 2.4)
        final_loss = float(surface_loss.detach())

    with torch.no_grad():
        output = model(pose, betas, trans, poses_type="skel", skelmesh=True)
        delta = output.skin_verts[0][valid_tensor] - mapped_target[valid_tensor]
        distances = torch.linalg.vector_norm(delta, dim=1).cpu().numpy()

    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    skeleton_vertices = output.skel_verts[0].cpu().numpy()
    skin_vertices = output.skin_verts[0].cpu().numpy()
    trimesh.Trimesh(
        vertices=skeleton_vertices,
        faces=model.skel_f.cpu().numpy(),
        process=False,
    ).export(output_dir / f"skel_reference_{args.gender}.obj")
    trimesh.Trimesh(
        vertices=skin_vertices,
        faces=model.skin_f.cpu().numpy(),
        process=False,
    ).export(output_dir / f"skel_fitted_skin_{args.gender}.obj")

    parameters = {
        "schema": "project-smplx-skel-fit-v1",
        "method": "project-surface-fit-v1",
        "official_transfer_correspondence": False,
        "medical_validation": False,
        "gender": args.gender,
        "betas": betas.detach().cpu().numpy()[0].tolist(),
        "pose": pose.detach().cpu().numpy()[0].tolist(),
        "trans": trans.detach().cpu().numpy()[0].tolist(),
        "steps": int(args.steps),
        # surface_loss is the mean over N*3 scalar coordinates.  Multiply by
        # three to report the conventional RMS Euclidean vertex distance.
        "initial_surface_rmse_m": float(np.sqrt(3.0 * max(initial_loss or 0.0, 0.0))),
        "surface_rmse_m": float(np.sqrt(np.mean(np.square(distances)))),
        "surface_distance_p95_m": float(np.quantile(distances, 0.95)),
        "valid_surface_vertices": int(valid.sum()),
    }
    (output_dir / f"skel_fit_{args.gender}.json").write_text(
        json.dumps(parameters, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("SMPLX_SKEL_FIT=PASS")
    print(json.dumps(parameters, ensure_ascii=False))


main()
