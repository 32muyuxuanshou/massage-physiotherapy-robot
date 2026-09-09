"""Build the MHR back-surface fitability gate data audit and handoff."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs/handoffs/real-scene-2026-09-09/mhr-back-surface-fitability-gate-v1"
CODE = OUT / "code"
OUT.mkdir(parents=True, exist_ok=True)
CODE.mkdir(exist_ok=True)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


evidence = ROOT / "AI感知模块/outputs/内部工程证据"
video_root = evidence / "2026-09-06_REAL_VIDEO_FRAME_PILOT_V1"
source_videos = read_json(video_root / "source_videos.json")["sources"]
selected = read_json(video_root / "selected_manifest.json")["images"]

flags = {
    "S01": {"VISIBLE_BARE_BACK": "PRESENT", "ROBOT_OCCLUDED": "ABSENT", "CLOTHED": "UNKNOWN", "BED": "PRESENT", "HAIR": "UNKNOWN", "SELF_OCCLUDED": "PARTIAL", "UNKNOWN": "PRESENT"},
    "S02": {"VISIBLE_BARE_BACK": "PARTIAL", "ROBOT_OCCLUDED": "ABSENT", "CLOTHED": "UNKNOWN", "BED": "PRESENT", "HAIR": "UNKNOWN", "SELF_OCCLUDED": "PRESENT", "UNKNOWN": "PRESENT"},
    "S03": {"VISIBLE_BARE_BACK": "PARTIAL", "ROBOT_OCCLUDED": "PRESENT", "CLOTHED": "UNKNOWN", "BED": "PRESENT", "HAIR": "UNKNOWN", "SELF_OCCLUDED": "PARTIAL", "UNKNOWN": "PRESENT"},
    "S04": {"VISIBLE_BARE_BACK": "PARTIAL", "ROBOT_OCCLUDED": "UNKNOWN", "CLOTHED": "UNKNOWN", "BED": "PRESENT", "HAIR": "UNKNOWN", "SELF_OCCLUDED": "PRESENT", "UNKNOWN": "PRESENT"},
    "S05": {"VISIBLE_BARE_BACK": "PARTIAL", "ROBOT_OCCLUDED": "PRESENT", "CLOTHED": "PARTIAL", "BED": "PRESENT", "HAIR": "PARTIAL", "SELF_OCCLUDED": "PARTIAL", "UNKNOWN": "PRESENT"},
    "S06": {"VISIBLE_BARE_BACK": "PARTIAL", "ROBOT_OCCLUDED": "PRESENT", "CLOTHED": "UNKNOWN", "BED": "PRESENT", "HAIR": "UNKNOWN", "SELF_OCCLUDED": "PARTIAL", "UNKNOWN": "PRESENT"},
    "S07": {"VISIBLE_BARE_BACK": "LIMITED", "ROBOT_OCCLUDED": "PRESENT", "CLOTHED": "UNKNOWN", "BED": "PRESENT", "HAIR": "UNKNOWN", "SELF_OCCLUDED": "UNKNOWN", "UNKNOWN": "PRESENT"},
    "S08": {"VISIBLE_BARE_BACK": "LIMITED", "ROBOT_OCCLUDED": "PRESENT", "CLOTHED": "UNKNOWN", "BED": "PRESENT", "HAIR": "UNKNOWN", "SELF_OCCLUDED": "UNKNOWN", "UNKNOWN": "PRESENT"},
}

rows = []
for frame in selected:
    rows.append({
        "subject_id": None,
        "subject_identity_status": "UNVERIFIED_DO_NOT_COUNT_AS_DISTINCT_SUBJECT",
        "session_id": frame["video_id"],
        "frame_id": frame["selection_id"],
        "frame_index": frame["frame_index"],
        "timestamp_s": frame["decoder_timestamp_s"],
        "rgb": {"exists": True, "width": frame["width"], "height": frame["height"], "sha256": frame["sha256"]},
        "depth": {"exists": False, "unit": None, "path": None},
        "registration": {"rgb_depth_registered": False, "evidence": None},
        "rgb_intrinsics": {"fx": None, "fy": None, "cx": None, "cy": None, "distortion": None},
        "depth_intrinsics": {"fx": None, "fy": None, "cx": None, "cy": None, "distortion": None},
        "rgb_to_depth_extrinsics": None,
        "visual_flags": flags[frame["selection_id"]],
        "review_note": frame["review_note"],
        "eligible_for_surface_fitting": False,
        "ineligibility": ["NO_DEPTH", "NO_CALIBRATION", "NO_RGB_DEPTH_REGISTRATION", "NO_INDEPENDENT_3D_SURFACE_OBSERVATION"],
    })

depth_like = []
sensor_containers = []
for path in (ROOT / "AI感知模块/outputs").rglob("*"):
    if not path.is_file():
        continue
    if any(token in path.name.lower() for token in ("depth", "rgbd", "pointcloud", "point_cloud")):
        depth_like.append(path)
    if path.suffix.lower() in {".bag", ".oni", ".pcd", ".ply", ".exr", ".mkv", ".sens", ".las", ".laz"}:
        sensor_containers.append(path)

audit = {
    "status": "NO_ELIGIBLE_REAL_3D_SURFACE_OBSERVATION",
    "audit_date": "2026-09-09",
    "research_question": "Can the frozen MHR representation fit prone backs when given reliable independent real geometry?",
    "workspace_sources": source_videos,
    "selected_rgb_frames": rows,
    "summary": {
        "rgb_videos": 2,
        "selected_rgb_frames": len(rows),
        "verified_unique_subjects": 0,
        "real_depth_frames": 0,
        "registered_rgb_depth_pairs": 0,
        "calibrated_real_cameras": 0,
        "qualified_visible_bare_back_surface_observations": 0,
        "multi_view_reconstructions": 0,
        "eligible_fit_subjects": 0,
        "eligible_held_out_geometry_subjects": 0,
    },
    "filesystem_scan": {
        "root": "AI感知模块/outputs",
        "depth_or_rgbd_named_files": len(depth_like),
        "sensor_container_files": len(sensor_containers),
        "sensor_container_extensions": {ext: sum(p.suffix.lower() == ext for p in sensor_containers) for ext in sorted({p.suffix.lower() for p in sensor_containers})},
        "real_sensor_bundle_found": False,
        "interpretation": "The located depth products are Blender/SKEL synthetic renders and derived experiment outputs. The 53 EXR containers are under BlenderMCP workstreams. No real RGB-D bag/ONI/PCD/calibration bundle was found.",
    },
    "contract": {
        "scene_depth_is_skin_depth": False,
        "valid_surface_loss_requires": ["registered real depth or independently reconstructed multi-view geometry", "visible bare-back semantic mask", "known metric unit", "camera calibration", "robot/clothes/bed/hair/occlusion excluded", "fit/evaluation observation separation"],
        "monocular_sam_or_mhr_depth_allowed_as_truth": False,
        "synthetic_blender_depth_allowed_for_this_gate": False,
    },
    "sources_checked": [
        "docs/handoffs/real-scene-2026-09-06/evidence/input_manifest.json",
        "AI感知模块/outputs/内部工程证据/2026-09-06_REAL_VIDEO_FRAME_PILOT_V1/source_videos.json",
        "AI感知模块/outputs/内部工程证据/2026-09-06_REAL_VIDEO_FRAME_PILOT_V1/selected_manifest.json",
        "AI感知模块/outputs/内部工程证据/2026-09-07_BACK_POSE_INVENTORY/README.md",
        "AI感知模块/outputs/BlenderMCP/workstreams",
    ],
}
write_json(OUT / "MHR_BACK_SURFACE_DATA_AUDIT_V1.json", audit)

parameter_audit = {
    "status": "CODE_AUDITED_NO_FITTING_EXECUTED",
    "sam3d_code_commit": "b5c765a0d89d789985e186d396315e7590887b94",
    "sources": ["sam_3d_body/models/heads/mhr_head.py", "sam_3d_body/models/heads/camera_head.py"],
    "mhr_raw_head_layout": {
        "total": 519,
        "global_rotation_6d": 6,
        "body_continuous": 260,
        "shape": 45,
        "scale_skeleton_basis": 28,
        "hands_left_right": 108,
        "face": 72,
        "face_behavior": "multiplied by zero in the current body forward path",
    },
    "mhr_forward_contract": {
        "body_pose": "continuous 260 is converted to model pose parameters; mhr_forward uses the first 130 body values",
        "shape": "45 coefficients",
        "scale": "28 coefficients mapped through scale_comps to 68 actual scale values",
        "global_body_translation": "feed-forward body head sets it to zero",
        "vertices": "18,439 vertices; MHR output divided by 100, then y/z signs flipped by the wrapper",
        "vertex_offsets_argument": "present in function signature but unused in this implementation",
    },
    "camera_contract": {
        "raw_dimension": 3,
        "raw_fields": ["s", "tx", "ty"],
        "conversion": "s plus bbox size and focal length determines tz; bbox/image/intrinsic center contributes x/y translation",
        "metric_camera_translation": "pred_cam_t with 3 values after perspective_projection",
    },
    "future_controlled_parameter_groups": {
        "camera_only": {"dimensions": 3, "variables": ["s", "tx", "ty"]},
        "pose_only": {"dimensions": 266, "variables": ["global_rotation_6d", "body_continuous_260"]},
        "identity_geometry_only": {"dimensions": 73, "variables": ["shape_45", "scale_skeleton_28"]},
        "combined": {"dimensions": 342, "variables": ["camera_3", "global_rotation_6d", "body_continuous_260", "shape_45", "scale_skeleton_28"]},
        "held_fixed": ["network weights", "hands_108", "face_72", "MHR assets"],
    },
    "multi_frame_sharing": {
        "representation_support": "A custom optimization loop can pass shared shape/scale tensors and per-frame pose/camera tensors through the batched differentiable MHR path.",
        "built_in_fitter": False,
        "limitation": "The estimator does not provide a ready per-subject shared-parameter fitting API; it must be implemented and validated after qualified data exist.",
    },
    "representation_limit_to_test": "The current parameterization has pose, identity shape and skeletal scale but no active local soft-tissue/contact vertex-offset term in this wrapper.",
}
write_json(OUT / "MHR_PARAMETER_INTERFACE_AUDIT_V1.json", parameter_audit)

protocol = {
    "status": "FROZEN_ACQUISITION_PROTOCOL_BEFORE_DATA",
    "gate_scope": "small representation-fitability gate, not the later 30-subject training dataset",
    "minimum": {"verified_subjects": 3, "preferred_subjects": 5, "capture_bundles_per_subject": 3, "qualified_rgb_depth_pairs": "9 minimum for 3 subjects"},
    "capture_bundles": [
        {"id": "A", "role": "FIT", "pose": "comfortable prone, neutral arms, clean exposed back, no robot"},
        {"id": "B", "role": "HELD_OUT_VIEW", "pose": "same maintained pose from a second calibrated view or synchronized second RGB-D camera"},
        {"id": "C", "role": "REPEATABILITY", "pose": "new comfortable prone placement with head/arm variation, no robot"},
    ],
    "calibration": {
        "rgb_intrinsics": ["fx", "fy", "cx", "cy", "distortion model and coefficients", "image size"],
        "depth_intrinsics": ["fx", "fy", "cx", "cy", "distortion model and coefficients", "depth size"],
        "extrinsics": "4x4 metric rigid transform between raw depth and RGB optical frames, with direction named explicitly",
        "depth_unit": "store raw scale and canonical meters; verify with measured planar targets at near/mid/far working distances",
        "registration_qa": ["save raw unregistered RGB/depth", "save registered depth", "report calibration reprojection RMS", "report planar depth median/P95 absolute error", "visually inspect discontinuities at a calibration target"],
        "initial_engineering_gates": {"calibration_reprojection_rms_px_max": 1.0, "registered_boundary_median_px_max": 2.0, "planar_depth_median_abs_mm_max": 5.0, "planar_depth_p95_abs_mm_max": 10.0},
    },
    "semantic_annotation": {
        "view": "original RGB and registered depth only; no SAM/MHR mesh overlay",
        "classes": ["VISIBLE_BARE_BACK", "OTHER_SKIN", "ROBOT_OCCLUDED", "CLOTHED", "BED", "HAIR", "SELF_OCCLUDED", "UNKNOWN", "BACKGROUND"],
        "surface_loss_allowed": ["VISIBLE_BARE_BACK with valid registered depth and acceptable local depth quality"],
        "surface_loss_forbidden": ["robot", "clothes", "bed", "hair", "unknown", "occlusion boundaries", "invalid/multipath/flying depth"],
        "quality": "two independent masks for held-out observations; adjudicate disagreements and retain UNKNOWN rather than guessing",
    },
    "fit_eval_independence": {
        "preferred": "fit bundle A; evaluate synchronized calibrated bundle B after applying known camera extrinsics",
        "secondary": "fit selected spatial tiles; evaluate disjoint upper/mid/lower and left/right tiles in the same registered frame",
        "secondary_claim_limit": "same-frame spatial holdout supports OPTIMIZATION_FEASIBILITY only",
        "never": "score the exact depth pixels used by the fitting loss as held-out improvement",
    },
    "future_execution": {
        "initializations": ["official SAM 3D Body", "V2 epoch5", "optional V2 epoch10"],
        "network_weights": "frozen",
        "development_subjects": "use at most 1-2 subjects for optimizer/loss-scale choices",
        "evaluation_subjects": "freeze parameters and thresholds before remaining subjects",
        "parameter_stages": ["camera only", "pose only", "shape/scale only", "combined with priors"],
        "surface_loss": "robust point-to-plane after coordinate/normal validation; point-to-point as diagnostic",
        "priors": ["initialization", "pose", "shape", "scale/skeleton", "camera drift"],
        "primary_metric": "held-out visible bare-back surface error in mm, subject-macro",
        "reports": ["mean", "median", "P90", "P95", "max", "per-region", "per-subject", "parameter before/after"],
        "dmd37": "method-to-method displacement only; never target error",
    },
    "gate_states": ["PASS_MHR_BACK_SURFACE_FITABILITY", "INCONCLUSIVE_OPTIMIZATION_OR_DATA_LIMITED", "FAIL_CURRENT_MHR_FITABILITY_HYPOTHESIS"],
}
write_json(OUT / "MHR_BACK_SURFACE_ACQUISITION_PROTOCOL_V1.json", protocol)

decision = {
    "gate_state": "INCONCLUSIVE_OPTIMIZATION_OR_DATA_LIMITED",
    "actual_fitting_executed": False,
    "global_finetuning_executed": False,
    "reason": "No registered/calibrated real RGB-D, qualified multi-view reconstruction, or other independent 3D visible-bare-back observation exists in the audited workspace.",
    "not_a_failure_of_mhr": "No representation test was run, so the evidence cannot distinguish MHR representation limits from SAM image-to-parameter prediction error.",
    "next_minimum_experiment": "Acquire three verified subjects with three calibrated RGB-D bundles each: fit view A, held-out view B, repeatability bundle C. Run staged camera/pose/shape-scale/combined per-image fitting with all network weights frozen.",
    "primary_blockers": ["data", "sensor calibration", "RGB-depth registration", "bare-back semantic validity", "independent held-out geometry"],
    "not_current_priorities": ["global finetuning", "LoRA", "more decoder unfreezing", "DMD37 training", "30-subject dataset", "medical labeling"],
    "claim_boundary": {"mesh_more_accurate": False, "dmd37_more_accurate": False, "medical_accuracy": False, "mhr_representation_failed": False},
}
write_json(OUT / "MHR_BACK_SURFACE_FITABILITY_DECISION_V1.json", decision)

template = {
    "status": "TEMPLATE",
    "subject_id": "SUBJECT_XXX",
    "session_id": "SESSION_YYYYMMDD_XXX",
    "consent_and_use_scope_recorded": False,
    "captures": [{
        "frame_id": "FRAME_XXX_A",
        "role": "FIT",
        "rgb_path": "relative/path/rgb.png",
        "depth_raw_path": "relative/path/depth_raw.png",
        "depth_registered_path": "relative/path/depth_registered.npy",
        "depth_raw_unit_scale_to_m": None,
        "rgb_intrinsics": {"width": None, "height": None, "fx": None, "fy": None, "cx": None, "cy": None, "distortion_model": None, "distortion_coefficients": []},
        "depth_intrinsics": {"width": None, "height": None, "fx": None, "fy": None, "cx": None, "cy": None, "distortion_model": None, "distortion_coefficients": []},
        "depth_to_rgb_extrinsics_4x4": None,
        "visible_bare_back_mask_path": "relative/path/visible_bare_back_mask.png",
        "semantic_mask_path": "relative/path/semantic_mask.png",
        "mesh_overlay_seen_during_annotation": False,
        "calibration_report_path": "relative/path/calibration_report.json",
        "quality": {"valid_depth_ratio_in_bare_back": None, "registration_boundary_median_px": None, "depth_median_abs_mm": None, "depth_p95_abs_mm": None},
    }],
}
write_json(OUT / "OBSERVATION_MANIFEST_TEMPLATE.json", template)

acq_md = """# MHR 背部 Fitability Gate：真实 RGB-D 采集协议 V1

本协议只服务 3–5 人的小型表示能力 Gate，不是正式 30 人训练集。当前两段视频只有 RGB，因此不能从中恢复独立毫米表面，也不能使用 SAM/MHR 自己的深度补齐。

## 最少采集

至少 3 位已核验匿名编号的真人，推荐 5 位。每人 3 个采集 bundle：A 为干净俯卧拟合视图；B 为同一保持姿态下的同步第二视角，专门作 held-out evaluation；C 为重新摆位后的重复性观测。最小为 9 对合格、注册的 RGB-D。先不放机械臂，背部尽量暴露，姿势舒适，允许自然头向和手臂位置变化。

## 标定与注册

保存 RGB/Depth 各自分辨率、`fx fy cx cy`、畸变模型与系数、Depth 到 RGB 的 4×4 米制外参以及原始 depth unit scale。保留 raw RGB、raw depth 和 registered depth，不只保存对齐结果。用覆盖实际工作距离的平面/标定板报告内参重投影 RMS、注册边界误差和深度绝对误差。首轮工程门为 RMS ≤1 px、注册边界中位数 ≤2 px、平面深度中位绝对误差 ≤5 mm、P95 ≤10 mm；不达标时修标定，不能靠放宽 surface 指标继续。

## 可进入 loss 的区域

标注者只能看原 RGB 和注册 Depth，不能看 SAM/MHR overlay。语义分为 `VISIBLE_BARE_BACK`、其它皮肤、机器人、衣物、床、头发、自遮挡、UNKNOWN 和背景。只有 `VISIBLE_BARE_BACK` 且局部深度有效、无飞点/多径/边缘混合的像素可以进入 surface loss。scene depth 不能整体当作 skin depth。

## 拟合和评价分离

优先用 A 视图 fitting、B 视图 evaluation，并用标定外参把预测表面变换到 B 相机。C 用于检查重新摆位后的重复性。若只有单相机同帧，只能把空间区域分成 FIT 与 HELD-OUT；这种结果最多叫 `OPTIMIZATION_FEASIBILITY`，不能判定 Gate PASS。任何用于 loss 的 depth pixel 都不得再次作为 held-out 成绩。

## 数据到位后的执行顺序

网络权重全部冻结，分别从 official、V2 epoch5、可选 epoch10 初始化。先在 1–2 个开发受试者上依次只优化 camera、只优化 pose、只优化 shape/scale，最后 combined；记录 loss/gradient scale 与参数漂移。固定优化器、先验、阈值后再打开其余受试者。主要指标为受试者宏平均的 held-out visible-back point-to-plane mm，并报告 median/P90/P95/max、上中下背与左右区域。DMD37 只报告方法间位移。

机器合同见 `MHR_BACK_SURFACE_ACQUISITION_PROTOCOL_V1.json`，填写模板见 `OBSERVATION_MANIFEST_TEMPLATE.json`。
"""
(OUT / "MHR_BACK_SURFACE_ACQUISITION_PROTOCOL_V1.md").write_text(acq_md, encoding="utf-8")

readme = """# MHR_BACK_SURFACE_FITABILITY_GATE_V1

更新日期：2026-09-09。最终 Gate 状态：**`INCONCLUSIVE_OPTIMIZATION_OR_DATA_LIMITED`**。本轮优先检查 MHR 表示能否在独立真实几何下拟合俯卧背部；审计发现当前没有合格真实 RGB-D/multi-view 表面观测，因此按停止条件没有运行 fitting，也没有 global finetuning。

## 研究问题、证据与判断

表示能力问题和预测问题已分开：SAM 可能预测错 MHR 参数，但 MHR 仍可能表达目标人体；也可能是俯卧软组织/床面接触超出当前参数化模型。只有给冻结的 MHR 独立几何，再看 held-out surface error，才能开始区分两者。

当前两段本地素材 V01/V02 是 RGB 宣传/演示视频。8 张精选帧包含真实俯卧背部和机器人遮挡案例，但没有 Depth、Depth 单位、RGB/Depth 注册、内参、畸变或外参。身份也未核验，不能把两段视频或相邻帧计成独立受试者。工作区中的 Depth/EXR 来自 Blender/SKEL 合成流程，不是真人传感器观测。

代码审计确认当前 MHR head 输出 519 维：全局旋转 6、body continuous 260、shape 45、scale/skeleton basis 28、双手 108、face 72；face 在当前 body forward 中被置零。camera head 是 3 维 `(s, tx, ty)`，再结合 bbox、焦距和内参转换成相机平移。当前 wrapper 的 `vertex_offsets` 参数没有实际使用，因此本 Gate 将来首先测试 pose/shape/skeletal scale 的表达，不假装已经具有局部接触形变自由度。

## README 要求的 15 个回答

1. **有真正独立 RGB-D/multi-view surface observation 吗？** 没有。
2. **observation 来自 visible bare back 吗？** RGB 中存在可见裸背区域，但没有对应真实 3D observation；因此没有合格 surface observation。
3. **RGB/Depth 可靠标定和注册了吗？** 没有 Depth，也没有标定或注册文件。
4. **Official SAM 的真实 surface 误差多少？** 无法计算；当前只有二维轮廓开发诊断。
5. **V2-E5 是否改善真实 surface？** 无法判断。V2-E5 只改善了当前 COCO 来源二维 joint validation。
6. **真实几何下 per-image/per-subject fitting 能否降低 held-out surface error？** 尚未执行，因为几何观测门未通过。
7. **改善来自 camera/pose/shape/skeleton/combined 哪项？** 没有合法实验结果。未来按四阶段受控诊断。
8. **有 parameter cheating 吗？** 本轮没有优化，因而没有新作弊；历史单图轮廓拟合已显示 camera 与 geometry 均能吸收二维误差，未来必须限制并报告漂移。
9. **Gate 是 PASS、INCONCLUSIVE 还是 FAIL？** `INCONCLUSIVE_OPTIMIZATION_OR_DATA_LIMITED`。
10. **是否值得现在采正式 30 人数据集？** 暂不启动。先用 3–5 人 Gate 判断表示与拟合链是否可行。
11. **下一个最小实验是什么？** 3 人、每人 A/B/C 三个标定 RGB-D bundle；A 拟合、B 独立视角评价、C 重复性。网络冻结，依次优化 camera、pose、shape/scale、combined。
12. **是否足以排除优化器和数据问题并判 FAIL？** 完全不足。当前没有进入优化。
13. **能说 Mesh 变准吗？** 不能。
14. **能说 DMD37 变准吗？** 不能；只能继续做绑定、传播和方法间差异。
15. **下一步最值得投入什么？** RGB-D 数据、标定与 fit/eval 独立性。没有它们，fitting、global finetuning、LoRA 和 MHR 表示扩展都缺少判断依据。

## 执行门与后续

采集协议固定在 [MHR_BACK_SURFACE_ACQUISITION_PROTOCOL_V1.md](MHR_BACK_SURFACE_ACQUISITION_PROTOCOL_V1.md)；机器可读版包含标定阈值、语义类别、held-out 设计和 Gate 执行顺序。数据审计见 [MHR_BACK_SURFACE_DATA_AUDIT_V1.json](MHR_BACK_SURFACE_DATA_AUDIT_V1.json)，参数接口见 [MHR_PARAMETER_INTERFACE_AUDIT_V1.json](MHR_PARAMETER_INTERFACE_AUDIT_V1.json)，停止决定见 [MHR_BACK_SURFACE_FITABILITY_DECISION_V1.json](MHR_BACK_SURFACE_FITABILITY_DECISION_V1.json)。

Gate PASS 前不启动 30 人训练集、不解冻 decoder、不上 LoRA。Gate 数据到位后，先完成 per-image/per-subject fitting；若多名受试者 held-out surface 一致改善且没有 camera/shape/scale 异常，再规划正式 target-domain dataset。

## Material Passport

本轮只读取两段本地 RGB 视频的既有抽帧清单、Blender 合成 RGB-D 资产索引和本地 SAM 3D Body 源码。没有复制原视频、真人帧、授权权重或合成数据进入新公开目录；Git 只包含审计结论、采集合同和代码接口说明。DMD37 未参与评价，`medical_truth=false`。
"""
(OUT / "README.md").write_text(readme, encoding="utf-8")

for script_name in ("build_gate_delivery.py", "validate_observation_manifest.py"):
    script_path = Path(__file__).parent / script_name
    shutil.copy2(script_path, CODE / script_name)

manifest = []
for path in sorted(OUT.rglob("*")):
    if path.is_file() and path.name != "FILES_MANIFEST.json":
        manifest.append({"path": path.relative_to(OUT).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
write_json(OUT / "FILES_MANIFEST.json", {"count": len(manifest), "files": manifest})
print(OUT)
