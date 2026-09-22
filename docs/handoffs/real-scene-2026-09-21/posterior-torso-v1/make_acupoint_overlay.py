from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
RAW = ROOT.parents[1] / "real-scene-2026-09-11" / "back-dmd37-engineering-validation-v1" / "raw"
v = np.load(RAW / "mhr_rest_vertices.npy")
f = np.load(RAW / "mhr_faces.npy")
mask = json.loads((ROOT / "candidate_posterior_mask.json").read_text(encoding="utf-8"))
pts = json.loads((ROOT / "VIRTUAL_ACUPOINTS_ENGINEERING_V1.json").read_text(encoding="utf-8"))["records"]
tri = v[f[np.asarray(mask["face_ids"], dtype=int)]]
points = np.asarray([p["canonical_xyz_mm"] for p in pts])
mins, maxs = v.min(axis=0), v.max(axis=0)
canvas = Image.new("RGB", (1500, 520), "white")
views = [("posterior", (0, 1)), ("oblique", (0, 2)), ("side", (1, 2))]
for i, (name, (a, b)) in enumerate(views):
    draw = ImageDraw.Draw(canvas)
    ox = i * 500 + 15
    draw.text((ox, 12), f"{name}: posterior mask + 8 virtual points", fill="black")
    scale = 450.0 / max(maxs[a] - mins[a], maxs[b] - mins[b])
    def xy(p):
        return (ox + 20 + (p[a] - mins[a]) * scale, 490 - (p[b] - mins[b]) * scale)
    for t in tri:
        draw.polygon([xy(p) for p in t], fill=(230, 120, 120))
    for p, rec in zip(points, pts):
        q = xy(p); r = 5
        draw.ellipse((q[0]-r, q[1]-r, q[0]+r, q[1]+r), fill=(20, 70, 220), outline="black")
        if name == "posterior":
            draw.text((q[0]+6, q[1]-6), rec["id"], fill="black")
canvas.save(ROOT / "posterior_acupoint_overlay.png")
print(ROOT / "posterior_acupoint_overlay.png")
