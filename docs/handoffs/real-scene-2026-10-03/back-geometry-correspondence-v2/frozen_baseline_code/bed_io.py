"""Shared I/O for the L1 fit: depth cloud, mattress plane, pressure map (PressurePose prone).

World frame (PressurePose): +z points AWAY from the overhead camera (camera at z=-1.66 m),
so larger world z = deeper into the mattress. Pressure mat: 64x27 cells, 28.6 mm pitch.
The pressure image is stored flipped along its first axis relative to world x
(checked: 0.92-0.96 of loaded taxels fall inside the depth silhouette with the flip vs
0.75-0.85 without, S107/S104/S165).
"""
from __future__ import annotations
import json, pickle
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
RAW = Path("/sessions/wizardly-focused-wright/mnt/outputs/raw_pp")
CALIB = ROOT / "preview/geometry_qa/pressurepose_k0_calibration_qa.json"
PITCH = 0.0286
NX, NY = 64, 27
SUBJECTS = ["S103", "S104", "S107", "S114", "S118", "S121", "S130", "S134", "S140", "S141",
            "S145", "S151", "S163", "S165", "S170", "S179", "S184", "S187", "S188", "S196"]


def calib():
    return {r["subject"]: r for r in json.loads(CALIB.read_text())["rows"]}


def prone_index(pose_types):
    labs = [x.decode("latin1") if isinstance(x, bytes) else x for x in pose_types]
    return labs.index("p_sel_prn")


def load_subject(s, cal):
    with (RAW / s / "p_select.p").open("rb") as fh:
        d = pickle.load(fh, encoding="latin1")
    i = prone_index(d["pose_type"])
    R = np.asarray(cal[s]["R_world_to_camera"], float)
    C = np.asarray(cal[s]["camera_center_m"], float)
    K = np.asarray(cal[s]["K"], float)
    pc_w = np.asarray(d["pc"][i], float)
    cam = (pc_w - C) @ R.T
    dep = np.rot90(np.asarray(d["depth"][i])).astype(float) / 1000.0
    pmat = np.asarray(d["images"][i], float)[::-1]          # flip to world-x order
    return dict(cam=cam, pc_w=pc_w, R=R, C=C, K=K, depth=dep, pmat=pmat)


def to_world(cam, R, C):
    return cam @ R + C


def bed_plane(sub):
    """Fit z = a x + b y + c to exposed mattress pixels (>4 cm from the person cloud)."""
    K, R, C, dep = sub["K"], sub["R"], sub["C"], sub["depth"]
    vv, uu = np.nonzero(dep > 0); z = dep[vv, uu]
    cam = np.c_[(uu - K[0, 2]) * z / K[0, 0], (vv - K[1, 2]) * z / K[1, 1], z]
    w = to_world(cam, R, C)
    dist, _ = cKDTree(sub["pc_w"][:, :2]).query(w[:, :2])
    m = ((w[:, 0] > .05) & (w[:, 0] < NX * PITCH - .05) & (w[:, 1] > .03) & (w[:, 1] < NY * PITCH - .03)
         & (dist > .04) & (np.abs(w[:, 2] - .03) < .15))
    A = np.c_[w[m, 0], w[m, 1], np.ones(m.sum())]; zz = w[m, 2]
    for _ in range(5):
        c, *_ = np.linalg.lstsq(A, zz, rcond=None)
        r = zz - A @ c; k = np.abs(r) < 2.5 * np.median(np.abs(r)) + 1e-4
        A, zz = A[k], zz[k]
    return c, float(np.median(np.abs(r)))


def height_above_bed(Pw, plane):
    """Positive = above the undeformed mattress surface (toward camera), metres."""
    return (plane[0] * Pw[:, 0] + plane[1] * Pw[:, 1] + plane[2]) - Pw[:, 2]


def mesh_contact_map(Vw, plane, tol=0.01):
    """Mat cells containing mesh vertices at or below (bed surface + tol)."""
    h = height_above_bed(Vw, plane)
    m = h <= tol
    gx = np.floor(Vw[m, 0] / PITCH).astype(int); gy = np.floor(Vw[m, 1] / PITCH).astype(int)
    ok = (gx >= 0) & (gx < NX) & (gy >= 0) & (gy < NY)
    out = np.zeros((NX, NY), bool); out[gx[ok], gy[ok]] = True
    return out


def contact_scores(Vw, plane, pmat, tol=0.01):
    cm = mesh_contact_map(Vw, plane, tol); pm = pmat > 0
    inter = (cm & pm).sum(); uni = (cm | pm).sum()
    return dict(iou=float(inter / max(uni, 1)), recall=float(inter / max(pm.sum(), 1)),
                precision=float(inter / max(cm.sum(), 1)))
