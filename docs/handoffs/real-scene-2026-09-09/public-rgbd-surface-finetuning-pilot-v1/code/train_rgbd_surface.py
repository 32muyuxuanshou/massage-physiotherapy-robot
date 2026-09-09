"""Governed RGB-D surface fine-tuning pilot for SAM 3D Body.

The only trainable modules are the Official model's pose and camera projection
heads. Camera A supplies the new surface supervision. Camera B is opened only by
validation after all optimizer work for an epoch. SEALED observations are never
valid inputs to this program.

The checked-in protocol and workset are frozen for the one-epoch engineering
smoke. Formal training still requires a separately reviewed protocol state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

import numpy as np
import torch
import torch.nn.functional as F

from surface_metrics import camera_to_world, point_to_triangle, rendered_depth, world_to_camera


ALLOWED_TRAINABLE = ("head_pose.proj", "head_camera.proj")
RUNNABLE_PROTOCOL_STATES = ("FROZEN_FOR_1_EPOCH_SMOKE", "FROZEN_FOR_FORMAL_PILOT")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_seed(seed: int, *parts: object) -> int:
    text = ":".join((str(seed), *(str(part) for part in parts)))
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "little")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_workset(manifest: dict, manifest_path: Path, verify_files: bool) -> tuple[list, list]:
    if manifest.get("final_split_frozen") is not True:
        raise RuntimeError("final subject split is not frozen")
    if manifest.get("workset_qa_passed") is not True:
        raise RuntimeError("RGB-D workset QA has not passed")
    samples = manifest.get("samples", [])
    if not samples:
        raise RuntimeError("workset contains no samples")
    train, val = [], []
    sealed_subjects = {str(value) for value in manifest.get("sealed_subject_ids", [])}
    subject_splits: dict[str, str] = {}
    ids: set[str] = set()
    for row in samples:
        split = str(row.get("split", "")).upper()
        if split not in ("TRAIN", "VAL"):
            raise RuntimeError(f"forbidden sample split {split!r}; only TRAIN/VAL may be materialized")
        sample_id, subject = str(row["id"]), str(row["subject_id"])
        if subject in sealed_subjects:
            raise RuntimeError(f"refusing SEALED subject: {subject}")
        if sample_id in ids:
            raise RuntimeError(f"duplicate sample id: {sample_id}")
        ids.add(sample_id)
        prior = subject_splits.setdefault(subject, split)
        if prior != split:
            raise RuntimeError(f"subject leakage: {subject} occurs in {prior} and {split}")
        path = Path(row["observation_npz"])
        if not path.is_absolute():
            path = (manifest_path.parent / path).resolve()
        # This guard happens before np.load. It prevents a mislabeled sealed path
        # from being opened even if its metadata says TRAIN.
        forbidden_component = any(part.lower() == "sealed" or part.lower().startswith("sealed_")
                                  for part in path.parts)
        if forbidden_component:
            raise RuntimeError(f"refusing SEALED path component: {path}")
        item = dict(row, split=split, resolved_path=path)
        if verify_files:
            if not path.is_file():
                raise FileNotFoundError(path)
            expected = row.get("observation_sha256")
            if not expected or sha256_file(path) != expected:
                raise RuntimeError(f"observation checksum missing or mismatched: {sample_id}")
        (train if split == "TRAIN" else val).append(item)
    if not train or not val:
        raise RuntimeError("workset must contain disjoint TRAIN and VAL subjects")
    return train, val


def validate_observation(path: Path, split: str) -> None:
    with np.load(path) as obs:
        required = {"rgb_a", "bbox_a", "K_a", "points_a"}
        if split == "VAL":
            required |= {"rgb_b", "K_b", "points_b", "R_a", "T_a", "R_b", "T_b"}
        missing = required.difference(obs.files)
        if missing:
            raise RuntimeError(f"{path.name} lacks keys: {sorted(missing)}")
        if obs["points_a"].ndim != 2 or obs["points_a"].shape[1] != 3:
            raise RuntimeError(f"bad Camera-A point shape in {path.name}")


def subsample(points: np.ndarray, maximum: int, seed: int) -> np.ndarray:
    if len(points) <= maximum:
        return points
    return points[np.random.default_rng(seed).choice(len(points), maximum, replace=False)]


def forward_observation(model, estimator, prepare_batch, recursive_to, path: Path) -> tuple[dict, dict]:
    with np.load(path) as raw:
        # Copy only Camera A arrays. Camera B remains unopened by training calls.
        obs_a = {key: raw[key].copy() for key in ("rgb_a", "bbox_a", "K_a", "points_a")}
    batch = prepare_batch(obs_a["rgb_a"], estimator.transform,
                          obs_a["bbox_a"][None].astype(np.float32), None, None)
    batch = recursive_to(batch, "cuda")
    batch["cam_int"] = torch.as_tensor(obs_a["K_a"][None], device="cuda").to(batch["img"])
    model._initialize_batch(batch)
    return model.forward_step(batch, decoder_type="body")["mhr"], obs_a


def cache_official_teacher(model, estimator, prepare_batch, recursive_to, rows: list) -> dict:
    teacher = {}
    with torch.no_grad():
        for row in rows:
            output, _ = forward_observation(model, estimator, prepare_batch, recursive_to,
                                            row["resolved_path"])
            teacher[row["id"]] = {
                "keypoints_2d": output["pred_keypoints_2d"].detach().cpu(),
                "keypoints_3d": output["pred_keypoints_3d"].detach().cpu(),
                "pred_cam_t": output["pred_cam_t"].detach().cpu(),
                "global_rot": output["global_rot"].detach().cpu(),
                "body_pose": output["body_pose"].detach().cpu(),
            }
    return teacher


def robust_surface_loss(vertices_camera: torch.Tensor, faces: torch.Tensor,
                        observed: np.ndarray, cfg: dict, seed: int) -> torch.Tensor:
    rng = np.random.default_rng(seed)
    point_ids = rng.choice(len(observed), min(len(observed), cfg["observed_samples"]), replace=False)
    face_ids = rng.choice(len(faces), min(len(faces), cfg["triangle_samples"]), replace=False)
    bary = rng.dirichlet(np.ones(3), len(face_ids)).astype(np.float32)
    points = torch.as_tensor(observed[point_ids], device=vertices_camera.device,
                             dtype=vertices_camera.dtype)
    face_ids_t = torch.as_tensor(face_ids, device=vertices_camera.device, dtype=torch.long)
    bary_t = torch.as_tensor(bary, device=vertices_camera.device, dtype=vertices_camera.dtype)
    surface = (vertices_camera[:, faces[face_ids_t]] * bary_t[None, :, :, None]).sum(2)
    distance = torch.cdist(points[None], surface).amin(-1)[0]
    delta = cfg["huber_delta_m"]
    return torch.where(distance < delta, 0.5 * distance.square() / delta,
                       distance - 0.5 * delta).mean()


def stability_loss(output: dict, target: dict, pelvis_idx: torch.Tensor,
                   image_hw: tuple[int, int]) -> tuple[torch.Tensor, torch.Tensor]:
    p2, p3 = output["pred_keypoints_2d"], output["pred_keypoints_3d"]
    t2 = target["keypoints_2d"].to(p2)
    t3 = target["keypoints_3d"].to(p3)
    size = p2.new_tensor([image_hw[1], image_hw[0]])
    loss2 = F.smooth_l1_loss(p2 / size, t2 / size)
    p3rel = p3 - p3[:, pelvis_idx].mean(1, keepdim=True)
    t3rel = t3 - t3[:, pelvis_idx].mean(1, keepdim=True)
    return loss2, F.smooth_l1_loss(p3rel, t3rel)


def head_initialization_loss(heads: dict, initial: dict) -> torch.Tensor:
    terms = []
    for head_name, head in heads.items():
        for name, parameter in head.named_parameters():
            terms.append(F.mse_loss(parameter, initial[f"{head_name}.{name}"]))
    return torch.stack(terms).mean()


def aggregate_subject_macro(rows: list) -> dict:
    by_subject: dict[str, list] = {}
    for row in rows:
        by_subject.setdefault(row["subject_id"], []).append(row)
    subject_rows = []
    for subject, values in sorted(by_subject.items()):
        subject_rows.append({
            "subject_id": subject,
            "point_to_triangle_frame_median_mm": float(np.median(
                [v["point_to_triangle"]["median_mm"] for v in values])),
            "point_to_triangle_frame_p90_mm": float(np.median(
                [v["point_to_triangle"]["p90_mm"] for v in values])),
            "point_to_triangle_frame_p95_mm": float(np.median(
                [v["point_to_triangle"]["p95_mm"] for v in values])),
            "rendered_depth_frame_median_mm": float(np.median(
                [v["rendered_depth"]["median_mm"] for v in values])),
            "rendered_depth_frame_p90_mm": float(np.median(
                [v["rendered_depth"]["p90_mm"] for v in values])),
            "rendered_depth_frame_p95_mm": float(np.median(
                [v["rendered_depth"]["p95_mm"] for v in values])),
            "rendered_depth_coverage": float(np.median(
                [v["rendered_depth"]["mesh_coverage_of_observed_points"] for v in values])),
        })
    return {
        "subject_count": len(subject_rows),
        "point_to_triangle_mean_of_subject_frame_medians_mm": float(np.mean(
            [v["point_to_triangle_frame_median_mm"] for v in subject_rows])),
        "point_to_triangle_median_of_subject_frame_medians_mm": float(np.median(
            [v["point_to_triangle_frame_median_mm"] for v in subject_rows])),
        "point_to_triangle_p90_of_subject_frame_medians_mm": float(np.percentile(
            [v["point_to_triangle_frame_median_mm"] for v in subject_rows], 90)),
        "point_to_triangle_p95_of_subject_frame_medians_mm": float(np.percentile(
            [v["point_to_triangle_frame_median_mm"] for v in subject_rows], 95)),
        "point_to_triangle_mean_of_subject_frame_p90_mm": float(np.mean(
            [v["point_to_triangle_frame_p90_mm"] for v in subject_rows])),
        "point_to_triangle_mean_of_subject_frame_p95_mm": float(np.mean(
            [v["point_to_triangle_frame_p95_mm"] for v in subject_rows])),
        "rendered_depth_mean_of_subject_frame_medians_mm": float(np.mean(
            [v["rendered_depth_frame_median_mm"] for v in subject_rows])),
        "rendered_depth_mean_of_subject_frame_p90_mm": float(np.mean(
            [v["rendered_depth_frame_p90_mm"] for v in subject_rows])),
        "rendered_depth_mean_of_subject_frame_p95_mm": float(np.mean(
            [v["rendered_depth_frame_p95_mm"] for v in subject_rows])),
        "rendered_depth_median_coverage": float(np.median(
            [v["rendered_depth_coverage"] for v in subject_rows])),
        "subjects": subject_rows,
    }


def evaluate(model, estimator, prepare_batch, recursive_to, rows: list, faces_np: np.ndarray,
             cfg: dict, seed: int, official_reference: dict) -> dict:
    details = []
    model.eval()
    with torch.no_grad():
        for index, row in enumerate(rows):
            output, _ = forward_observation(model, estimator, prepare_batch, recursive_to,
                                            row["resolved_path"])
            vertices_a = (output["pred_vertices"] + output["pred_cam_t"][:, None, :])[
                0].float().cpu().numpy()
            # Camera B is first opened here, never during teacher caching/training.
            with np.load(row["resolved_path"]) as obs:
                points_b = subsample(obs["points_b"].astype(np.float64),
                                     cfg["maximum_eval_points"], seed + index)
                vertices_b = world_to_camera(camera_to_world(vertices_a, obs["R_a"], obs["T_a"]),
                                             obs["R_b"], obs["T_b"])
                triangle = point_to_triangle(points_b, vertices_b, faces_np)
                depth = rendered_depth(points_b, vertices_b, faces_np, obs["K_b"],
                                       obs["rgb_b"].shape[0], obs["rgb_b"].shape[1])
            if triangle.get("status") == "NO_VALID_OVERLAP" or depth.get("status") == "NO_VALID_OVERLAP":
                raise RuntimeError(f"no valid held-out surface overlap for {row['id']}")
            reference = official_reference[row["id"]]
            sanity = {
                "camera_translation_delta_m": float(torch.linalg.vector_norm(
                    output["pred_cam_t"].detach().cpu() - reference["pred_cam_t"])),
                "global_rotation_rms_parameter": float(torch.sqrt(torch.mean(
                    torch.atan2(
                        torch.sin(output["global_rot"].detach().cpu() - reference["global_rot"]),
                        torch.cos(output["global_rot"].detach().cpu() - reference["global_rot"]),
                    ) ** 2))),
                "body_pose_rms_parameter": float(torch.sqrt(torch.mean(
                    (output["body_pose"].detach().cpu()
                     - reference["body_pose"]) ** 2))),
            }
            details.append({"id": row["id"], "subject_id": row["subject_id"],
                            "point_to_triangle": triangle, "rendered_depth": depth,
                            "parameter_delta_from_official": sanity})
    limits = cfg["parameter_sanity_limits"]
    maxima = {key: max(row["parameter_delta_from_official"][key] for row in details)
              for key in limits}
    parameter_sanity = {"limits": limits, "maximum_over_val_observations": maxima,
                        "within_all_limits": all(maxima[key] <= limits[key] for key in limits)}
    return {"aggregation": aggregate_subject_macro(details),
            "parameter_sanity": parameter_sanity, "observations": details}


def save_checkpoint(path: Path, heads: dict, optimizer, epoch: int, counters: dict,
                    protocol_hash: str, workset_hash: str, history: list,
                    early_stop_state: dict) -> dict:
    payload = {"status": "PILOT_RESEARCH_CHECKPOINT_NOT_DEPLOYABLE",
               "heads": {name: head.state_dict() for name, head in heads.items()},
               "optimizer": optimizer.state_dict(), "epoch": epoch, "counters": counters,
               "history": history, "early_stop_state": early_stop_state,
               "protocol_sha256": protocol_hash, "workset_sha256": workset_hash}
    torch.save(payload, path)
    loaded = torch.load(path, map_location="cpu", weights_only=False)
    roundtrip = all(torch.equal(tensor.cpu(), loaded["heads"][head][name])
                    for head, module in heads.items() for name, tensor in module.state_dict().items())
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size,
            "head_state_roundtrip_exact": roundtrip}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("dry-run", "smoke", "train"), required=True)
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--workset", type=Path, required=True)
    ap.add_argument("--sam-repo", type=Path)
    ap.add_argument("--checkpoint", type=Path)
    ap.add_argument("--mhr", type=Path)
    ap.add_argument("--output-dir", type=Path)
    ap.add_argument("--resume", type=Path,
                    help="Resume from a completed epoch checkpoint in the same output directory")
    args = ap.parse_args()
    protocol, workset = load_json(args.protocol), load_json(args.workset)
    train_rows, val_rows = validate_workset(workset, args.workset, verify_files=True)
    for row in train_rows + val_rows:
        validate_observation(row["resolved_path"], row["split"])
    if args.mode == "dry-run":
        print(json.dumps({"status": "DRY_RUN_VALID", "optimizer_steps": 0,
                          "sealed_data_accessed": False, "train_samples": len(train_rows),
                          "val_samples": len(val_rows), "protocol_status": protocol.get("status")}, indent=2))
        return
    if protocol.get("status") not in RUNNABLE_PROTOCOL_STATES:
        raise RuntimeError(f"protocol is not authorized to run: {protocol.get('status')}")
    if any(value is None for value in (args.sam_repo, args.checkpoint, args.mhr, args.output_dir)):
        raise ValueError("model paths and --output-dir are required outside dry-run")
    run_cfg = protocol["smoke"] if args.mode == "smoke" else protocol["formal_pilot"]
    if args.mode == "smoke" and run_cfg["epochs"] != 1:
        raise RuntimeError("smoke mode is hard-capped at exactly one epoch")
    if args.mode == "smoke" and args.resume is not None:
        raise RuntimeError("the one-epoch smoke cannot be resumed")
    if args.mode == "train" and protocol["status"] != "FROZEN_FOR_FORMAL_PILOT":
        raise RuntimeError("formal training requires FROZEN_FOR_FORMAL_PILOT")
    checkpoint_hash = sha256_file(args.checkpoint)
    mhr_hash = sha256_file(args.mhr)
    if checkpoint_hash != protocol["initialization"]["checkpoint_sha256"]:
        raise RuntimeError("checkpoint is not the frozen Official SAM 3D Body checkpoint")
    if mhr_hash != protocol["initialization"]["mhr_model_sha256"]:
        raise RuntimeError("MHR asset checksum does not match the frozen protocol")
    expected = protocol["workset_contract"]
    if args.mode == "train":
        train_subjects = {row["subject_id"] for row in train_rows}
        val_subjects = {row["subject_id"] for row in val_rows}
        if len(train_subjects) != expected["train_subjects"] or len(val_subjects) != expected["val_subjects"]:
            raise RuntimeError("formal subject counts do not match frozen protocol")
    if args.mode == "smoke":
        train_rows = train_rows[:run_cfg["maximum_train_observations"]]
        val_rows = val_rows[:run_cfg["maximum_val_observations"]]

    sys.path.insert(0, str(args.sam_repo.resolve()))
    from sam_3d_body import SAM3DBodyEstimator, load_sam_3d_body
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    torch.manual_seed(protocol["seed"])
    np.random.seed(protocol["seed"])
    model, cfg = load_sam_3d_body(str(args.checkpoint), device="cuda", mhr_path=str(args.mhr))
    model.eval().requires_grad_(False)
    heads = {"pose": model.head_pose.proj, "camera": model.head_camera.proj}
    for head in heads.values():
        head.requires_grad_(True)
    trainable_names = [name for name, p in model.named_parameters() if p.requires_grad]
    if (not trainable_names
            or not all(any(name.startswith(prefix) for prefix in ALLOWED_TRAINABLE)
                       for name in trainable_names)
            or not all(any(name.startswith(prefix) for name in trainable_names)
                       for prefix in ALLOWED_TRAINABLE)):
        raise RuntimeError(f"unexpected trainable parameter: {trainable_names}")
    params = [p for p in model.parameters() if p.requires_grad]
    estimator = SAM3DBodyEstimator(model, cfg)
    faces = model.head_pose.faces.detach().long()
    faces_np = faces.cpu().numpy().astype(np.int64)
    initial_heads = {f"{head}.{name}": value.detach().clone()
                     for head, module in heads.items() for name, value in module.named_parameters()}
    teacher = cache_official_teacher(model, estimator, prepare_batch, recursive_to,
                                     train_rows + val_rows)
    optimizer = torch.optim.AdamW(params, lr=protocol["optimizer"]["lr"],
                                  weight_decay=protocol["optimizer"]["weight_decay"])
    protocol_hash, workset_hash = sha256_file(args.protocol), sha256_file(args.workset)
    if args.resume is None:
        args.output_dir.mkdir(parents=True, exist_ok=False)
    else:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if args.resume.resolve().parent != args.output_dir.resolve():
            raise RuntimeError("resume checkpoint must be inside --output-dir")
    start = time.time()
    torch.cuda.reset_peak_memory_stats()
    baseline = evaluate(model, estimator, prepare_batch, recursive_to, val_rows, faces_np,
                        protocol["validation"], protocol["seed"], teacher)
    counters = {"optimizer_updates": 0, "training_observation_exposures": 0}
    history, checkpoints, gradient_seen = [], [], {"pose": False, "camera": False}
    early_stop_state = {"best_value_mm": None, "best_epoch": None,
                        "epochs_without_improvement": 0, "stopped_early": False}
    start_epoch = 1
    elapsed_before_resume = 0.0
    if args.resume is not None:
        saved = torch.load(args.resume, map_location="cpu", weights_only=False)
        allowed_parent = protocol["formal_pilot"].get("continuation_parent_protocol_sha256")
        if (saved["protocol_sha256"] not in {protocol_hash, allowed_parent}
                or saved["workset_sha256"] != workset_hash):
            raise RuntimeError("resume checkpoint protocol/workset hash mismatch")
        if saved["epoch"] >= run_cfg["epochs"]:
            raise RuntimeError("resume checkpoint already reached the planned final epoch")
        for name, head in heads.items():
            head.load_state_dict(saved["heads"][name], strict=True)
        optimizer.load_state_dict(saved["optimizer"])
        counters = dict(saved["counters"])
        history = list(saved["history"])
        early_stop_state = dict(saved["early_stop_state"])
        if early_stop_state["stopped_early"]:
            raise RuntimeError("refusing to resume a run whose early-stop condition already fired")
        start_epoch = int(saved["epoch"]) + 1
        elapsed_before_resume = float(history[-1]["elapsed_seconds"])
        for epoch in range(1, start_epoch):
            prior_path = args.output_dir / f"official_pose_camera_epoch{epoch}.pt"
            if not prior_path.is_file():
                raise FileNotFoundError(f"missing prior epoch checkpoint: {prior_path}")
            checkpoints.append({"path": str(prior_path), "sha256": sha256_file(prior_path),
                                "bytes": prior_path.stat().st_size,
                                "head_state_roundtrip_exact": None,
                                "reconstructed_during_resume": True})
    stop_reason = "PLANNED_FINAL_EPOCH"
    for epoch in range(start_epoch, run_cfg["epochs"] + 1):
        order = np.random.default_rng(stable_seed(protocol["seed"], "order", epoch)).permutation(len(train_rows))
        epoch_losses = []
        accumulation = protocol["optimizer"]["gradient_accumulation_observations"]
        for start_index in range(0, len(order), accumulation):
            chunk = order[start_index:start_index + accumulation]
            optimizer.zero_grad(set_to_none=True)
            for item_index in chunk:
                row = train_rows[int(item_index)]
                output, obs_a = forward_observation(model, estimator, prepare_batch, recursive_to,
                                                    row["resolved_path"])
                vertices = output["pred_vertices"] + output["pred_cam_t"][:, None, :]
                surface = robust_surface_loss(vertices, faces, obs_a["points_a"], protocol["loss"],
                                              stable_seed(protocol["seed"], row["id"], epoch))
                joint2, joint3 = stability_loss(output, teacher[row["id"]], model.pelvis_idx,
                                                obs_a["rgb_a"].shape[:2])
                regularizer = head_initialization_loss(heads, initial_heads)
                weights = protocol["loss"]["weights"]
                loss = (weights["surface"] * surface + weights["teacher_joint_2d"] * joint2
                        + weights["teacher_joint_3d"] * joint3
                        + weights["head_initialization"] * regularizer)
                if not torch.isfinite(loss):
                    raise RuntimeError(f"non-finite loss at {row['id']}")
                (loss / len(chunk)).backward()
                counters["training_observation_exposures"] += 1
                epoch_losses.append({"total": float(loss.detach()), "surface_m": float(surface.detach()),
                                     "teacher_joint_2d": float(joint2.detach()),
                                     "teacher_joint_3d": float(joint3.detach()),
                                     "head_initialization": float(regularizer.detach())})
            for name, head in heads.items():
                gradient_seen[name] |= any(p.grad is not None and torch.isfinite(p.grad).all()
                                           and torch.any(p.grad != 0) for p in head.parameters())
            torch.nn.utils.clip_grad_norm_(params, protocol["optimizer"]["gradient_clip_norm"],
                                           error_if_nonfinite=True)
            optimizer.step()
            counters["optimizer_updates"] += 1
        val = evaluate(model, estimator, prepare_batch, recursive_to, val_rows, faces_np,
                       protocol["validation"], protocol["seed"] + epoch, teacher)
        history.append({"epoch": epoch, "training_loss_component_means": {
            key: float(np.mean([value[key] for value in epoch_losses])) for key in epoch_losses[0]},
            "validation": val, "counters": dict(counters),
            "elapsed_seconds": elapsed_before_resume + time.time() - start})
        primary_key = "point_to_triangle_mean_of_subject_frame_medians_mm"
        current_value = val["aggregation"][primary_key]
        early_cfg = protocol["formal_pilot"]["early_stop"]
        selection_eligible = val["parameter_sanity"]["within_all_limits"]
        history[-1]["checkpoint_selection_eligible"] = selection_eligible
        improved = (selection_eligible and (early_stop_state["best_value_mm"] is None
                    or current_value < early_stop_state["best_value_mm"]
                    - early_cfg["minimum_delta_mm"]))
        if improved:
            early_stop_state.update(best_value_mm=current_value, best_epoch=epoch,
                                    epochs_without_improvement=0)
        elif epoch > early_cfg["minimum_epochs_before_early_stop"]:
            early_stop_state["epochs_without_improvement"] += 1
        # E1-E10 is an indivisible first window. Earlier non-improvement cannot
        # spend the patience budget for a later, separately frozen extension.
        if epoch == early_cfg["minimum_epochs_before_early_stop"]:
            early_stop_state["epochs_without_improvement"] = 0
        should_stop = (args.mode == "train" and early_cfg["enabled"]
                       and epoch > early_cfg["minimum_epochs_before_early_stop"]
                       and early_stop_state["epochs_without_improvement"]
                       >= early_cfg["patience_epochs"])
        if should_stop:
            early_stop_state["stopped_early"] = True
            stop_reason = "EARLY_STOP_PATIENCE_EXHAUSTED"
        checkpoint_path = args.output_dir / f"official_pose_camera_epoch{epoch}.pt"
        checkpoints.append(save_checkpoint(checkpoint_path, heads, optimizer, epoch, counters,
                                           protocol_hash, workset_hash, history, early_stop_state))
        progress = {"status": "EPOCH_COMPLETE", "last_epoch": epoch,
                    "epochs_planned": run_cfg["epochs"], "counters": counters,
                    "early_stop_state": early_stop_state, "checkpoints": checkpoints,
                    "sealed_data_accessed": False}
        (args.output_dir / "run_progress.json").write_text(json.dumps(progress, indent=2),
                                                           encoding="utf-8")
        if should_stop:
            break

    completed_epochs = len(history)
    expected_updates = completed_epochs * math.ceil(len(train_rows) / accumulation)
    expected_exposures = completed_epochs * len(train_rows)
    final_agg = history[-1]["validation"]["aggregation"]
    smoke_checks = {
        "exactly_one_epoch": args.mode != "smoke" or len(history) == 1,
        "optimizer_updates_exact": counters["optimizer_updates"] == expected_updates,
        "observation_exposures_exact": counters["training_observation_exposures"] == expected_exposures,
        "both_heads_received_nonzero_finite_gradient": all(gradient_seen.values()),
        "checkpoint_roundtrip_exact": all(row["head_state_roundtrip_exact"] for row in checkpoints),
        "validation_primary_finite": bool(np.isfinite(final_agg[
            "point_to_triangle_mean_of_subject_frame_medians_mm"])),
        "rendered_depth_coverage_above_floor": bool(
            final_agg["rendered_depth_median_coverage"] >= protocol[
                "smoke_gate"]["minimum_rendered_depth_coverage"]),
        "sealed_data_accessed": False,
    }
    smoke_pass = all(value is True for key, value in smoke_checks.items() if key != "sealed_data_accessed")
    eligible_indices = [index for index, row in enumerate(history)
                        if row.get("checkpoint_selection_eligible", False)]
    best_index = (None if not eligible_indices else min(
        eligible_indices, key=lambda index: history[index]["validation"]["aggregation"][primary_key]))
    selection = None if args.mode == "smoke" or best_index is None else {
        "epoch": history[best_index]["epoch"], "checkpoint": checkpoints[best_index]["path"],
        "primary_metric": protocol["validation"]["primary_selection_metric"],
        "value_mm": history[best_index]["validation"]["aggregation"][primary_key],
        "parameter_sanity_qualified": True, "tie_policy": "earliest epoch",
    }
    formal_status = ("FAILED_PARAMETER_SANITY_NO_ELIGIBLE_CHECKPOINT" if best_index is None
                     else "EARLY_STOPPED_FORMAL_PILOT_PENDING_SCIENTIFIC_REVIEW"
                     if early_stop_state["stopped_early"]
                     else "COMPLETED_FORMAL_PILOT_PENDING_SCIENTIFIC_REVIEW")
    report = {
        "status": ("PASS_1_EPOCH_ENGINEERING_SMOKE_NOT_EFFICACY" if args.mode == "smoke" and smoke_pass
                   else "FAIL_1_EPOCH_ENGINEERING_SMOKE" if args.mode == "smoke"
                   else formal_status),
        "initialization": "Official SAM 3D Body checkpoint", "trainable_modules": list(ALLOWED_TRAINABLE),
        "vertex_offsets": "DISABLED", "sealed_data_accessed": False,
        "new_supervision": "Camera-A person-mask RGB-D surface only",
        "stability_terms": "detached Official teacher 2D and pelvis-relative 3D joints plus head-init L2",
        "selection_metric": protocol["validation"]["primary_selection_metric"],
        "selected_checkpoint": selection,
        "baseline_validation": baseline, "history": history, "counters": counters,
        "epochs_planned": run_cfg["epochs"], "epochs_completed": completed_epochs,
        "stop_reason": stop_reason, "early_stop_state": early_stop_state,
        "elapsed_seconds": elapsed_before_resume + time.time() - start,
        "peak_cuda_allocated_gib": torch.cuda.max_memory_allocated() / 2 ** 30,
        "checkpoints": checkpoints, "smoke_gate": smoke_checks,
        "input_assets": {"official_checkpoint_sha256": checkpoint_hash,
                         "mhr_model_sha256": mhr_hash},
        "protocol_sha256": protocol_hash, "workset_sha256": workset_hash,
        "claim_limit": "A smoke pass proves execution integrity only; VAL efficacy and SEALED generalization remain unclaimed.",
    }
    (args.output_dir / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.mode == "smoke" and not smoke_pass:
        raise RuntimeError("one-epoch smoke gate failed; inspect training_report.json")


if __name__ == "__main__":
    main()
