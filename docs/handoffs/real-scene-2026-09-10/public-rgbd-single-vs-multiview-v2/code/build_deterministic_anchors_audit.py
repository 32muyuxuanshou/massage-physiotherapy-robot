import argparse, hashlib, json, time
from pathlib import Path

import numpy as np
import torch


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sam-repo", type=Path, required=True)
    ap.add_argument("--official", type=Path, required=True)
    ap.add_argument("--mhr", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20260910)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    import sys
    sys.path.insert(0, str(args.sam_repo))
    from sam_3d_body import load_sam_3d_body

    model, _ = load_sam_3d_body(str(args.official), device="cuda", mhr_path=str(args.mhr))
    faces = model.head_pose.faces.detach().cpu().numpy().astype("<i8", copy=False)
    vertex_count = int(faces.max()) + 1
    rng = np.random.default_rng(args.seed)
    ids = rng.choice(len(faces), 16384, replace=len(faces) < 16384).astype("<i8")
    bary = rng.dirichlet(np.ones(3), 16384).astype("<f4")
    binary = args.out / "MHR_DETERMINISTIC_SURFACE_ANCHORS_V1.npz"
    np.savez(binary, face_index=ids, barycentric=bary)
    loaded = np.load(binary)
    exact = np.array_equal(ids, loaded["face_index"]) and np.array_equal(bary, loaded["barycentric"])

    # Isolate the dominant sampled-surface-to-observation cdist cost on the target GPU.
    # Synthetic vertices/observations are sufficient for cost and gradient-budget validation.
    torch.manual_seed(17)
    verts = torch.randn((1, vertex_count, 3), device="cuda", dtype=torch.float32) * 0.3
    obs_a = torch.randn((2048, 3), device="cuda", dtype=torch.float32) * 0.3
    obs_b = torch.randn((2048, 3), device="cuda", dtype=torch.float32) * 0.3
    f = torch.as_tensor(faces, device="cuda", dtype=torch.long)
    results = []
    grads = {}
    for label, count, observations in [("single_16384", 16384, [obs_a]), ("multi_8192_plus_8192", 8192, [obs_a, obs_b])]:
        times = []
        norms = []
        peak = []
        for _ in range(3):
            v = verts.detach().clone().requires_grad_(True)
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize(); start = time.perf_counter()
            view_losses = []
            for vi, obs in enumerate(observations):
                off = vi * count
                fid = torch.as_tensor(ids[off:off+count], device="cuda", dtype=torch.long)
                bw = torch.as_tensor(bary[off:off+count], device="cuda")
                surf = (v[:, f[fid]] * bw[None, :, :, None]).sum(2)
                d = torch.cdist(obs[None], surf).amin(-1)[0]
                view_losses.append(torch.where(d < .03, .5*d.square()/.03, d-.015).mean())
            loss = torch.stack(view_losses).mean()
            loss.backward(); torch.cuda.synchronize()
            times.append((time.perf_counter()-start)*1000)
            norms.append(float(v.grad.norm()))
            peak.append(torch.cuda.max_memory_allocated()/2**20)
        results.append({"arm": label, "total_anchor_budget": 16384,
                        "view_anchor_budget": count, "views": len(observations),
                        "median_forward_backward_ms": float(np.median(times)),
                        "median_peak_allocated_mib": float(np.median(peak)),
                        "median_vertex_gradient_norm": float(np.median(norms))})
        grads[label] = float(np.median(norms))

    manifest = {
        "status": "FROZEN_TOPOLOGY_BOUND_ANCHORS",
        "algorithm": "numpy PCG64 uniform face-index without replacement when topology permits; Dirichlet(1,1,1) barycentric",
        "seed": args.seed, "anchor_count": 16384,
        "topology": {"vertex_count_index_bound": vertex_count, "face_count": int(len(faces)),
                     "faces_sha256": digest_bytes(faces.tobytes())},
        "arrays": {"face_index": {"dtype": str(ids.dtype), "shape": list(ids.shape), "sha256": digest_bytes(ids.tobytes())},
                   "barycentric": {"dtype": str(bary.dtype), "shape": list(bary.shape), "sha256": digest_bytes(bary.tobytes())}},
        "binary_file": binary.name, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "reuse_contract": "The exact same binary and ordered anchors are used by S and M for every update, epoch and seed."
    }
    validation = {"status": "PASS_DETERMINISTIC_SURFACE_ANCHORS" if exact else "FAIL",
                  "roundtrip_exact": exact, "barycentric_sum_max_abs_error": float(np.max(np.abs(bary.sum(1)-1))),
                  "face_indices_valid": bool(ids.min() >= 0 and ids.max() < len(faces)),
                  "barycentric_nonnegative": bool((bary >= 0).all()), "cost_benchmark": results,
                  "benchmark_scope": "isolated CUDA cdist+surface interpolation+backward, synthetic vertices and observations; excludes SAM forward",
                  "feasibility": "PASS_2080TI" if max(r["median_peak_allocated_mib"] for r in results) < 10000 else "NOT_READY_MEMORY"}
    ratio = grads["multi_8192_plus_8192"] / grads["single_16384"]
    fairness = {"status": "PASS_CONTRACT_AND_SYNTHETIC_GRADIENT_SCALE" if 0.5 <= ratio <= 2 else "FAIL_GRADIENT_SCALE",
                "fixed_total_surface_anchor_budget": 16384,
                "single": {"views": 1, "anchors_per_view": [16384], "view_reduction": "mean"},
                "multi": {"views": 2, "anchors_per_view": [8192,8192], "within_view_reduction": "mean", "across_view_reduction": "mean"},
                "synthetic_vertex_gradient_norm_ratio_multi_over_single": ratio,
                "evidence_boundary": "Contract and synthetic scale test only; a matched real DEV model-state blockwise pose/camera gradient audit remains required before READY."}
    for name, obj in [("MHR_DETERMINISTIC_SURFACE_ANCHORS_V1.json", manifest),
                      ("DETERMINISTIC_SURFACE_SAMPLING_VALIDATION_V1.json", validation),
                      ("SINGLE_MULTI_GRADIENT_BUDGET_AUDIT_V1.json", fairness)]:
        (args.out/name).write_text(json.dumps(obj, indent=2)+"\n")

if __name__ == "__main__": main()
