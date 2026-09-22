"""Propagate provisional acupoints onto existing same-topology MHR predictions."""
from pathlib import Path
import json, hashlib
import numpy as np

ROOT = Path(__file__).parent
RAW = ROOT.parents[1] / "real-scene-2026-09-11" / "back-dmd37-engineering-validation-v1" / "raw"
PRED_ROOT = ROOT.parents[2] / ".." / "AI感知模块" / "outputs" / "内部工程证据" / "2026-09-07_PUBLIC_BACK_PILOT"
PRED_ROOT = PRED_ROOT.resolve()
OUT = ROOT / "prediction_propagation_v1"
OUT.mkdir(exist_ok=True)

frozen_faces = np.load(RAW / "mhr_faces.npy")
mask = json.loads((ROOT / "candidate_posterior_mask.json").read_text(encoding="utf-8"))
point_data = json.loads((ROOT / "VIRTUAL_ACUPOINTS_ENGINEERING_V1.json").read_text(encoding="utf-8"))
face_ids = np.asarray(mask["face_ids"], dtype=int)

def write_points(path, pts):
    with path.open("w", encoding="ascii") as fp:
        fp.write("ply\nformat ascii 1.0\n")
        fp.write(f"element vertex {len(pts)}\nproperty float x\nproperty float y\nproperty float z\n")
        fp.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for p in pts:
            fp.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f} 30 80 220\n")

def transfer(vertices):
    out = []
    for r in point_data["records"]:
        tri = frozen_faces[int(r["face_index"])]
        bary = np.asarray(r["barycentric"], dtype=float)
        out.append((vertices[tri] * bary[:, None]).sum(axis=0))
    return np.asarray(out)

results = []
for d in sorted(PRED_ROOT.glob("B*")):
    p = d / "prediction.npz"
    if not p.exists():
        continue
    data = np.load(p, allow_pickle=True)
    vertices = np.asarray(data["pred_vertices"], dtype=float)
    faces = np.asarray(data["faces"])
    if vertices.shape != (18439, 3) or not np.array_equal(faces, frozen_faces):
        raise SystemExit(f"topology mismatch: {p}")
    points = transfer(vertices)
    mask_vertices = np.unique(frozen_faces[face_ids].reshape(-1))
    result_dir = OUT / d.name
    result_dir.mkdir(exist_ok=True)
    write_points(result_dir / "virtual_acupoints.ply", points)
    result = {
        "sample": d.name,
        "source": str(p),
        "coordinate_note": "prediction.npz pred_vertices coordinate frame",
        "topology_verified": True,
        "posterior_mask_vertex_count": int(len(mask_vertices)),
        "posterior_mask_bbox": {"min": vertices[mask_vertices].min(axis=0).tolist(), "max": vertices[mask_vertices].max(axis=0).tolist()},
        "acupoints": [{"id": r["id"], "xyz": q.tolist(), "medical_truth": False} for r, q in zip(point_data["records"], points)]
    }
    (result_dir / "PROPAGATED_POINTS.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    results.append(result)

summary = {
    "status": "PASS",
    "sample_count": len(results),
    "samples": [r["sample"] for r in results],
    "topology": {"vertices": 18439, "faces": 36874, "faces_sha256": hashlib.sha256(np.ascontiguousarray(frozen_faces).tobytes()).hexdigest()},
    "medical_truth": False,
    "interpretation": "Eight provisional engineering points were propagated by frozen face+barycentric correspondence; coordinates are per-prediction-frame and are not clinician-validated landmarks."
}
(OUT / "PROPAGATION_SUMMARY_V1.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
