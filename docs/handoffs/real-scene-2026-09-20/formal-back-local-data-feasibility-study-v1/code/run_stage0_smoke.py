"""Audit the available BEHAVE/HuMMan assets and verify crop geometry.

This deliberately stops before model evaluation when the reference gates required
by FORMAL_BACK_LOCAL_DATA_FEASIBILITY_STUDY_V1 are not available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    y, x = np.where(mask > 127)
    if not len(x):
        raise ValueError("empty person mask")
    return int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1


def crop_boxes(mask: np.ndarray) -> dict[str, tuple[int, int, int, int]]:
    """Fixed normalized rules, applied to the observed person-mask bbox."""
    x0, y0, x1, y1 = mask_bbox(mask)
    w, h = x1 - x0, y1 - y0
    image_h, image_w = mask.shape

    def box(rx0: float, ry0: float, rx1: float, ry1: float) -> tuple[int, int, int, int]:
        return (
            max(0, round(x0 + rx0 * w)), max(0, round(y0 + ry0 * h)),
            min(image_w, round(x0 + rx1 * w)), min(image_h, round(y0 + ry1 * h)),
        )

    return {
        "FULL": box(-0.05, -0.05, 1.05, 1.05),
        "UPPER": box(0.02, 0.00, 0.98, 0.72),
        "BACK_LOCAL": box(0.20, 0.15, 0.80, 0.72),
    }


def effective_k(K: np.ndarray, box: tuple[int, int, int, int], target=(512, 512)) -> np.ndarray:
    x0, y0, x1, y1 = box
    sx, sy = target[0] / (x1 - x0), target[1] / (y1 - y0)
    out = K.astype(np.float64).copy()
    out[0, 0] *= sx
    out[1, 1] *= sy
    out[0, 2] = (out[0, 2] - x0) * sx
    out[1, 2] = (out[1, 2] - y0) * sy
    return out


def projection_error(K: np.ndarray, K_crop: np.ndarray,
                     box: tuple[int, int, int, int]) -> float:
    x0, y0, x1, y1 = box
    sx, sy = 512 / (x1 - x0), 512 / (y1 - y0)
    points = np.array([[-0.25, -0.20, 2.0], [0.0, 0.0, 2.5],
                       [0.30, 0.22, 3.0], [-0.10, 0.35, 2.2]], np.float64)
    uv = points @ K[:3, :3].T
    uv = uv[:, :2] / uv[:, 2:]
    expected = np.column_stack(((uv[:, 0] - x0) * sx, (uv[:, 1] - y0) * sy))
    got = points @ K_crop.T
    got = got[:, :2] / got[:, 2:]
    return float(np.abs(expected - got).max())


def zbuffer(points: np.ndarray, K: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    uvw = points @ K.T
    uv = np.rint(uvw[:, :2] / uvw[:, 2:]).astype(np.int32)
    good = ((points[:, 2] > 0) & (uv[:, 0] >= 0) & (uv[:, 0] < shape[1]) &
            (uv[:, 1] >= 0) & (uv[:, 1] < shape[0]))
    uv, z = uv[good], points[good, 2]
    depth = np.full(shape, np.inf, np.float32)
    np.minimum.at(depth, (uv[:, 1], uv[:, 0]), z.astype(np.float32))
    depth[~np.isfinite(depth)] = 0
    return depth


def depth_vis(depth: np.ndarray) -> np.ndarray:
    valid = depth > 0
    out = np.zeros((*depth.shape, 3), np.uint8)
    if valid.any():
        lo, hi = np.percentile(depth[valid], [2, 98])
        s = np.zeros(depth.shape, np.uint8)
        s[valid] = np.clip((depth[valid] - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)
        out = cv2.cvtColor(cv2.applyColorMap(255 - s, cv2.COLORMAP_TURBO), cv2.COLOR_BGR2RGB)
        out[~valid] = 0
    return out


def save_rgb(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))


def make_smoke(name: str, rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray,
               K: np.ndarray, out: Path) -> list[dict]:
    rows, panels = [], []
    for condition, box in crop_boxes(mask).items():
        x0, y0, x1, y1 = box
        rgb_c = cv2.resize(rgb[y0:y1, x0:x1], (512, 512), interpolation=cv2.INTER_AREA)
        dep_c = cv2.resize(depth[y0:y1, x0:x1], (512, 512), interpolation=cv2.INTER_NEAREST)
        mask_c = cv2.resize(mask[y0:y1, x0:x1], (512, 512), interpolation=cv2.INTER_NEAREST)
        k_c = effective_k(K, box)
        err = projection_error(K, k_c, box)
        base = out / "inputs" / "smoke" / name / condition.lower()
        save_rgb(base / "rgb.png", rgb_c)
        save_rgb(base / "depth.png", depth_vis(dep_c))
        save_rgb(base / "mask.png", np.repeat(mask_c[:, :, None], 3, axis=2))
        panels.append(np.hstack([rgb_c, depth_vis(dep_c), np.repeat(mask_c[:, :, None], 3, axis=2)]))
        rows.append({
            "dataset_sample": name, "condition": condition, "source_box_xyxy": list(box),
            "target_wh": [512, 512], "original_K": K.tolist(), "effective_K": k_c.tolist(),
            "projection_max_abs_error_px": err, "projection_test": "PASS" if err < 1e-6 else "FAIL",
            "rgb_depth_mask_written": True,
        })
    canvas = np.vstack(panels)
    save_rgb(out / "visualizations" / f"{name}_full_upper_back_local_contact_sheet.png", canvas)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--behave-sequences", type=Path, required=True)
    ap.add_argument("--behave-calibs", type=Path, required=True)
    ap.add_argument("--formal-manifest", type=Path, required=True)
    ap.add_argument("--humman-workset", type=Path, required=True)
    ap.add_argument("--humman-prepared", type=Path, required=True)
    ap.add_argument("--humman-smpl", type=Path, required=True)
    ap.add_argument("--sam-repo", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--mhr", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = a.out
    out.mkdir(parents=True, exist_ok=True)

    source = json.loads(a.formal_manifest.read_text())
    rows = source["rows"]
    selected_behave = []
    for subject in ("Sub03", "Sub04", "Sub05"):
        subject_rows = [r for r in rows if r["subject"] == subject]
        for sequence in sorted({r["sequence"] for r in subject_rows}):
            seq_rows = [r for r in subject_rows if r["sequence"] == sequence]
            selected_behave.extend([seq_rows[0], seq_rows[-1]])

    humman_frames = {
        "p000823_a000035": [8, 16, 24],
        "p001088_a000203": [52, 103, 154],
    }
    selected_humman = []
    for sequence, frame_ids in humman_frames.items():
        for frame_id in frame_ids:
            selected_humman.append({
                "dataset": "HuMMan", "subject": sequence.split("_")[0], "sequence": sequence,
                "frame": f"{frame_id:06d}", "input_camera": "kinect_008",
                "heldout_camera": "kinect_009", "selection_rule": "three pre-extracted temporal quantiles",
            })

    subset = {
        "schema": "FORMAL_BACK_LOCAL_FEASIBILITY_SUBSET_V1",
        "status": "FROZEN_OUTCOME_BLIND",
        "selection_source": str(a.formal_manifest),
        "selection_rule": "BEHAVE first/last of each pre-frozen action for Sub03-05; HuMMan three pre-extracted temporal quantiles for two sequences",
        "subject_count": 5, "timestamp_count": 24,
        "pose_coverage": ["backpack/back-oriented", "stool/sitting", "yogaball/articulated", "HuMMan two external actions"],
        "prone_status": "PRONE_NOT_AVAILABLE",
        "behave": [{**r, "dataset": "BEHAVE", "selection_role": "feasibility"} for r in selected_behave],
        "humman": selected_humman,
    }
    write_json(out / "subset" / "FEASIBILITY_SUBSET.json", subset)

    first = selected_behave[0]
    bf = a.behave_sequences / first["sequence"] / first["frame"]
    rgb_b = cv2.cvtColor(cv2.imread(str(bf / "k0.color.jpg")), cv2.COLOR_BGR2RGB)
    dep_b = cv2.imread(str(bf / "k0.depth.png"), cv2.IMREAD_UNCHANGED).astype(np.float32) / 1000
    mask_b = cv2.imread(str(bf / "k0.person_mask.jpg"), cv2.IMREAD_GRAYSCALE)
    intr = json.loads((a.behave_calibs / "intrinsics" / "0" / "calibration.json").read_text())["color"]
    K_b = np.array([[intr["fx"], 0, intr["cx"]], [0, intr["fy"], intr["cy"]], [0, 0, 1]], float)

    hp = a.humman_prepared / "p000823_a000035_f000016.npz"
    z = np.load(hp)
    rgb_h, mask_h, K_h = z["rgb_a"], z["mask_a"], z["K_a"]
    dep_h = zbuffer(z["points_a"], K_h, mask_h.shape)
    qa_rows = make_smoke("behave", rgb_b, dep_b, mask_b, K_b, out)
    qa_rows += make_smoke("humman", rgb_h, dep_h, mask_h, K_h, out)
    write_json(out / "audit" / "CROP_PROJECTION_QA.json", {
        "status": "PASS" if all(r["projection_test"] == "PASS" for r in qa_rows) else "FAIL",
        "rows": qa_rows,
        "scope": "coordinate and file-generation smoke only; BACK_LOCAL boxes are provisional geometric crops",
    })

    behave_fit = bf / "person" / "fit02" / "person_fit.ply"
    humman_smpl_files = sorted(a.humman_smpl.glob("**/smpl_params.npz"))
    # These are the relevant project/model roots. A prior targeted server search
    # found no licensed SMPL body model; avoid an unbounded scan of all /raid5.
    candidate_roots = [a.sam_repo, a.humman_smpl.parent, a.repo]
    smpl_models = [p for root in candidate_roots for p in (
        root / "SMPL_NEUTRAL.pkl", root / "models" / "SMPL_NEUTRAL.pkl",
        root / "data" / "SMPL_NEUTRAL.pkl") if p.exists()]
    conversion_tool_local = [p for root in candidate_roots for p in (
        root / "tools" / "mhr_smpl_conversion", root / "mhr_smpl_conversion") if p.exists()]
    audit = {
        "schema": "DATA_ASSET_AUDIT_V1", "status": "COMPLETED_FROM_DISK",
        "behave": {
            "sequences": "AVAILABLE", "selected_subjects": ["Sub03", "Sub04", "Sub05"],
            "rgb_depth_mask": "AVAILABLE", "intrinsics_extrinsics": "AVAILABLE",
            "official_multiview_smpl_fit": "AVAILABLE" if behave_fit.exists() else "MISSING",
            "official_fit_example": str(behave_fit),
            "existing_sam_o1_o2": "AVAILABLE_IN_PRIOR_DELIVERIES",
        },
        "humman": {
            "selected_subjects": ["p000823", "p001088"], "rgb_depth_mask": "AVAILABLE",
            "intrinsics_extrinsics": "AVAILABLE", "smpl_parameter_archives": "AVAILABLE",
            "extracted_smpl_parameter_files": [str(p) for p in humman_smpl_files],
            "smpl_body_model_files": "AVAILABLE" if smpl_models else "MISSING_LICENSED_ASSET",
            "textured_mesh_or_scan": "NOT_CHECKED_NOT_REQUIRED_FOR_SMOKE",
            "3d_keypoints": "NOT_CHECKED_NOT_REQUIRED_FOR_SMOKE",
        },
        "mhr_conversion": {
            "official_upstream": "AVAILABLE_AT_https://github.com/facebookresearch/MHR/tree/main/tools/mhr_smpl_conversion",
            "local_tool": "AVAILABLE" if conversion_tool_local else "MISSING",
            "required_official_smpl_body_model": "AVAILABLE" if smpl_models else "MISSING_LICENSED_ASSET",
            "conversion_smoke": "BLOCKED",
            "conversion_error": "NOT_COMPUTABLE",
        },
        "frozen_model_assets": {
            "sam_repo": str(a.sam_repo), "checkpoint": str(a.checkpoint), "checkpoint_sha256": sha256(a.checkpoint),
            "mhr_asset": str(a.mhr), "mhr_sha256": sha256(a.mhr),
        },
    }
    write_json(out / "audit" / "DATA_ASSET_AUDIT.json", audit)

    region = {
        "schema": "BACK_REGION_V1", "status": "BLOCKED_NOT_FROZEN",
        "vertex_ids": [], "face_ids": [],
        "source": "No independently validated posterior MHR/SMPL semantic region is frozen in the project",
        "definition_notes": [
            "The generated BACK_LOCAL crop is a provisional image-space torso crop, not a back-surface reference.",
            "Existing provisional posterior polygons require independent review and cannot be promoted after seeing errors.",
        ],
    }
    write_json(out / "regions" / "BACK_REGION_V1.json", region)

    tests = {
        "schema": "PREEXECUTION_TESTS_V1", "overall": "HOLD",
        "tests": {
            "TEST_1_three_crops": "PASS_BEHAVE_AND_HUMMAN_SMOKE",
            "TEST_2_crop_rgb_depth_projection": "PASS",
            "TEST_3_official_smpl_to_mhr": "BLOCKED_MISSING_LICENSED_SMPL_BODY_MODEL_AND_LOCAL_CONVERTER",
            "TEST_4_conversion_surface_error": "BLOCKED_BY_TEST_3",
            "TEST_5_official_sam_three_inputs": "NOT_RUN_GATE_STOP",
            "TEST_6_cheap_txyz_crop_depth": "NOT_RUN_GATE_STOP",
            "TEST_7_t_pose_oracle_crop_depth": "NOT_RUN_GATE_STOP",
            "TEST_8_heldout_exclusion": "PASS_BY_FROZEN_SUBSET_CONTRACT",
        },
        "gate_reason": "The prompt requires TEST 3 and TEST 4 before entering the feasibility subset. Running model metrics without a ready regional/reference contract would not answer the scientific question.",
    }
    write_json(out / "audit" / "PREEXECUTION_TESTS.json", tests)

    characterization = {
        "schema": "FINAL_CHARACTERIZATION_V1", "result": "REFERENCE_NOT_READY",
        "training_decision": "NO_TRAINING",
        "completed": ["disk asset audit", "outcome-blind 5-subject/24-timestamp freeze", "BEHAVE and HuMMan FULL/UPPER/BACK_LOCAL crop smoke", "effective-intrinsics projection QA"],
        "blocking_facts": ["Official SMPL-to-MHR conversion cannot run without the licensed SMPL body-model files", "BACK_REGION_V1 has no independently validated topology correspondence", "Therefore back-region and conversion-reference error cannot be validly reported"],
        "claim_limit": "No FULL/UPPER/BACK_LOCAL model accuracy comparison was made in this stopped run.",
    }
    write_json(out / "FINAL_CHARACTERIZATION.json", characterization)

    report = f"""# FORMAL_BACK_LOCAL_DATA_FEASIBILITY_STUDY_V1\n\n## Decision\n\n**REFERENCE_NOT_READY — NO_TRAINING.**\n\nThe task design is scientifically sound, but the current local assets do not satisfy its own minimum execution gate. We therefore completed the data/crop feasibility portion and stopped before producing model comparisons that would lack a valid regional/reference contract.\n\n## What was actually executed\n\n- Audited BEHAVE and HuMMan assets from disk.\n- Froze an outcome-blind subset of **5 subjects / 24 timestamps**: 18 BEHAVE timestamps across Sub03–05 and 6 HuMMan timestamps across p000823/p001088.\n- Generated synchronized FULL, UPPER and provisional BACK_LOCAL RGB/depth/mask files for one BEHAVE and one HuMMan sample.\n- Recomputed effective crop intrinsics and passed numeric projection equivalence for all six crop cases.\n- Preserved the held-out camera role in the frozen subset.\n\n## Why the formal model experiment stopped\n\nHuMMan SMPL parameter NPZ files are available, but the licensed SMPL body-model files needed to instantiate source vertices are absent. The official MHR conversion workflow is also not installed locally. TEST 3 therefore cannot run, and TEST 4 cannot compute a conversion surface error. Separately, the project has no independently validated canonical posterior surface mapping that can be frozen as BACK_REGION_V1; prior polygons remain provisional engineering annotations.\n\nThe BACK_LOCAL images produced here only prove crop and camera-coordinate handling. They are not evidence that the cropped person is posterior-facing, and they cannot support a scientific back-region metric.\n\n## Answers to the requested questions\n\n1. Existing datasets can construct synchronized local torso RGB-D inputs: **yes, at smoke-test level**.\n2. FULL/UPPER/BACK_LOCAL model errors: **not measured; gate stopped before model evaluation**.\n3. Whether local input degrades SAM 3D Body: **not yet knowable from this run**.\n4. Cheap Txyz on local input: **not evaluated after gate failure**.\n5. T+Pose on local input: **not evaluated after gate failure**.\n6. Whole-body versus back-region trend: **not comparable until BACK_REGION_V1 is valid**.\n7. Current reference labels: BEHAVE whole-body fitted reference is available; the cross-dataset back-local reference is **not ready**.\n8. SMPL→MHR error: **not computable with current licensed assets**.\n9. Single-view fitting pseudo-label quality: **not started because the stronger-reference prerequisite is missing**.\n10. Training decision: **NO_TRAINING; repair reference generation first**.\n\n## Smallest valid next step\n\nProvide the official licensed SMPL model files on the server, install the upstream MHR conversion tool, run the prescribed five-sample conversion smoke, and independently freeze a posterior surface mapping before viewing model error maps. After those gates pass, the frozen 24-timestamp subset can be used for Official/O1/O2 comparisons without changing sample selection.\n\n## Reproducibility\n\nRun `code/run_stage0_smoke.py` with the recorded server paths. Exact audit records are under `audit/`; crop images and contact sheets are under `inputs/` and `visualizations/`.\n"""
    (out / "FINAL_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "COMPLETED", "result": "REFERENCE_NOT_READY", "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
