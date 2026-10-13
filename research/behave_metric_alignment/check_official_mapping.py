"""Numerical check against the pinned official MHR mapping method on CPU.

Only the official mapping method is executed. Its parameter-fitting backends,
licensed SMPL model, and MHR forward model are not needed for this check.
"""

import argparse
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from metrics import map_mhr_to_smpl, sha256


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--official-source", type=Path, required=True)
    p.add_argument("--mapping", type=Path, required=True)
    p.add_argument("--faces", type=Path, required=True)
    p.add_argument("--vertices-m", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    torch.set_num_threads(1)
    tree = ast.parse(args.official_source.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Conversion")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_compute_target_vertices")
    # Avoid importing unrelated fitting backends, while retaining the actual method body.
    def tqdm(iterable, **kwargs):
        return iterable
    tqdm._instances = []
    namespace = dict(np=np, torch=torch, tqdm=tqdm,
                     logger=SimpleNamespace(info=lambda message: None),
                     ConversionConstants=SimpleNamespace(CENTIMETERS_TO_METERS=0.01,
                                                          METERS_TO_CENTIMETERS=100.0))
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(args.official_source), "exec"), namespace)
    with np.load(args.mapping) as data:
        mapping = (data["triangle_ids"], data["baryc_coords"])
    faces = np.load(args.faces)
    vertices = np.load(args.vertices_m).astype(np.float64)
    owner = SimpleNamespace(_load_surface_mapping_MHR2SMPL=lambda: mapping,
                            _mhr_model=SimpleNamespace(character=SimpleNamespace(mesh=SimpleNamespace(faces=faces))),
                            _DEVICE=torch.device("cpu"), _batch_size=1)
    # The official method expects raw MHR centimeters, unlike our camera-meter API.
    official = namespace["_compute_target_vertices"](
        owner, torch.tensor(vertices[None] * 100, dtype=torch.float64), "mhr2smpl"
    ).numpy()[0]
    ours = map_mhr_to_smpl(vertices, faces, args.mapping)
    maximum = float(np.abs(official - ours).max())
    mean_mm = float(1000 * np.linalg.norm(official - ours, axis=1).mean())
    assert maximum < 1e-6
    result = {"status": "PASS_OFFICIAL_METHOD_NUMERICAL_COMPARISON", "device": "cpu",
              "max_coordinate_difference_m": maximum, "mean_vertex_difference_mm": mean_mm,
              "float32_official_weights": True, "vertex_count": len(ours),
              "official_method_source_sha256": sha256(args.official_source),
              "mapping_sha256": sha256(args.mapping), "scientific_benchmark_executed": False}
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
