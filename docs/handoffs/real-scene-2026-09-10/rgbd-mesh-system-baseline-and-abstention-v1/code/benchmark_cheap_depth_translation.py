"""Measure correction-only latency; excludes SAM forward and held-out evaluation."""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
import torch

from audit_cheap_depth_translation import load, robust_translation, surface_anchors


def main():
    ap = argparse.ArgumentParser()
    for name in ("sam-repo", "official", "mhr", "rows", "anchors", "out"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(); sys.path.insert(0, str(args.sam_repo))
    from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    rows = load(args.rows)["rows"]
    model, cfg = load_sam_3d_body(str(args.official), device="cuda", mhr_path=str(args.mhr))
    model.eval(); estimator = SAM3DBodyEstimator(model, cfg)
    faces = model.head_pose.faces.cpu().numpy().astype(np.int64)
    spec_npz = np.load(args.anchors)
    spec = spec_npz["face_index"], spec_npz["barycentric"].astype(np.float64)
    inference, tz_latency, txyz_latency = [], [], []
    with torch.no_grad():
        for row in rows:
            with np.load(row["path"]) as z:
                rgb, bbox, K, points = z["rgb_a"].copy(), z["bbox_a"].copy(), z["K_a"].copy(), z["points_a"].astype(np.float64)
            torch.cuda.synchronize(); start = time.perf_counter()
            batch = recursive_to(prepare_batch(rgb, estimator.transform, bbox[None].astype(np.float32), None, None), "cuda")
            batch["cam_int"] = torch.as_tensor(K[None], device="cuda").to(batch["img"])
            model._initialize_batch(batch); pred = model.forward_step(batch, decoder_type="body")["mhr"]
            vertices = (pred["pred_vertices"] + pred["pred_cam_t"][:, None])[0].cpu().numpy()
            torch.cuda.synchronize(); inference.append(time.perf_counter() - start)
            anchors = surface_anchors(vertices, faces, *spec)
            start = time.perf_counter(); robust_translation(points, anchors, "tz"); tz_latency.append(time.perf_counter() - start)
            start = time.perf_counter(); robust_translation(points, anchors, "txyz"); txyz_latency.append(time.perf_counter() - start)
    result = {"status":"PASS_CORRECTION_ONLY_LATENCY_MEASURED", "frame_count":len(rows),
              "official_forward_p50_s":float(np.median(inference)), "official_forward_p90_s":float(np.quantile(inference,.9)),
              "tz_correction_p50_s":float(np.median(tz_latency)), "tz_correction_p90_s":float(np.quantile(tz_latency,.9)),
              "txyz_correction_p50_s":float(np.median(txyz_latency)), "txyz_correction_p90_s":float(np.quantile(txyz_latency,.9)),
              "scope":"CPU scipy cKDTree correction only; excludes depth preprocessing and Camera-B evaluation"}
    args.out.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))


if __name__ == "__main__": main()
