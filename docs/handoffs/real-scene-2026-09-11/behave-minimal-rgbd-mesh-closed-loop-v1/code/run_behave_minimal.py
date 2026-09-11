"""Frozen SAM 3D Body + Camera-A-only translation fit + Camera-B exam on BEHAVE."""
import argparse, csv, hashlib, json, sys, time
from pathlib import Path

import cv2
import numpy as np
import torch
from scipy.spatial import cKDTree

FRAMES = {
    "Date01_Sub01_backpack_back": "t0008.000",
    "Date01_Sub01_stool_sit": "t0034.000",
    "Date01_Sub01_yogaball_play": "t0031.000",
}
ITERATIONS, TRIM, STEP_BOUND, TOTAL_BOUND = 6, .20, .05, .18


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_calib(root, kid):
    p = root / "intrinsics" / str(kid) / "calibration.json"
    j = json.loads(p.read_text())
    c = j["color"]
    K = np.array([[c["fx"], 0, c["cx"]], [0, c["fy"], c["cy"]], [0, 0, 1.]], float)
    dist = np.asarray(c["opencv"][4:], float)
    table = np.load(root / "intrinsics" / str(kid) / "pointcloud_table.npy")
    q = json.loads((root / "Date01" / "config" / str(kid) / "config.json").read_text())
    R = np.asarray(q["rotation"], float).reshape(3, 3)
    t = np.asarray(q["translation"], float)
    return K, dist, table, R, t, [str(p), str(root / "intrinsics" / str(kid) / "pointcloud_table.npy"), str(root / "Date01" / "config" / str(kid) / "config.json")]


def depth_points(depth, mask, table):
    good = (depth > 0) & (mask > 127)
    rays = np.dstack([table, np.ones(table.shape[:2], table.dtype)])
    return rays[good].astype(float) * (depth[good, None].astype(float) / 1000.)


def local_to_world(p, R, t):
    return p @ R.T + t


def world_to_local(p, R, t):
    return (p - t) @ R


def robust_translation(points, anchors):
    t = np.zeros(3); trace = []
    idx = np.linspace(0, len(points)-1, min(25000, len(points)), dtype=int)
    points = points[idx]
    for i in range(ITERATIONS):
        moved = anchors + t
        dist, near = cKDTree(moved).query(points, workers=-1)
        threshold = float(np.quantile(dist, 1-TRIM)); keep = dist <= threshold
        step = np.clip(np.median(points[keep] - moved[near[keep]], axis=0), -STEP_BOUND, STEP_BOUND)
        t += step
        trace.append({"iteration": i+1, "step_m": step.tolist(), "translation_m": t.tolist(), "kept": int(keep.sum()), "threshold_m": threshold})
    return t, trace


def metric(points, verts, faces, point_to_triangle_distances, key):
    if len(points) > 5000:
        rng = np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:16], 16))
        points = points[np.sort(rng.choice(len(points), 5000, False))]
    d = point_to_triangle_distances(points, verts, faces) * 1000.
    return {"metric":"observed_to_exact_triangle_surface","sample_count":int(len(d)),"unit":"mm","mean_mm":float(d.mean()),"median_mm":float(np.median(d)),"p90_mm":float(np.percentile(d,90)),"p95_mm":float(np.percentile(d,95)),"max_mm":float(d.max()),"coverage_50mm":float(np.mean(d<50.))}


def project(v, K, dist):
    return cv2.projectPoints(v[:, None], np.zeros(3), np.zeros(3), K, dist)[0].reshape(-1, 2)


def render(rgb, verts, faces, K, dist, alpha=.88):
    uv = project(verts, K, dist); tri = verts[faces]
    order = np.argsort(tri[:, :, 2].mean(1))[::-1]
    normals = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0])
    normals /= np.linalg.norm(normals, axis=1, keepdims=True).clip(1e-8)
    shade = .62 + .34*np.abs(normals @ np.array([-.25, -.45, -.86]))
    mesh = rgb.copy(); H, W = rgb.shape[:2]
    for i in order:
        pts = np.rint(uv[faces[i]]).astype(np.int32)
        if np.all((pts[:, 0] < 0) | (pts[:, 0] >= W) | (pts[:, 1] < 0) | (pts[:, 1] >= H)):
            continue
        q = int(np.clip(245*shade[i], 150, 245))
        cv2.fillConvexPoly(mesh, pts, (q, q, q), cv2.LINE_AA)
        cv2.polylines(mesh, [pts], True, (120, 130, 140), 1, cv2.LINE_AA)
    mask = np.any(mesh != rgb, axis=2); out = rgb.copy()
    out[mask] = (rgb[mask]*(1-alpha) + mesh[mask]*alpha).astype(np.uint8)
    return out


def write_obj(path, v, f):
    with open(path, "w") as o:
        for x in v: o.write(f"v {x[0]:.7f} {x[1]:.7f} {x[2]:.7f}\n")
        for x in f: o.write(f"f {x[0]+1} {x[1]+1} {x[2]+1}\n")


def save(path, rgb):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def triptych(images, labels):
    ims = [cv2.resize(x, (640, 480)) for x in images]
    for im, label in zip(ims, labels):
        cv2.rectangle(im, (0, 0), (640, 38), (250, 250, 250), -1)
        cv2.putText(im, label, (14, 26), cv2.FONT_HERSHEY_SIMPLEX, .68, (20, 25, 30), 2, cv2.LINE_AA)
    return np.hstack(ims)


def main():
    p = argparse.ArgumentParser()
    for name in ["data", "calibs", "sam-repo", "checkpoint", "mhr", "anchors", "out"]:
        p.add_argument("--"+name, required=True, type=Path)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    sys.path[:0] = [str(a.sam_repo), "/raid5/xuhd/rgbd_mesh_system_v1"]
    from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    from surface_metrics import point_to_triangle_distances
    model, cfg = load_sam_3d_body(str(a.checkpoint), device="cuda", mhr_path=str(a.mhr)); model.eval()
    est = SAM3DBodyEstimator(model, cfg); faces = model.head_pose.faces.cpu().numpy().astype(np.int64)
    az = np.load(a.anchors); face_idx, bary = az["face_index"], az["barycentric"].astype(float)
    cal = {k: read_calib(a.calibs, k) for k in [0, 1]}; results = []
    torch.cuda.reset_peak_memory_stats()
    for seq_name, frame_name in FRAMES.items():
        sid = seq_name + "_" + frame_name.replace(".", "_"); frame = a.data / seq_name / frame_name
        rgbs=[]; depths=[]; masks=[]; points=[]
        for k in [0, 1]:
            bgr=cv2.imread(str(frame/f"k{k}.color.jpg")); rgbs.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            depths.append(cv2.imread(str(frame/f"k{k}.depth.png"), cv2.IMREAD_UNCHANGED))
            masks.append(cv2.imread(str(frame/f"k{k}.person_mask.jpg"), 0))
            points.append(depth_points(depths[-1], masks[-1], cal[k][2]))
        ys, xs = np.where(masks[0] > 127); pad=25
        bbox=np.array([[max(0,xs.min()-pad),max(0,ys.min()-pad),min(rgbs[0].shape[1]-1,xs.max()+pad),min(rgbs[0].shape[0]-1,ys.max()+pad)]],np.float32)
        batch=recursive_to(prepare_batch(rgbs[0],est.transform,bbox,None,None),"cuda")
        batch["cam_int"]=torch.as_tensor(cal[0][0][None],device="cuda").to(batch["img"])
        torch.cuda.synchronize(); start=time.perf_counter(); model._initialize_batch(batch)
        with torch.inference_mode(): pred=model.forward_step(batch,decoder_type="body")["mhr"]
        torch.cuda.synchronize(); sam_ms=(time.perf_counter()-start)*1000
        official=(pred["pred_vertices"]+pred["pred_cam_t"][:,None])[0].detach().cpu().numpy()
        anchors=(official[faces[face_idx]]*bary[:,:,None]).sum(1)
        start=time.perf_counter(); raw_t,trace=robust_translation(points[0],anchors); t_ms=(time.perf_counter()-start)*1000
        fallback=bool(np.linalg.norm(raw_t)>TOTAL_BOUND); applied=np.zeros(3) if fallback else raw_t; corrected=official+applied
        off_b=world_to_local(local_to_world(official,cal[0][3],cal[0][4]),cal[1][3],cal[1][4])
        cor_b=world_to_local(local_to_world(corrected,cal[0][3],cal[0][4]),cal[1][3],cal[1][4])
        metrics={"A_official":metric(points[0],official,faces,point_to_triangle_distances,sid+"ao"),"A_txyz":metric(points[0],corrected,faces,point_to_triangle_distances,sid+"at"),"B_official":metric(points[1],off_b,faces,point_to_triangle_distances,sid+"bo"),"B_txyz":metric(points[1],cor_b,faces,point_to_triangle_distances,sid+"bt")}
        ia=a.out/"visualizations"/"inference"/sid; ev=a.out/"visualizations"/"evaluation"/sid; meshdir=a.out/"meshes"/sid
        oa=render(rgbs[0],official,faces,cal[0][0],cal[0][1]); ta=render(rgbs[0],corrected,faces,cal[0][0],cal[0][1])
        ob=render(rgbs[1],off_b,faces,cal[1][0],cal[1][1]); tb=render(rgbs[1],cor_b,faces,cal[1][0],cal[1][1])
        for path,img in [(ia/"camA_rgb_original.png",rgbs[0]),(ia/"camA_official_overlay.png",oa),(ia/"camA_txyz_overlay.png",ta),(ia/"camA_triptych.png",triptych([rgbs[0],oa,ta],["Camera A RGB","Official SAM3D","Camera-A Txyz"])),(ev/"camB_rgb_original.png",rgbs[1]),(ev/"camB_official_overlay.png",ob),(ev/"camB_txyz_overlay.png",tb),(ev/"camB_triptych.png",triptych([rgbs[1],ob,tb],["Held-out Camera B","Official from A","Txyz from A"]))]: save(path,img)
        meshdir.mkdir(parents=True,exist_ok=True); write_obj(meshdir/"official_camA.obj",official,faces); write_obj(meshdir/"txyz_camA.obj",corrected,faces); write_obj(meshdir/"official_camB.obj",off_b,faces); write_obj(meshdir/"txyz_camB.obj",cor_b,faces)
        outcome="improved" if metrics["B_txyz"]["median_mm"]+1<metrics["B_official"]["median_mm"] else ("degraded" if metrics["B_txyz"]["median_mm"]>metrics["B_official"]["median_mm"]+1 else "unchanged")
        row={"id":sid,"sequence":seq_name,"frame":frame_name,"camera_A":0,"camera_B":1,"bbox_A":bbox[0].tolist(),"Txyz_m":raw_t.tolist(),"applied_Txyz_m":applied.tolist(),"fallback":fallback,"trace":trace,"metrics":metrics,"heldout_outcome":outcome,"runtime_sam_ms":sam_ms,"runtime_txyz_ms":t_ms,"runtime_total_ms":sam_ms+t_ms}
        (ia/"result.json").write_text(json.dumps(row,indent=2)+"\n"); (ev/"result.json").write_text(json.dumps(row,indent=2)+"\n"); results.append(row); print(json.dumps({"id":sid,"outcome":outcome,"B0":metrics["B_official"]["median_mm"],"B1":metrics["B_txyz"]["median_mm"]}),flush=True)
    report=a.out/"report"; report.mkdir(exist_ok=True); (report/"per_frame_metrics.json").write_text(json.dumps(results,indent=2)+"\n")
    flat=[]
    for r in results:
        q={"id":r["id"],"heldout_outcome":r["heldout_outcome"],"tx_m":r["Txyz_m"][0],"ty_m":r["Txyz_m"][1],"tz_m":r["Txyz_m"][2],"runtime_sam_ms":r["runtime_sam_ms"],"runtime_txyz_ms":r["runtime_txyz_ms"]}
        for side in ["A","B"]:
            for kind in ["official","txyz"]:
                for key,val in r["metrics"][f"{side}_{kind}"].items(): q[f"{side}_{kind}_{key}"]=val
        flat.append(q)
    with open(report/"per_frame_metrics.csv","w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    (report/"run_runtime.json").write_text(json.dumps({"peak_gpu_memory_mb":torch.cuda.max_memory_allocated()/2**20,"frames":len(results)},indent=2)+"\n")


if __name__ == "__main__": main()
