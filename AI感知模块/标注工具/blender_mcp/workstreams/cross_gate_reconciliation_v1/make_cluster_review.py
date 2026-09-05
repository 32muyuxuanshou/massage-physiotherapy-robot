from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def camera_contract(probe: dict) -> tuple[np.ndarray, float, float, float, float]:
    matrix = np.asarray(probe["camera"]["world_to_opencv"], dtype=np.float64)
    rows = probe["points"]
    x = np.asarray([item["xyz_camera_opencv_m"][0] / item["xyz_camera_opencv_m"][2] for item in rows])
    y = np.asarray([item["xyz_camera_opencv_m"][1] / item["xyz_camera_opencv_m"][2] for item in rows])
    u = np.asarray([item["uv_pixel_opencv"][0] for item in rows])
    v = np.asarray([item["uv_pixel_opencv"][1] for item in rows])
    fx, cx = np.linalg.lstsq(np.column_stack([x, np.ones_like(x)]), u, rcond=None)[0]
    fy, cy = np.linalg.lstsq(np.column_stack([y, np.ones_like(y)]), v, rcond=None)[0]
    return matrix, float(fx), float(fy), float(cx), float(cy)


def project(world: list[float], contract) -> tuple[float, float]:
    matrix, fx, fy, cx, cy = contract
    camera = matrix @ np.asarray([*world, 1.0])
    return fx * camera[0] / camera[2] + cx, fy * camera[1] / camera[2] + cy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    controls = read(args.root / "control_reconciliation_report.json")["controls"]
    benchmarks = read(args.root / "overlap_benchmark_report.json")["benchmarks"]
    rows = [("controls", item) for item in controls if item["status"] != "CROSS_QUALIFIED"]
    rows += [("benchmarks", item) for item in benchmarks]
    columns, thumb = 3, (640, 512)
    row_count = math.ceil(len(rows) / columns)
    canvas = Image.new("RGB", (columns * thumb[0], row_count * (thumb[1] + 44)), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    review_rows = []
    for index, (phase, item) in enumerate(rows):
        identifier = item["case_id"]
        probe = read(args.root / phase / "probes" / f"{identifier}.json")
        narrow = read(args.root / phase / "narrow" / f"{identifier}.json")
        clusters = {cluster["cluster_id"]: cluster for cluster in narrow["clusters"]}
        flagged_ids = {cluster["cluster_id"] for cluster in item.get("new_clusters", [])}
        flagged_ids.update(record["cluster_id"] for record in item.get("severity_escalations", []))
        contract = camera_contract(probe)
        source = Image.open(args.root / phase / "previews" / f"{identifier}.png").convert("RGB")
        source.thumbnail(thumb, Image.Resampling.LANCZOS)
        scale_x, scale_y = source.width / probe["camera"]["resolution"][0], source.height / probe["camera"]["resolution"][1]
        local_draw = ImageDraw.Draw(source)
        projected = []
        for cluster_id in sorted(flagged_ids):
            cluster = clusters[cluster_id]
            u, v = project(cluster["center_world_m"], contract)
            x, y = u * scale_x, v * scale_y
            radius = 10
            local_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 220, 0), outline=(210, 25, 25), width=4)
            local_draw.text((x + 12, y - 8), cluster_id, fill=(160, 0, 0), font=font)
            projected.append({"cluster_id": cluster_id, "uv": [u, v], "coarse_region": cluster["coarse_region"], "pair_count": cluster["confirmed_pair_count"], "max_segment_mm": cluster["max_segment_length_m"] * 1000.0, "max_crossing_depth_proxy_mm": cluster["max_crossing_depth_proxy_m"] * 1000.0})
        x0, y0 = (index % columns) * thumb[0], (index // columns) * (thumb[1] + 44)
        canvas.paste(source, (x0 + (thumb[0] - source.width) // 2, y0 + 40))
        draw.text((x0 + 5, y0 + 5), identifier[:56], fill="black", font=font)
        draw.text((x0 + 5, y0 + 19), item["status"], fill=(210, 100, 0), font=font)
        review_rows.append({"case_id": identifier, "phase": phase, "status": item["status"], "flagged_clusters": projected})
    output = args.root / "cluster_caution_review.png"
    canvas.save(output)
    (args.root / "cluster_caution_review.json").write_text(json.dumps({"schema": "cluster-caution-visual-review-v1", "cases": review_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
