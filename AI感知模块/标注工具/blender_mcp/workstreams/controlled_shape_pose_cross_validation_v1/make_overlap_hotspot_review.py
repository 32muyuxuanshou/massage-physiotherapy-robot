from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_obj(path: Path) -> tuple[np.ndarray, np.ndarray]:
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("v "):
                vertices.append([float(value) for value in line.split()[1:4]])
            elif line.startswith("f "):
                faces.append([int(value.split("/")[0]) - 1 for value in line.split()[1:4]])
    return np.asarray(vertices, dtype=np.float64), np.asarray(faces, dtype=np.int64)


def project(point: np.ndarray, axes: tuple[int, int], bounds: tuple[np.ndarray, np.ndarray], box: tuple[int, int, int, int]) -> tuple[int, int]:
    minimum, maximum = bounds
    x0, y0, x1, y1 = box
    horizontal = (point[axes[0]] - minimum[axes[0]]) / max(maximum[axes[0]] - minimum[axes[0]], 1e-12)
    vertical = (point[axes[1]] - minimum[axes[1]]) / max(maximum[axes[1]] - minimum[axes[1]], 1e-12)
    return int(x0 + horizontal * (x1 - x0)), int(y1 - vertical * (y1 - y0))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--case", action="append", required=True)
    args = parser.parse_args()

    report = read_json(args.root / "geometry_preflight_report.json")
    by_id = {item["case_id"]: item for item in report["cells"]}
    width, row_height = 1600, 620
    canvas = Image.new("RGB", (width, row_height * len(args.case)), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    result_rows = []

    for row_index, case_id in enumerate(args.case):
        case = by_id[case_id]
        obj = args.root / "diagnostics" / "manual_review" / case_id / "native" / "skin_female.obj"
        vertices, faces = load_obj(obj)
        minimum, maximum = vertices.min(axis=0), vertices.max(axis=0)
        bounds = (minimum, maximum)
        base_y = row_index * row_height
        front_box = (30, base_y + 70, 760, base_y + 590)
        side_box = (840, base_y + 70, 1570, base_y + 590)
        draw.text((30, base_y + 12), f"{case_id} | {case['status']} | interaction-new={case['interaction_new_pair_count']}", fill="black", font=font)
        draw.text((30, base_y + 34), "left: native X-Y view; right: native Z-Y side view; red triangles are interaction-only new overlap pairs", fill=(70, 70, 70), font=font)
        for box, axes, title in ((front_box, (0, 1), "X-Y"), (side_box, (2, 1), "Z-Y")):
            draw.rectangle(box, outline=(80, 80, 80), width=1)
            draw.text((box[0] + 5, box[1] + 5), title, fill=(30, 30, 30), font=font)
            step = max(1, len(vertices) // 5000)
            for vertex in vertices[::step]:
                x, y = project(vertex, axes, bounds, box)
                draw.point((x, y), fill=(178, 190, 198))

        pair_rows = []
        for pair_index, (face_a, face_b) in enumerate(case["interaction_new_pairs"], start=1):
            centroids = []
            for face_index in (face_a, face_b):
                triangle = vertices[faces[face_index]]
                centroids.append(triangle.mean(axis=0))
                for box, axes in ((front_box, (0, 1)), (side_box, (2, 1))):
                    polygon = [project(vertex, axes, bounds, box) for vertex in triangle]
                    draw.line(polygon + [polygon[0]], fill=(220, 25, 30), width=3)
            midpoint = (centroids[0] + centroids[1]) / 2.0
            distance_mm = float(np.linalg.norm(centroids[0] - centroids[1]) * 1000.0)
            for box, axes in ((front_box, (0, 1)), (side_box, (2, 1))):
                x, y = project(midpoint, axes, bounds, box)
                draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(255, 220, 30), outline=(180, 20, 20), width=2)
                draw.text((x + 8, y - 8), str(pair_index), fill=(160, 0, 0), font=font)
            pair_rows.append({
                "pair_number": pair_index,
                "faces": [face_a, face_b],
                "centroid_a_native_m": centroids[0].tolist(),
                "centroid_b_native_m": centroids[1].tolist(),
                "midpoint_native_m": midpoint.tolist(),
                "centroid_distance_mm": distance_mm,
            })
        result_rows.append({
            "case_id": case_id,
            "status_before_manual_review": case["status"],
            "ring2_overlap_pair_count": case["ring2_overlap_pair_count"],
            "ring3_new_pair_count": case["ring3_new_pair_count"],
            "interaction_new_pair_count": case["interaction_new_pair_count"],
            "native_bounds_m": {"minimum": minimum.tolist(), "maximum": maximum.tolist()},
            "pairs": pair_rows,
        })

    output_dir = args.root / "diagnostics" / "manual_review"
    output_dir.mkdir(parents=True, exist_ok=True)
    canvas.save(output_dir / "overlap_hotspot_review.png")
    (output_dir / "overlap_hotspot_review.json").write_text(
        json.dumps({"schema": "manual-overlap-hotspot-review-v1", "cases": result_rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
