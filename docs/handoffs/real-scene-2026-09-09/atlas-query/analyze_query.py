"""Compare three Atlas propagation routes; distances measure consistency, not accuracy."""
import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/video_runtime'))

import cv2
import numpy as np


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def project(xyz, intrinsic):
    homogeneous = xyz @ intrinsic.T
    return homogeneous[:, :2] / homogeneous[:, 2:3]


def interpolate(vertices, indices, weights):
    return np.sum(vertices[indices] * weights[..., None], axis=1)


def stats(values):
    values = np.asarray(values)
    return {"mean": float(values.mean()), "median": float(np.median(values)),
            "p95": float(np.percentile(values, 95)), "max": float(values.max())}


def read_image(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def save_image(path, image):
    cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 94])[1].tofile(path)


def panel(image, xy, width, height, title):
    image = image.copy()
    h, w = image.shape[:2]
    scaled = xy * np.array([w / width, h / height])
    for number, (x, y) in enumerate(scaled, 1):
        if not np.isfinite([x, y]).all():
            continue
        x, y = int(round(x)), int(round(y))
        cv2.circle(image, (x, y), 4, (0, 0, 0), -1)
        cv2.circle(image, (x, y), 2, (0, 255, 255), -1)
        cv2.putText(image, str(number), (x + 4, y - 3), cv2.FONT_HERSHEY_SIMPLEX,
                    .38, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(image, str(number), (x + 4, y - 3), cv2.FONT_HERSHEY_SIMPLEX,
                    .38, (0, 255, 255), 1, cv2.LINE_AA)
    image = cv2.copyMakeBorder(image, 42, 0, 0, 0, cv2.BORDER_CONSTANT, value=(28, 28, 28))
    cv2.putText(image, title, (10, 27), cv2.FONT_HERSHEY_SIMPLEX,
                .55, (255, 255, 255), 1, cv2.LINE_AA)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--dev-root", type=Path)
    parser.add_argument("--native-binding", type=Path)
    args = parser.parse_args()
    root = args.root
    dev = args.dev_root or root.parent / "2026-09-08_SAM_NLF_DEV40"
    native_path = args.native_binding or root.parent / "2026-09-07_MHR_NATIVE_ATLAS_PROPAGATION/native_binding.json"
    binding = read_json(root / "binding.json")
    points = binding["points"]
    native = {p["point_id"]: p for p in read_json(native_path)["points"]}
    indices = np.array([p["vertex_indices"] for p in points])
    weights = np.array([p["barycentric"] for p in points])
    support_indices = np.array(binding["support_query_indices"])
    native_indices = np.array([native[p["point_id"]]["vertex_indices"] for p in points])
    native_weights = np.array([native[p["point_id"]]["barycentric"] for p in points])
    manifest = {row["id"]: row for row in read_json(dev / "manifest.json")}
    rows, images, comparisons = [], [], []
    ids = ["B1", "B2", "B3", "B4", "B5", "N1"]
    for image_id in ids:
        dest, previous = root / image_id, dev / image_id
        query = np.load(dest / "query.npz")
        sam = np.load(previous / "sam.npz")
        fitted = np.load(previous / "nlf.npz")
        intrinsic = np.asarray(query["K"], dtype=float).reshape(3, 3)
        xyz_query = query["poses3d"][0]
        direct = xyz_query[:len(points)]
        support = interpolate(xyz_query, support_indices, weights)
        surface = interpolate(fitted["vertices3d"][0], indices, weights)
        sam_xyz = interpolate(sam["vertices_camera"], native_indices, native_weights) * 1000
        positions = {"sam": sam_xyz, "fitted": surface, "direct": direct, "support": support}
        xy = {name: project(value, intrinsic) for name, value in positions.items()}
        distances = {}
        for left, right in [("direct", "fitted"), ("direct", "support"), ("sam", "fitted"), ("sam", "direct")]:
            distances[f"{left}_vs_{right}_mm"] = np.linalg.norm(positions[left] - positions[right], axis=1)
            distances[f"{left}_vs_{right}_px"] = np.linalg.norm(xy[left] - xy[right], axis=1)
        # The supplied poses2d is retained as an API consistency check, not used
        # for barycentric interpolation, since perspective projection is nonlinear.
        distances["direct_projection_vs_api2d_px"] = np.linalg.norm(xy["direct"] - query["poses2d"][0, :len(points)], axis=1)
        uncertainty = np.asarray(query["uncertainties"]).reshape(binding["query_count"], -1)
        for i, point in enumerate(points):
            row = {"image_id": image_id, "number": i + 1, "point_id": point["point_id"],
                   "reference_code": point["reference_code"], "side": point["side"]}
            row.update({name: float(value[i]) for name, value in distances.items()})
            for name in positions:
                row.update({f"{name}_{axis}_mm": float(value) for axis, value in zip("xyz", positions[name][i])})
                row.update({f"{name}_{axis}_px": float(value) for axis, value in zip("uv", xy[name][i])})
            row["direct_uncertainty_raw"] = json.dumps(uncertainty[i].tolist())
            rows.append(row)
        item = manifest[image_id]
        panels = [panel(read_image(previous / filename), xy[name], item["width"], item["height"], title)
                  for filename, name, title in [
                      ("sam_overlay.jpg", "sam", f"{image_id} | SAM / old MHR binding"),
                      ("nlf_overlay.jpg", "fitted", f"{image_id} | NLF fitted SMPL surface"),
                      ("original_display.jpg", "direct", f"{image_id} | NLF direct queries")]]
        comparison = np.concatenate(panels, axis=1)
        save_image(dest / "comparison.jpg", comparison)
        comparisons.append(comparison)
        images.append({"id": image_id, "point_count": len(points),
                       "consistency_distances": {name: stats(value) for name, value in distances.items()},
                       "nonpositive_depth_counts": {name: int((value[:, 2] <= 0).sum()) for name, value in positions.items()},
                       "comparison": f"{image_id}/comparison.jpg"})
    metric_names = list(distances)
    analysis = {
        "status": "MODEL_AND_BINDING_CONSISTENCY_ONLY_NOT_ACCURACY",
        "medical_truth": False, "images": images,
        "aggregate": {name: stats([row[name] for row in rows]) for name in metric_names},
        "units": {"3d_distances": "mm", "2d_distances": "original_input_pixels", "uncertainties": "raw_model_output"},
        "methods": {"sam": "Old MHR native binding on SAM camera vertices, m converted to mm",
                    "fitted": "Original SKEL vertex indices and weights on NLF fitted SMPL vertices",
                    "direct": "First 37 NLF canonical surface queries",
                    "support": "Barycentric interpolation of directly queried supporting vertices",
                    "projection": "Project every resulting 3D point with query K; do not interpolate 2D vertices"},
        "limitations": ["No medical or patient ground truth: these are agreement distances, not localization accuracy.",
                        "SAM comparisons conflate reconstruction differences and the old nearest-neighbor binding bridge.",
                        "Direct versus fitted also includes fitting and inference-run differences.",
                        "Direct versus support measures continuous-field interpolation consistency.",
                        "All 37 points are displayed, including occluded/back-surface points; no visibility validation."]}
    (root / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    with (root / "points.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    tiles = []
    tile_w = 1500
    for comparison in comparisons:
        tiles.append(cv2.resize(comparison, (tile_w, round(comparison.shape[0] * tile_w / comparison.shape[1]))))
    save_image(root / "overview.jpg", np.concatenate(tiles, axis=0))
    print(json.dumps({"images": len(images), "points": len(rows), "analysis": str(root / "analysis.json")}))


if __name__ == "__main__":
    main()
