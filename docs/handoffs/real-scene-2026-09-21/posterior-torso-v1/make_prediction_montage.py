from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
PRED = ROOT / "prediction_propagation_v1"
RAW = ROOT.parents[1] / "real-scene-2026-09-11" / "back-dmd37-engineering-validation-v1" / "raw"
f = np.load(RAW / "mhr_faces.npy")
canvas = Image.new("RGB", (1500, 420), "white")
for i, name in enumerate(["B1", "B2", "B3", "B4", "B5"]):
    data = json.loads((PRED / name / "PROPAGATED_POINTS.json").read_text(encoding="utf-8"))
    npz = np.load(Path(data["source"]), allow_pickle=True)
    v = np.asarray(npz["pred_vertices"], dtype=float)
    pts = np.asarray([x["xyz"] for x in data["acupoints"]])
    a, b = 0, 1
    mn, mx = v[:, [a, b]].min(axis=0), v[:, [a, b]].max(axis=0)
    scale = 350.0 / max(mx - mn)
    ox = i * 300 + 8
    draw = ImageDraw.Draw(canvas)
    draw.text((ox, 8), f"{name}: propagated points", fill="black")
    # light point-cloud silhouette for robust display without a graphics stack
    stride = max(1, len(v) // 3000)
    for p in v[::stride]:
        x = ox + 10 + (p[a] - mn[0]) * scale
        y = 390 - (p[b] - mn[1]) * scale
        draw.ellipse((x, y, x+1, y+1), fill=(210, 210, 210))
    for q, rec in zip(pts, data["acupoints"]):
        x = ox + 10 + (q[a] - mn[0]) * scale
        y = 390 - (q[b] - mn[1]) * scale
        draw.ellipse((x-4, y-4, x+4, y+4), fill=(25, 65, 220), outline="black")
        draw.text((x+5, y-5), rec["id"], fill="black")
canvas.save(ROOT / "prediction_acupoint_montage.png")
print(ROOT / "prediction_acupoint_montage.png")
