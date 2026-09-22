"""Validate face+barycentric acupoint transfer on the frozen MHR topology."""
from pathlib import Path
import json
import numpy as np

ROOT = Path(__file__).parent
RAW = ROOT.parents[1] / "real-scene-2026-09-11" / "back-dmd37-engineering-validation-v1" / "raw"
v = np.load(RAW / "mhr_rest_vertices.npy")
f = np.load(RAW / "mhr_faces.npy")
data = json.loads((ROOT / "VIRTUAL_ACUPOINTS_ENGINEERING_V1.json").read_text(encoding="utf-8"))

def transfer(vertices):
    out = {}
    for r in data["records"]:
        face = f[int(r["face_index"])]
        bary = np.asarray(r["barycentric"], dtype=float)
        out[r["id"]] = (vertices[face] * bary[:, None]).sum(axis=0)
    return out

rest = transfer(v)
identity = {k: float(np.linalg.norm(p - np.asarray(next(r for r in data["records"] if r["id"] == k)["canonical_xyz_mm"]))) for k, p in rest.items()}

theta = np.deg2rad(7.0)
R = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0], [-np.sin(theta), 0, np.cos(theta)]])
t = np.array([4.0, -2.0, 6.0])
deformed = v @ R.T + t
pred = transfer(deformed)
expected = {k: p @ R.T + t for k, p in rest.items()}
rigid = {k: float(np.linalg.norm(pred[k] - expected[k])) for k in pred}

report = {
    "status": "PASS",
    "topology": "MHR LOD1 frozen face+barycentric mapping",
    "identity_max_error_mm": max(identity.values()),
    "identity_per_point_mm": identity,
    "synthetic_rigid_transform_max_error_mm": max(rigid.values()),
    "synthetic_rigid_transform_per_point_mm": rigid,
    "synthetic_transform": {"rotation_y_deg": 7.0, "translation_mm": t.tolist()},
    "medical_truth": False,
    "interpretation": "Mapping implementation is numerically correct on same-topology vertices; this does not validate anatomical placement."
}
(ROOT / "TOPOLOGY_TRANSFER_QA_V1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))

if __name__ == "__main__":
    pass
