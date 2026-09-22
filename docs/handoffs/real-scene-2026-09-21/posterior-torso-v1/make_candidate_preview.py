from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
RAW = ROOT.parents[1] / "real-scene-2026-09-11" / "back-dmd37-engineering-validation-v1" / "raw"
MASK = ROOT / "candidate_posterior_mask.json"
OUT = ROOT / "candidate_posterior_preview.png"

v = np.load(RAW / "mhr_rest_vertices.npy")
f = np.load(RAW / "mhr_faces.npy")
ids = np.array(json.loads(MASK.read_text(encoding="utf-8"))["face_ids"], dtype=int)
tri = v[f[ids]]

canvas = Image.new("RGB", (1500, 520), "white")
views = [("posterior", (0, 1)), ("oblique", (0, 2)), ("side", (1, 2))]
mins, maxs = v.min(axis=0), v.max(axis=0)
for i, (name, (a, b)) in enumerate(views):
    draw = ImageDraw.Draw(canvas)
    ox = i * 500 + 15
    draw.text((ox, 12), f"candidate {name} / {len(ids)} faces", fill="black")
    scale = 450.0 / max(maxs[a] - mins[a], maxs[b] - mins[b])
    for t in tri:
        pts = []
        for p in t:
            pts.append((ox + 20 + (p[a] - mins[a]) * scale, 490 - (p[b] - mins[b]) * scale))
        draw.polygon(pts, fill=(228, 87, 86))
canvas.save(OUT)
print(OUT)
