"""Build the V2 HuMMan subject protocol without reading sealed/reserve pixels."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OLD = ROOT / "docs/handoffs/real-scene-2026-09-09/public-rgbd-surface-finetuning-pilot-v1"
OUT = Path(__file__).resolve().parent.parent
SEED = "humman-single-multiview-v2-20260910"


def read(name: str) -> dict:
    return json.loads((OLD / name).read_text(encoding="utf-8"))


def write(name: str, value: dict) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def main() -> None:
    inventory = read("HUMMAN_EXISTING_ARCHIVE_INVENTORY_V1.json")
    old_split = read("HUMMAN_SUBJECT_SPLIT_V1.json")
    old_qa = json.loads((OLD / "evidence/nonsealed-rgbd-registration/NONSEALED_RGBD_REGISTRATION_QA_FINAL_V1.json").read_text(encoding="utf-8"))
    old_sealed_qa = read("SEALED_RGBD_REGISTRATION_QA_FINAL_V1.json")
    seq_rows = [row for row in inventory["packed_coverage"]["sequence_records"] if row["structurally_usable"]]
    by_subject: dict[str, list[dict]] = defaultdict(list)
    for row in seq_rows:
        by_subject[row["subject"]].append(row)

    history = {}
    labels = {
        "V1_DEVELOPMENT": old_split["final_subjects"]["DEV_EXCLUDED_FROM_TRAINER"],
        "V1_TRAIN_CONSUMED": old_split["final_subjects"]["TRAIN"],
        "V1_VAL_CONSUMED": old_split["final_subjects"]["VAL"],
        "V1_SEALED_CONSUMED": old_split["final_subjects"]["SEALED_EXCLUDED"],
    }
    for label, subjects in labels.items():
        for subject in subjects:
            history[subject] = label

    old_pass = ({row["subject"] for row in old_qa["results"] if row["usable"]} |
                {row["subject"] for row in old_sealed_qa["results"] if row["usable"]})
    available_new = sorted(set(by_subject) - set(history), key=lambda s: digest(f"{SEED}:{s}"))
    assert len(available_new) == 100

    # Reserve and sealed are bound from header-only inventory. Their sequences,
    # frames and pixels are deliberately not selected or inspected here.
    reserve = available_new[:15]
    sealed = available_new[15:27]
    val = available_new[27:39]
    new_train = available_new[39:84]
    qa_alternates = available_new[84:]
    historical_train = old_split["final_subjects"]["TRAIN"]
    train = historical_train + new_train
    old_extract = read("SERVER_SELECTIVE_EXTRACTION_PLAN_V1.json")
    old_observation = {r["subject"]: r for r in old_extract["observations"]}

    def select_sequence(subject: str) -> dict:
        candidates = sorted(by_subject[subject], key=lambda r: digest(f"{SEED}:sequence:{r['sequence']}"))
        row = candidates[0]
        cams = {c["camera"]: c for c in row["cameras"]}
        common = None
        for camera in ("kinect_008", "kinect_009"):
            ids = {i for lo, hi in cams[camera]["paired_frame_ranges"] for i in range(lo, hi + 1)}
            common = ids if common is None else common & ids
        ids = sorted(common)
        frames = sorted({ids[round((len(ids) - 1) * q)] for q in (.25, .50, .75)})
        return {"subject": subject, "sequence": row["sequence"], "action": row["action"],
                "action_name": row.get("action_name"), "frame_ids": frames,
                "camera_candidates": ["kinect_008", "kinect_009"],
                "selection_basis": "ARCHIVE_HEADER_METADATA_ONLY"}

    nonsealed_plan = []
    for split, subjects in (("TRAIN_HISTORICAL", historical_train), ("TRAIN_NEW", new_train), ("VAL_NEW", val)):
        for subject in subjects:
            if split == "TRAIN_HISTORICAL":
                old = old_observation[subject]
                row = {"subject": subject, "sequence": old["sequence"], "action": old["action"],
                       "action_name": old_split["one_sequence_per_subject_candidates"][subject].get("action_name"),
                       "frame_ids": old["frame_ids"], "camera_candidates": old["cameras"],
                       "selection_basis": "V1_FROZEN_WORKSET_REUSE"}
            else:
                row = select_sequence(subject)
            row["split"] = split; nonsealed_plan.append(row)

    groups = {"TRAIN": train, "VAL": val, "V2_SEALED": sealed,
              "FINAL_RESERVE": reserve, "QA_ALTERNATES": qa_alternates,
              "HISTORICAL_DEVELOPMENT_EXCLUDED": sorted(history)}
    all_primary = [set(groups[k]) for k in ("TRAIN", "VAL", "V2_SEALED", "FINAL_RESERVE")]
    assert all(not (a & b) for i, a in enumerate(all_primary) for b in all_primary[i + 1:])

    archive_bindings = []
    for row in inventory["archives"]:
        archive_bindings.append({"file": Path(row["path"]).name, "bytes": row["bytes"],
                                 "sha256": row["prior_report_sha256_not_rehashed_this_scan"]})

    qa = {
        "status": "PARTIAL_GEOMETRY_QA_REQUIRES_NEW_NONSEALED_EXTRACTION",
        "scope": "SUBJECT_LEVEL_ARCHIVE_AND_EXISTING_PIXEL_QA",
        "source_structural_inventory": str((OLD / "HUMMAN_EXISTING_ARCHIVE_INVENTORY_V1.json").as_posix()),
        "archive_bindings": archive_bindings,
        "counts": {"structurally_usable_subjects": len(by_subject), "historically_pixel_geometry_qa_passed": len(old_pass),
                   "new_structural_candidates": len(available_new), "new_pixel_geometry_qa_passed": 0},
        "definitions": {
            "structurally_usable": "At least one sequence has RGB video, depth, mask, intrinsics/extrinsics and matching frame IDs in headers.",
            "geometry_qa_passed": "Decoded RGB/depth/mask, valid registered person geometry, valid camera rotation and two-view consistency checked.",
        },
        "historical_subject_status": [{"subject": s, "history": history[s],
                                       "existing_geometry_qa": "PASS" if s in old_pass else "NOT_ESTABLISHED"}
                                      for s in sorted(history)],
        "new_nonsealed_qa_plan": nonsealed_plan,
        "sealed_and_reserve_pixel_policy": "NO PIXEL/FRAME/SEQUENCE CONTENT READ BEFORE THE APPLICABLE GATE",
        "download": {"performed": False, "required_now": False, "reason": "Existing archives contain 100 new structural candidates."},
        "readiness_effect": "NOT_READY until new TRAIN/VAL selective extraction and geometry QA finish",
    }
    split = {
        "status": "V2_SUBJECT_SPLIT_PRECOMMITTED_PENDING_NONSEALED_GEOMETRY_QA",
        "seed": SEED,
        "assignment_rule": "SHA256(seed:subject); first 15 Final Reserve, next 12 V2 Sealed, next 12 VAL, next 45 new TRAIN, remaining 16 QA alternates; append 15 V1 TRAIN subjects to TRAIN.",
        "groups": groups,
        "counts": {k: len(v) for k, v in groups.items()},
        "train_composition": {"new_subjects": len(new_train), "historical_v1_train_subjects": len(historical_train), "total": len(train)},
        "subject_disjoint_primary_splits": True,
        "all_sequences_frames_cameras_actions_follow_subject": True,
        "history_policy": "V1 TRAIN may remain TRAIN and is explicitly consumed; V1 DEV/VAL/SEALED are excluded from V2 VAL, V2 SEALED and Final Reserve.",
        "new_nonsealed_observation_plan": nonsealed_plan,
        "seal_policy": {"V2_SEALED": "IDENTITY BOUND; DO NOT OPEN UNTIL S/M WINNER FREEZE",
                        "FINAL_RESERVE": "IDENTITY BOUND; DO NOT OPEN IN V2"},
    }
    reserve_manifest = {
        "status": "FINAL_RESERVE_IDENTITY_SEALED_HEADER_ONLY",
        "seed": SEED,
        "subject_ids": reserve,
        "subject_count": len(reserve),
        "archive_bindings": archive_bindings,
        "content_opened": False,
        "sequence_selected": False,
        "frame_or_camera_selected": False,
        "allowed_information_used": ["subject identity", "archive membership", "archive byte size", "previously recorded SHA256"],
        "prohibition": "Do not decode/list subject-specific frame, sequence, action, RGB, depth or mask content during V2.",
    }
    write("HUMMAN_V2_SUBJECT_QA_V1.json", qa)
    write("HUMMAN_V2_SUBJECT_SPLIT_V1.json", split)
    write("HUMMAN_V2_FINAL_RESERVE_MANIFEST_V1.json", reserve_manifest)
    depth_archive_for_sequence = {}
    for archive in inventory["archives"]:
        name = Path(archive["path"]).name
        if name.startswith("point_kinect_depth_part_"):
            for sequence in archive["sequences"]:
                depth_archive_for_sequence[sequence] = name
    members: dict[str, set[str]] = defaultdict(set)
    for row in nonsealed_plan:
        if row["split"] == "TRAIN_HISTORICAL":
            continue
        sequence = row["sequence"]
        members["point_cameras.7z"].add(f"{sequence}/cameras.json")
        for camera in row["camera_candidates"]:
            members["point_kinect_color_part_02.7z"].add(f"{sequence}/kinect_color/{camera}.mp4")
            for frame in row["frame_ids"]:
                members[depth_archive_for_sequence[sequence]].add(f"{sequence}/kinect_depth/{camera}/{frame:06d}.png")
                members["point_kinect_mask.7z"].add(f"{sequence}/kinect_mask/{camera}/{frame:06d}.png")
    extraction = {
        "status": "READY_FOR_NEW_TRAIN_VAL_SELECTIVE_EXTRACTION",
        "server_archive_root": "/raid5/xuhd/datasets/humman/archives",
        "server_workset_root": "/raid5/xuhd/public_rgbd_single_vs_multiview_v2/workset_nonsealed_v1",
        "subject_split_seed": SEED,
        "observations": [r for r in nonsealed_plan if r["split"] != "TRAIN_HISTORICAL"],
        "historical_train_reuse_root": "/raid5/xuhd/public_rgbd_surface_finetuning_pilot_v1/workset_v1",
        "archives": [{"file": name,
                      "sha256": next(a["prior_report_sha256_not_rehashed_this_scan"] for a in inventory["archives"] if Path(a["path"]).name == name),
                      "members": sorted(paths)} for name, paths in sorted(members.items())],
        "v2_sealed_subjects_excluded": sealed,
        "final_reserve_subjects_excluded": reserve,
        "sealed_or_reserve_pixels_selected": False,
        "selected_new_subject_count": len(new_train) + len(val),
        "selected_member_count": sum(len(x) for x in members.values()),
    }
    write("raw/HUMMAN_V2_NONSEALED_EXTRACTION_PLAN_V1.json", extraction)
    print(json.dumps({"counts": split["counts"], "qa_status": qa["status"]}, indent=2))


if __name__ == "__main__":
    main()
