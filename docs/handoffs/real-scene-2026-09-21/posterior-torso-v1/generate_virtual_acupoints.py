"""Create provisional engineering acupoint anchors on the frozen MHR surface.

The coordinates are an engineering initialization from vertebral-level and
midline/lateral rules. They are explicitly not clinical ground truth.
"""
from pathlib import Path
import hashlib, json
import numpy as np

ROOT = Path(__file__).parent
RAW = ROOT.parents[1] / "real-scene-2026-09-11" / "back-dmd37-engineering-validation-v1" / "raw"
MASK = ROOT / "candidate_posterior_mask.json"
OUT = ROOT / "VIRTUAL_ACUPOINTS_ENGINEERING_V1.json"

v = np.load(RAW / "mhr_rest_vertices.npy")
f = np.load(RAW / "mhr_faces.npy")
mask = json.loads(MASK.read_text(encoding="utf-8"))
face_ids = np.asarray(mask["face_ids"], dtype=int)
candidate_vertices = np.unique(f[face_ids].reshape(-1))

# y-levels and lateral offsets are initialization coordinates only. The WHO
# standard supplies the relative vertebral/lateral rules; MHR y is not a
# clinical vertebral measurement.
spec = [
    ("BL13_L", "Feishu", "left", 87.0, -11.0, "T3, 1.5 B-cun lateral"),
    ("BL13_R", "Feishu", "right", 87.0, 11.0, "T3, 1.5 B-cun lateral"),
    ("BL15_L", "Xinshu", "left", 99.0, -11.5, "T5, 1.5 B-cun lateral"),
    ("BL15_R", "Xinshu", "right", 99.0, 11.5, "T5, 1.5 B-cun lateral"),
    ("BL18_L", "Ganshu", "left", 116.0, -12.0, "T9, 1.5 B-cun lateral"),
    ("BL18_R", "Ganshu", "right", 116.0, 12.0, "T9, 1.5 B-cun lateral"),
    ("GV14", "Dazhui", "midline", 79.0, 0.0, "posterior median line, C7/T1 level"),
    ("GV4", "Mingmen", "midline", 139.0, 0.0, "posterior median line, L2 level"),
]

def sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

records = []
for key, name, side, y0, x0, rule in spec:
    # Select a local posterior surface point: closest candidate vertex in x/y,
    # then choose the most posterior (minimum z) within the local band.
    dy = np.abs(v[candidate_vertices, 1] - y0)
    dx = np.abs(v[candidate_vertices, 0] - x0)
    d = dy + dx
    pool = candidate_vertices[(dy < 3.0) & (dx < 8.0)]
    if len(pool) == 0:
        pool = candidate_vertices[np.argsort(d)[:20]]
    vid = int(pool[np.argmin(v[pool, 2])])
    xyz = v[vid].tolist()
    incident = np.flatnonzero(np.any(f == vid, axis=1))
    incident = [int(i) for i in incident if int(i) in set(face_ids)]
    face = incident[0] if incident else int(face_ids[np.argmin(np.linalg.norm(v[f[face_ids]].mean(axis=1) - v[vid], axis=1))])
    bary = [1.0 if int(x) == vid else 0.0 for x in f[face]]
    records.append({
        "id": key, "name": name, "laterality": side,
        "face_index": face, "barycentric": bary,
        "canonical_xyz_mm": xyz, "placement_rule": rule,
        "source": "WHO standard location rule + engineering MHR surface projection",
        "virtual_engineering_label": True, "medical_truth": False,
        "review_status": "PROVISIONAL_NO_CLINICIAN_VALIDATION"
    })

payload = {
    "schema": "VIRTUAL_ACUPOINTS_ENGINEERING_V1",
    "status": "PROVISIONAL_ENGINEERING_ONLY",
    "medical_truth": False,
    "mesh_contract": "POSTERIOR_TORSO_V1",
    "mesh_hashes": {"rest_vertices_sha256": sha(v), "faces_sha256": sha(f)},
    "records": records,
    "warning": "These points are not clinical ground truth and must not be used for patient treatment without qualified clinical review."
}
OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(OUT)
