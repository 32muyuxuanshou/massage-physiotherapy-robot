"""Build the V2 postmortem and surface-supervision decision handoff.

This script is read-only with respect to model checkpoints.  It consumes the
completed inference audit and training report, then creates review artifacts.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
OUT = ROOT / "docs/handoffs/real-scene-2026-09-09/back-surface-supervision-pilot-v1"
VIS = OUT / "visualizations"
RAW = OUT / "raw"
CODE = OUT / "code"
for directory in (OUT, VIS, RAW, CODE):
    directory.mkdir(parents=True, exist_ok=True)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


raw = load(EVIDENCE / "VISIBLE_AB_V2_POSTMORTEM_RAW.json")
loss_audit = load(EVIDENCE / "LOSS_GRADIENT_AUDIT_V1.json")
training_report = load(EVIDENCE / "report.json")
protocol = load(EVIDENCE / "protocol.json")
epochs = {row["epoch"]: row for row in raw["epochs"]}


def image_scores(epoch: int, visibility: set[int]):
    grouped = defaultdict(list)
    for row in raw["details"]:
        if row["epoch"] == epoch and row["visibility"] in visibility:
            grouped[row["image"]].append(row["normalized_error"])
    return {
        image: {"nme": float(np.mean(values)), "pck05": float(np.mean(np.asarray(values) < 0.05))}
        for image, values in grouped.items()
    }


def paired_bootstrap(left_epoch: int, right_epoch: int, visibility: set[int], seed: int = 20260909):
    left, right = image_scores(left_epoch, visibility), image_scores(right_epoch, visibility)
    names = sorted(set(left) & set(right))
    rng = np.random.default_rng(seed + left_epoch * 100 + right_epoch)
    result = {"images": len(names), "replicates": 10000, "unit": "image"}
    for metric in ("nme", "pck05"):
        delta = np.asarray([right[name][metric] - left[name][metric] for name in names])
        draws = rng.integers(0, len(delta), size=(10000, len(delta)))
        means = delta[draws].mean(axis=1)
        result[metric] = {
            "mean_delta_right_minus_left": float(delta.mean()),
            "paired_percentile_95_ci": [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))],
            "images_improved": int((delta < 0).sum()) if metric == "nme" else int((delta > 0).sum()),
            "direction_of_improvement": "negative" if metric == "nme" else "positive",
        }
    return result


per_epoch = []
for epoch in range(11):
    row = epochs[epoch]
    legacy = training_report["baseline"] if epoch == 0 else training_report["history"][epoch - 1]["validation"]
    per_epoch.append(
        {
            "epoch": epoch,
            "tag": row["tag"],
            "legacy_image_macro_person_first": legacy,
            "diagnostic_all_labeled": row["all_labeled"],
            "diagnostic_visible_v2": row["visible_v2"],
            "diagnostic_labeled_not_visible_v1": row["labeled_not_visible_v1"],
        }
    )


per_joint = []
for joint in epochs[0]["per_joint"]:
    values = {}
    for epoch in (0, 5, 10):
        values[str(epoch)] = epochs[epoch]["per_joint"][joint]
    base = values["0"]["all_labeled"]["image_macro_nme"]
    values["relative_nme_change_percent"] = {
        "epoch5_vs_official": 100 * (values["5"]["all_labeled"]["image_macro_nme"] / base - 1),
        "epoch10_vs_official": 100 * (values["10"]["all_labeled"]["image_macro_nme"] / base - 1),
    }
    per_joint.append({"joint": joint, **values})


categories = {}
for category in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle"):
    selected = [row for row in per_joint if row["joint"].endswith(category)]
    categories[category] = {
        "joints": [row["joint"] for row in selected],
        "mean_relative_nme_change_percent": {
            key: float(np.mean([row["relative_nme_change_percent"][key] for row in selected]))
            for key in ("epoch5_vs_official", "epoch10_vs_official")
        },
    }


postmortem = {
    "status": "COMPLETED_READ_ONLY_POSTMORTEM",
    "scope": "COCO-source validation: 69 images, 82 people, 821 labeled body-joint observations",
    "training_contract": {
        "manual_supervision": "COCO shoulder-to-ankle body joints with visibility v=2 only",
        "legacy_evaluation": "COCO visibility v>0; per-person means followed by image-macro mean",
        "diagnostic_evaluation": "visibility split; image-macro NME over joint observations and pooled-joint PCK/percentiles",
        "normalization": "Euclidean pixel error divided by sqrt(COCO annotation bbox area)",
        "selection_warning": "Epochs 5 and 10 were inspected on this validation set; it is not an untouched test.",
    },
    "reported_value_reconciliation": {
        "legacy_report_is_authoritative_for_original_claim": True,
        "legacy": {
            "official_nme": training_report["baseline"]["nme"],
            "official_pck05": training_report["baseline"]["pck05"],
            "epoch5_nme": training_report["history"][4]["validation"]["nme"],
            "epoch5_pck05": training_report["history"][4]["validation"]["pck05"],
            "epoch10_nme": training_report["history"][9]["validation"]["nme"],
            "epoch10_pck05": training_report["history"][9]["validation"]["pck05"],
        },
        "why_diagnostic_numbers_differ_slightly": "The original evaluator averages each person's joint mean and then image-macros people. The postmortem image-macros joint observations and pools PCK/tails. Both use the same predictions and normalization.",
    },
    "per_epoch": per_epoch,
    "per_joint_official_epoch5_epoch10": per_joint,
    "joint_category_summary": categories,
    "paired_image_bootstrap": {
        "epoch5_vs_official": paired_bootstrap(0, 5, {1, 2}),
        "epoch10_vs_official": paired_bootstrap(0, 10, {1, 2}),
        "epoch10_vs_epoch5": paired_bootstrap(5, 10, {1, 2}),
        "visible_epoch5_vs_official": paired_bootstrap(0, 5, {2}),
        "visible_epoch10_vs_official": paired_bootstrap(0, 10, {2}),
    },
    "conclusions": {
        "v2_2d_improvement_reproduced": True,
        "where_improvement_occurs": "Largest task-relevant gain is at hips (epoch5 mean relative NME -6.32% across left/right). Shoulders improve only -1.46%. Right elbow and left wrist also improve; knees and ankles are mixed. The gain is not mainly a distal hand/foot artifact.",
        "epoch5": "Best original-contract NME and best diagnostic all-labeled NME; 31 bad-tail joints versus 35 official, but diagnostic P99 is worse than official.",
        "epoch10": "Best original-contract PCK05 and tied best diagnostic pooled PCK05; lower P90/P95 than epoch5, but worse mean NME and 32 bad-tail joints. It trades mean error for more points under the 0.05 threshold.",
        "visibility": "The direction holds for v=2 visible joints. The v=1 subset has only 44 observations, was not manually supervised, and is too small for strong claims.",
        "claim_boundary": "This validates a 2D joint signal on a reused COCO-source validation set. It does not validate mesh surface, unseen target-domain subjects, DMD37, or medical accuracy.",
    },
}
dump(OUT / "VISIBLE_AB_V2_POSTMORTEM_V1.json", postmortem)
dump(OUT / "LOSS_GRADIENT_AUDIT_V1.json", loss_audit)
shutil.copy2(EVIDENCE / "VISIBLE_AB_V2_POSTMORTEM_RAW.json", RAW / "VISIBLE_AB_V2_POSTMORTEM_RAW.json")
for name in ("postmortem_infer.py", "loss_gradient_audit.py", "build_delivery.py"):
    shutil.copy2(EVIDENCE / name, CODE / name)


with (OUT / "PER_EPOCH_JOINT_METRICS.csv").open("w", newline="", encoding="utf-8") as handle:
    fields = ["epoch", "legacy_nme", "legacy_pck05", "diagnostic_nme", "diagnostic_pck05", "p50", "p90", "p95", "p99", "bad_tail_count", "bad_tail_ratio"]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for row in per_epoch:
        a, legacy = row["diagnostic_all_labeled"], row["legacy_image_macro_person_first"]
        writer.writerow({
            "epoch": row["epoch"], "legacy_nme": legacy["nme"], "legacy_pck05": legacy["pck05"],
            "diagnostic_nme": a["image_macro_nme"], "diagnostic_pck05": a["pck05"],
            **a["percentiles"], "bad_tail_count": a["bad_tail_count"], "bad_tail_ratio": a["bad_tail_ratio"],
        })


with (OUT / "PER_JOINT_EPOCH5_EPOCH10.csv").open("w", newline="", encoding="utf-8") as handle:
    fields = ["joint", "official_nme", "epoch5_nme", "epoch10_nme", "epoch5_relative_change_percent", "epoch10_relative_change_percent"]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for row in per_joint:
        writer.writerow({
            "joint": row["joint"],
            "official_nme": row["0"]["all_labeled"]["image_macro_nme"],
            "epoch5_nme": row["5"]["all_labeled"]["image_macro_nme"],
            "epoch10_nme": row["10"]["all_labeled"]["image_macro_nme"],
            "epoch5_relative_change_percent": row["relative_nme_change_percent"]["epoch5_vs_official"],
            "epoch10_relative_change_percent": row["relative_nme_change_percent"]["epoch10_vs_official"],
        })


inventory = {
    "status": "AUDITED",
    "decision_rule": "Count unique subjects/events and independent target-relevant observations, not frames times points.",
    "candidates": [
        {
            "source": "B1/B2/B3/B5/N1 sparse visible-boundary references",
            "repository_evidence": "AI感知模块/outputs/内部工程证据/2026-09-08_TARGET_DATA_V1/targets.json",
            "human_or_real_observation": "assistant observations on original real RGB",
            "derived_from_sam_or_mhr": False,
            "previous_predictions_seen": True,
            "training_target": "18 references across B1/B3/N1 were planned for train; 7 across B2/B5 for development validation",
            "independent_evaluation_eligible": False,
            "coverage": {"images": 5, "source_or_subject_groups": 5, "sparse_references": 25, "sealed_test_subjects": 0},
            "target_back_relevance": "partial torso side contours; not dense bare-back surface",
            "confounders": ["B2 shoulder cloth", "B3 waist clothing", "B5 arm occlusion", "all references created after model predictions had been viewed"],
        },
        {
            "source": "B4 real image",
            "repository_evidence": "AI感知模块/outputs/内部工程证据/2026-09-08_TARGET_DATA_V1/targets.json",
            "human_or_real_observation": "real RGB; no eligible contour label",
            "derived_from_sam_or_mhr": False,
            "previous_predictions_seen": True,
            "training_target": False,
            "independent_evaluation_eligible": False,
            "coverage": {"images": 1, "source_or_subject_groups": 0, "sparse_references": 0},
            "target_back_relevance": "arm/trunk contact makes isolated torso boundary ambiguous",
            "confounders": ["arm contact", "same session/person group as B3"],
        },
        {
            "source": "S01-S08 user-video frames",
            "repository_evidence": "docs/handoffs/real-scene-2026-09-06/evidence/input_manifest.json",
            "human_or_real_observation": "real RGB frames; assistant-reviewed ROIs and region states",
            "derived_from_sam_or_mhr": False,
            "previous_predictions_seen": True,
            "training_target": False,
            "independent_evaluation_eligible": False,
            "coverage": {"frames": 8, "videos": 2, "verified_unique_subjects": 0, "labeled_surface_masks": 0},
            "target_back_relevance": "high, but current labels are visibility/region drafts rather than surface truth",
            "confounders": ["robot/contact head", "bed", "occlusion", "cropping", "subject identities unverified", "adjacent video frames are correlated"],
        },
        {
            "source": "S01/S03/S05 assistant contour checks",
            "repository_evidence": "docs/handoffs/real-scene-2026-09-06/audit-2026-09-07/contour_diagnostics.csv",
            "human_or_real_observation": "assistant observations on original RGB",
            "derived_from_sam_or_mhr": False,
            "previous_predictions_seen": True,
            "training_target": False,
            "independent_evaluation_eligible": False,
            "coverage": {"frames": 3, "videos": 1, "verified_unique_subjects": 0, "sparse_references": 9},
            "target_back_relevance": "visible outer-boundary diagnostics",
            "confounders": ["same video", "robot occlusion", "not blind", "no dense or 3D surface measurement"],
        },
        {
            "source": "S05 hand-traced visible-person mask",
            "repository_evidence": "docs/handoffs/real-scene-2026-09-06/mask-ab-2026-09-07/mask_provenance.json",
            "human_or_real_observation": "assistant hand trace on original RGB",
            "derived_from_sam_or_mhr": False,
            "previous_predictions_seen": True,
            "training_target": False,
            "independent_evaluation_eligible": False,
            "coverage": {"frames": 1, "masks": 1},
            "target_back_relevance": "visible person silhouette, not bare-back surface",
            "confounders": ["includes hair, skin and clothing", "same-image contour checks overlap", "mask-prompt inference is not contour-loss training"],
        },
        {
            "source": "COCO human segmentations/keypoints",
            "repository_evidence": "AI感知模块/outputs/内部工程证据/2026-09-08_COCO2014_DATASET",
            "human_or_real_observation": "human-annotated real-image person masks/keypoints where available",
            "derived_from_sam_or_mhr": False,
            "previous_predictions_seen": "some development outputs viewed; source may overlap SAM pretraining",
            "training_target": "V2 uses visible keypoints, not masks",
            "independent_evaluation_eligible": False,
            "coverage": {"v2_images": 343, "v2_people": 427, "target_bare_back_count_audited": 0},
            "target_back_relevance": "generic clothed-person silhouette; not visible bare-back surface",
            "confounders": ["clothing", "occlusion", "non-target domain", "possible pretraining overlap"],
        },
        {
            "source": "official SAM 3D Body MHR fitted labels and projected mesh",
            "repository_evidence": "docs/handoffs/real-scene-2026-09-09/scaleup343",
            "human_or_real_observation": False,
            "derived_from_sam_or_mhr": True,
            "previous_predictions_seen": True,
            "training_target": "fitted 2D and pelvis-relative fitted 3D joints are used",
            "independent_evaluation_eligible": False,
            "coverage": {"v2_images": 343, "v2_people": 427},
            "target_back_relevance": "model fit, not independent target surface truth",
            "confounders": ["self-confirmation if used to evaluate SAM/MHR", "joint rather than surface supervision"],
        },
        {
            "source": "DMD37 engineering Atlas and projected points",
            "repository_evidence": "docs/handoffs/real-scene-2026-09-09/atlas-query",
            "human_or_real_observation": False,
            "derived_from_sam_or_mhr": "Atlas binding is fixed; image projections inherit predicted mesh/camera",
            "previous_predictions_seen": True,
            "training_target": False,
            "independent_evaluation_eligible": False,
            "coverage": {"engineering_points": 37, "medical_truth": False},
            "target_back_relevance": "downstream engineering topology/binding only",
            "confounders": ["not patient anatomy truth", "cannot prove source mesh accuracy"],
        },
        {
            "source": "calibrated RGB-D or synchronized multi-view target-back captures",
            "repository_evidence": None,
            "human_or_real_observation": "would be direct sensor observation after calibration and quality control",
            "derived_from_sam_or_mhr": False,
            "previous_predictions_seen": False,
            "training_target": "unavailable",
            "independent_evaluation_eligible": "yes if captured and sealed before model review",
            "coverage": {"available_subjects": 0, "available_events": 0},
            "target_back_relevance": "high",
            "confounders": ["depth holes on skin/hair", "robot occlusion", "cross-sensor registration", "bed/contact surfaces must be masked"],
        },
    ],
}
dump(OUT / "SURFACE_SUPERVISION_INVENTORY_V1.json", inventory)


decision = {
    "decision": "INSUFFICIENT_NEED_NEW_SURFACE_REFERENCE",
    "formal_surface_training_started": False,
    "basis": {
        "unique_subjects": "Only five conservative public source/subject groups have sparse references; no sealed unseen target-domain subject test exists.",
        "event_region_coverage": "A few standing, raised-arm, leaning and seated views; no adequate lying/prone, strong twist, robot/bed/contact, body-shape, clothing and occlusion strata.",
        "supervision_independence": "Existing contour drafts were produced after predictions had been viewed, and S05 mask/contour share the same image. SAM/MHR fits and Atlas projections are model-derived.",
        "target_back_relevance": "Twenty-five references are sparse 2D outer-boundary samples, not a dense visible bare-back surface or calibrated depth measurement.",
    },
    "why_no_10_epoch_surface_run": "Without an independent held-out surface metric, a lower training contour loss would only demonstrate fitting and could not answer whether unseen back surfaces improve.",
    "minimum_collection_plan": {
        "scope": "Operational minimum for a controlled pilot, not a powered clinical study",
        "subjects": 30,
        "images": "2-4 non-adjacent target-region observations per subject (about 60-120 images)",
        "subject_split": {"train": 18, "validation": 6, "sealed_test": 6},
        "split_rule": "Split by verified person plus capture session before annotation/model review; no adjacent frames or same person across splits.",
        "required_event_families": [
            "prone/lying on treatment bed with and without robot/contact occlusion",
            "seated or forward-leaning target back",
            "standing with neutral, raised-arm and strong-twist poses",
        ],
        "coverage_controls": ["sex/body-shape diversity", "near/far scale", "oblique views", "partial visibility", "hair", "waist/shoulder clothing", "bed and robot boundaries"],
        "annotation": {
            "source_view": "Annotate original RGB/depth without any mesh overlay.",
            "labels": ["visible bare-back skin", "other skin", "clothing", "hair", "robot", "bed", "self-occlusion", "unknown"],
            "geometry": "Dense pixel mask plus uncertainty boundary; calibrated depth or multi-view surface where available.",
            "quality": "Two independent annotators for validation/test, adjudication, and saved disagreement/unknown regions.",
            "provenance": "Record subject/session IDs, camera calibration, timestamps, annotator, revision, and whether any prediction had been seen."
        },
        "use": {
            "train": "18-subject labels may drive the new surface loss.",
            "validation": "6 subjects may select epoch and loss weight; they cease to be final test once used for tuning.",
            "sealed_test": "6 subjects remain inaccessible until protocol, code, thresholds and checkpoint are frozen."
        },
        "primary_metric": "Held-out visible bare-back symmetric contour distance and, where depth exists, robust point-to-observed-depth error; report mean/median/P90/P95/worst/per-subject.",
        "secondary_metrics": ["manual joint NME/PCK05 regression", "camera/shape/scale sanity", "failure strata"],
    },
}
dump(OUT / "BACK_SURFACE_SUPERVISION_DATA_DECISION_V1.json", decision)


adaptation = {
    "status": "ANALYZED_NOT_EXECUTED_DUE_TO_DATA_DECISION",
    "recommended_order": ["collect independent surface references", "A/B current output heads + surface loss", "only then test larger adaptation if the A/B diagnoses under-capacity"],
    "options": {
        "A_current_output_head_tuning": {
            "solves": "low-cost global correction of pose/camera/shape outputs",
            "current_evidence": "V2 changes 2D joint validation modestly; no surface evidence",
            "required_supervision": "independent train/validation surface observations plus joint regression metric",
            "risk": "camera and pose can absorb 2D loss without improving 3D surface",
            "minimum_ab": "same official initialization and joint loss; B adds only surface loss",
            "execute_when": "after subject-disjoint surface train/validation data exist",
        },
        "B_output_head_plus_limited_body_decoder": {
            "solves": "more capacity for target-domain image-to-body mapping",
            "current_evidence": "not supported yet; current failure could be supervision rather than capacity",
            "required_supervision": "larger diverse surface dataset with held-out subjects",
            "risk": "overfit and damage general pose robustness",
            "minimum_ab": "freeze all else and unfreeze only the last body-decoder block against option A",
            "execute_when": "only if A underfits training and validation together after labels are valid",
        },
        "C_adapter_or_lora": {
            "solves": "parameter-efficient feature/domain adaptation",
            "current_evidence": "no evidence that feature adaptation is the current bottleneck",
            "required_supervision": "more target-domain subjects than the minimum output-head pilot",
            "risk": "correlated small data can overfit despite few trainable parameters",
            "minimum_ab": "A versus same insertion points with fixed LoRA rank/seed/budget",
            "execute_when": "after output-head pilot shows repeatable surface signal but limited capacity",
        },
        "D_per_image_parameter_refinement": {
            "solves": "fit one observed person/image using masks, depth or multi-view evidence",
            "current_evidence": "prototype shows one training image contour can be fitted, partly through camera; no generalization proof",
            "required_supervision": "per-image calibrated depth/multiview or trusted mask with occlusion labels",
            "risk": "local fit, camera/shape cheating, latency; cannot stand in for global fine-tuning",
            "minimum_ab": "hold out some observed pixels/views for the same subject and check 3D/depth plus camera priors",
            "execute_when": "useful as a robot-time engineering module once sensor evidence exists, in parallel with global-model research",
        },
    },
}
dump(OUT / "MODEL_ADAPTATION_DECISION_V1.json", adaptation)


checks = {
    "official": {"server_path": "/raid5/xuhd/sam3d_s01_pilot_20260906/weights/model.ckpt", "sha256": "3b1cb897f4bbd977bf81cbb0b30780a9582681ac642ee112865790ceb4d66056", "bytes": 1691205237, "preserved": True},
    "v2_epoch5": {"server_path": "/raid5/xuhd/nlf_pilot_20260908/visible_ab_v2/heads_epoch5.pt", "sha256": "0b34bc092ebad40ea920b95277ea4a398f686d24dfff0dccb67d821db7583f65", "bytes": 31623146, "preserved": True},
    "v2_epoch10": {"server_path": "/raid5/xuhd/nlf_pilot_20260908/visible_ab_v2/heads_epoch10.pt", "sha256": "9a35879e66952043368bce9cb5e5f85891cba017228e3aba941fa2079f508f41", "bytes": 31623182, "preserved": True},
    "distribution": "Authorized weights are not committed to the public repository.",
}
for name in ("protocol.json", "samples.json", "train.py"):
    path = EVIDENCE / name
    checks[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
dump(OUT / "CHECKPOINT_MANIFEST.json", checks)


validation = {
    "status": "AUDITED",
    "checks": {
        "descriptive_only": "Pass: 10,000 paired image bootstrap intervals added; no unsupported significance test.",
        "p_value_interpretation": "Not applicable: no p-values reported.",
        "confidence_intervals": "Pass: intervals describe paired image-macro metric deltas, not clinical uncertainty.",
        "multiple_comparisons": "Caution: 10 epochs, 12 joints and several metrics were inspected; no multiplicity-adjusted confirmatory claim.",
        "causal_language": "Pass: V2 is interpreted as an association under a controlled training change, not proof of surface causality.",
        "subgroup_interactions": "Caution: per-joint/visibility summaries are exploratory; no interaction tests.",
        "missing_data": "COCO v=0 joints are excluded; v=1 has only 44 observations and is reported separately.",
        "sample_size": "69 validation images/82 people; independence by person is unverified and COCO-source/pretraining overlap is possible.",
        "effect_size": "Legacy epoch5 NME relative change is reported; absolute deltas and tail counts retained.",
        "model_assumptions": "Metric code and aggregation were re-read; differing aggregation contracts are explicitly reconciled.",
        "conclusion_strength": "Bounded to reused source-domain 2D joint validation; no mesh/DMD37/medical claim.",
    },
}
dump(OUT / "STATISTICAL_VALIDATION_V1.json", validation)


material_passport = {
    "materials": [
        {"id": "sam3d_official_weights", "type": "restricted model checkpoint", "source": "Hugging Face facebook/sam-3d-body-vith", "location": checks["official"]["server_path"], "share_status": "hash/path only"},
        {"id": "v2_checkpoints", "type": "derived head checkpoints", "source": "V2 training", "location": "/raid5/xuhd/nlf_pilot_20260908/visible_ab_v2", "share_status": "hash/path only"},
        {"id": "coco2014", "type": "public image/annotation dataset", "source": "COCO 2014 with per-image license metadata", "location": "AI感知模块/outputs/内部工程证据/2026-09-08_COCO2014_DATASET", "share_status": "metadata/results only in handoff"},
        {"id": "target_sparse_refs", "type": "assistant engineering annotations", "source": "original public RGB images", "location": "AI感知模块/outputs/内部工程证据/2026-09-08_TARGET_DATA_V1", "share_status": "already in repository; not blinded truth"},
        {"id": "user_video_frames", "type": "project-local real RGB frames", "source": "workspace videos", "location": "docs/handoffs/real-scene-2026-09-06/input", "share_status": "existing repository handoff; no subject identity claim"},
    ]
}
dump(OUT / "MATERIAL_PASSPORT.json", material_passport)


def svg_line_chart(path: Path):
    width, height, margin = 900, 500, 70
    xs = list(range(11))
    nmes = [training_report["baseline"]["nme"]] + [r["validation"]["nme"] for r in training_report["history"]]
    pcks = [training_report["baseline"]["pck05"]] + [r["validation"]["pck05"] for r in training_report["history"]]
    def poly(values, low, high):
        return " ".join(f"{margin + i*(width-2*margin)/10:.1f},{height-margin-(v-low)/(high-low)*(height-2*margin):.1f}" for i,v in enumerate(values))
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="#101820"/>']
    body += [f'<text x="{margin}" y="35" fill="white" font-family="Arial" font-size="22">Visible A/B V2: original validation contract</text>', f'<text x="{margin}" y="58" fill="#aab7c4" font-family="Arial" font-size="13">Epoch 0 = official; lower NME / higher PCK05 is better</text>']
    for i in range(11):
        x = margin + i*(width-2*margin)/10
        body.append(f'<line x1="{x}" y1="{margin}" x2="{x}" y2="{height-margin}" stroke="#263746" stroke-width="1"/>')
        body.append(f'<text x="{x}" y="{height-35}" text-anchor="middle" fill="#c5d0da" font-family="Arial" font-size="12">{i}</text>')
    body.append(f'<polyline points="{poly(nmes,0.034,0.0355)}" fill="none" stroke="#25c2a0" stroke-width="4"/>')
    body.append(f'<polyline points="{poly(pcks,0.785,0.815)}" fill="none" stroke="#ffb347" stroke-width="4"/>')
    body.append(f'<text x="{width-260}" y="95" fill="#25c2a0" font-family="Arial" font-size="15">NME (own axis 0.034-0.0355)</text>')
    body.append(f'<text x="{width-260}" y="120" fill="#ffb347" font-family="Arial" font-size="15">PCK05 (own axis 0.785-0.815)</text>')
    body.append('</svg>')
    path.write_text("\n".join(body), encoding="utf-8")


def svg_joint_chart(path: Path):
    width, height, margin = 1000, 620, 110
    labels = [row["joint"].replace("left_", "L ").replace("right_", "R ") for row in per_joint]
    vals5 = [row["relative_nme_change_percent"]["epoch5_vs_official"] for row in per_joint]
    vals10 = [row["relative_nme_change_percent"]["epoch10_vs_official"] for row in per_joint]
    scale = 28
    zero = 390
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="#101820"/>', '<text x="60" y="38" fill="white" font-family="Arial" font-size="22">Per-joint NME change vs official (%)</text>', '<text x="60" y="62" fill="#aab7c4" font-family="Arial" font-size="13">Negative is improvement; exploratory validation analysis</text>']
    body.append(f'<line x1="{zero}" y1="85" x2="{zero}" y2="585" stroke="#d9e2e9"/>')
    for i,(label,v5,v10) in enumerate(zip(labels, vals5, vals10)):
        y=100+i*40
        body.append(f'<text x="{margin-12}" y="{y+13}" text-anchor="end" fill="#d9e2e9" font-family="Arial" font-size="13">{label}</text>')
        for v,dy,color in ((v5,0,"#25c2a0"),(v10,16,"#ffb347")):
            x2=zero+v*scale
            body.append(f'<line x1="{zero}" y1="{y+dy}" x2="{x2}" y2="{y+dy}" stroke="{color}" stroke-width="8"/>')
            body.append(f'<text x="{x2 + (6 if v>=0 else -6)}" y="{y+dy+4}" text-anchor="{("start" if v>=0 else "end")}" fill="{color}" font-family="Arial" font-size="11">{v:.1f}</text>')
    body.append('<text x="760" y="100" fill="#25c2a0" font-family="Arial" font-size="14">epoch5</text><text x="760" y="122" fill="#ffb347" font-family="Arial" font-size="14">epoch10</text></svg>')
    path.write_text("\n".join(body), encoding="utf-8")


svg_line_chart(VIS / "v2_epochs.svg")
svg_joint_chart(VIS / "v2_joint_deltas.svg")

manifest = []
for path in sorted(OUT.rglob("*")):
    if path.is_file() and path.name != "FILES_MANIFEST.json":
        manifest.append({
            "path": path.relative_to(OUT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
dump(OUT / "FILES_MANIFEST.json", {"files": manifest, "count": len(manifest)})
print(OUT)
