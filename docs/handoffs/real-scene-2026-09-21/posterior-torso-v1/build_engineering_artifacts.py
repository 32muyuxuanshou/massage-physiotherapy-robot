"""Export the frozen engineering posterior mask and virtual points for Blender/QA."""
from pathlib import Path
import json
import numpy as np

ROOT = Path(__file__).parent
RAW = ROOT.parents[1] / "real-scene-2026-09-11" / "back-dmd37-engineering-validation-v1" / "raw"
V = np.load(RAW / "mhr_rest_vertices.npy")
F = np.load(RAW / "mhr_faces.npy")
mask = json.loads((ROOT / "candidate_posterior_mask.json").read_text(encoding="utf-8"))
points = json.loads((ROOT / "VIRTUAL_ACUPOINTS_ENGINEERING_V1.json").read_text(encoding="utf-8"))
face_ids = np.asarray(mask["face_ids"], dtype=int)

def write_ply(path, vertices, faces=None, colors=None):
    faces = np.empty((0, 3), dtype=int) if faces is None else np.asarray(faces, dtype=int)
    colors = np.tile([210, 80, 80], (len(vertices), 1)) if colors is None else colors
    with path.open("w", encoding="ascii") as fp:
        fp.write("ply\nformat ascii 1.0\n")
        fp.write(f"element vertex {len(vertices)}\nproperty float x\nproperty float y\nproperty float z\n")
        fp.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        fp.write(f"element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n")
        for p, c in zip(vertices, colors):
            fp.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f} {int(c[0])} {int(c[1])} {int(c[2])}\n")
        for tri in faces:
            fp.write(f"3 {tri[0]} {tri[1]} {tri[2]}\n")

selected = np.unique(F[face_ids].reshape(-1))
remap = {int(old): i for i, old in enumerate(selected)}
local_faces = np.array([[remap[int(x)] for x in tri] for tri in F[face_ids]], dtype=int)
write_ply(ROOT / "posterior_torso_engineering_mask.ply", V[selected], local_faces)

pts = np.asarray([r["canonical_xyz_mm"] for r in points["records"]], dtype=float)
point_colors = np.tile([30, 80, 220], (len(pts), 1))
write_ply(ROOT / "virtual_acupoints_engineering.ply", pts, colors=point_colors)

tri = V[F[face_ids]]
normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
report = {
    "status": "ENGINEERING_ARTIFACTS_GENERATED",
    "mask_faces": int(len(face_ids)),
    "mask_vertices": int(len(selected)),
    "mask_bbox_mm": {"min": V[selected].min(axis=0).tolist(), "max": V[selected].max(axis=0).tolist()},
    "posterior_normal_z_mean": float(normals[:, 2].mean()),
    "posterior_normal_z_median": float(np.median(normals[:, 2])),
    "point_count": int(len(pts)),
    "point_bbox_mm": {"min": pts.min(axis=0).tolist(), "max": pts.max(axis=0).tolist()},
    "point_ids": [r["id"] for r in points["records"]],
    "medical_truth": False,
    "artifacts": ["posterior_torso_engineering_mask.ply", "virtual_acupoints_engineering.ply"]
}
(ROOT / "ENGINEERING_ARTIFACTS_QA_V1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
