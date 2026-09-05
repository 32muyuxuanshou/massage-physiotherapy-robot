"""Freeze a passed engineering dataset after explicit visual-review evidence."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime

import build_qc_dataset_30 as d
b=d.b


def main(root):
    root=root.resolve()
    if b.AI_ROOT.resolve() not in root.parents:
        raise ValueError("Not a project delivery")
    report=b.read_json(root/"dataset_qc_report.json")
    index=b.read_json(root/"dataset_index.json")
    visual=b.read_json(root/"visual_review.json")
    if not report["automatic_passed"] or report["sample_count"]!=30:
        raise ValueError("Automatic QC has not passed")
    if not visual["approved"] or set(visual["reviewed_samples"]) != {r["sample_id"] for r in index}:
        raise ValueError("All 30 overlays must be reviewed")
    if b.read_json(root/"source_hashes.json") != d.source_hashes():
        raise ValueError("Sources changed")
    if b.sha256(root/d.ATLAS.name)!=b.read_json(d.CONFIG)["atlas_sha256"]:
        raise ValueError("Atlas copy changed")
    edge_count=0
    edge_max=0.
    raster_counts=[]
    rgb_hashes=[]
    summaries=[]
    for entry in index:
        sid=entry["sample_id"]
        sample=root/"samples"/sid
        if b.sha256(root/entry["snapshot"])!=entry["snapshot_sha256"]:
            raise ValueError("Snapshot changed")
        for name in ("rgb.png","scene_depth_z.npy","depth_valid_mask.png","skin_mask.png","labels.json","render_metadata.json","overlay.png"):
            if not (sample/name).is_file():
                raise ValueError("Missing sample component")
        strict=b.read_json(root/"qc_reports"/(sid+"_strict.json"))
        independent=b.read_json(root/"qc_reports"/(sid+"_independent.json"))
        edge=b.read_json(root/"qc_reports"/(sid+"_silhouette_edges.json"))
        if not strict["passed"] or not independent["passed"] or edge["mismatch_count"]:
            raise ValueError("Failed stored QC")
        if not d.strict_qc(sample,b.read_json(root/d.ATLAS.name),b.read_json(root/entry["profile"]),b.read_json(d.CONFIG))["passed"]:
            raise ValueError("Final strict QC differs")
        meta=b.read_json(sample/"render_metadata.json")
        if meta["depth"]["backend"]!="SCENE_RAY_CAST_PIXEL_CENTER" or not meta["alignment"]["rgb_and_scene_z_same_camera_frame_geometry"]:
            raise ValueError("Wrong buffer backend")
        edge_count+=edge["pixel_count"]
        edge_max=max(edge_max,edge["max_depth_error_m"])
        raster_counts.append(meta["raster_diagnostic"]["skin_ownership_disagreement_pixels"])
        rgb_hashes.append(b.sha256(sample/"rgb.png"))
        summaries.append(independent["summary"])
    if len(set(rgb_hashes))!=30:
        raise ValueError("Duplicate RGB samples")
    protected=[]
    for asset in b.read_json(b.PROTECTED)["files"]:
        actual=b.sha256(Path(asset["path"]))
        if actual != asset["sha256"]:
            raise ValueError("Protected asset changed: "+asset["name"])
        protected.append({"name":asset["name"],"sha256":actual,"unchanged":True})
    tests=subprocess.run([str(b.PYTHON),"-m","unittest","discover","-s","tests","-v"],cwd=b.TOOL_ROOT,capture_output=True,text=True)
    if tests.returncode:
        raise RuntimeError(tests.stdout+tests.stderr)
    evidence=root/"repair_evidence"
    evidence.mkdir(exist_ok=True)
    diag=b.AI_ROOT/"outputs"/"BlenderMCP"/"workstreams"/"qc_dataset_30"
    for folder,name,destination in (
        ("pixel_sampling_diagnostic_1","diagnostic.json","raster_sampling_diagnostic.json"),
        ("center_sampling_regression","edges.json","single_sample_raster_edges.json"),
        ("ray_depth_regression","edges.json","ray_depth_edges.json"),
        ("ray_depth_regression","analytic_depth.json","analytic_depth.json"),
        ("ray_depth_regression","verification.json","ray_depth_independent.json")):
        shutil.copy2(diag/folder/name,evidence/destination)
    (evidence/"unit_tests.txt").write_text(tests.stdout+tests.stderr,encoding="utf-8")
    shutil.copy2(diag/"elbow_candidate_22.0_20-10-11"/"candidate_report.json",evidence/"elbow_22_candidate_selection.json")
    shutil.copy2(diag/"intrinsics_precision_diagnostic.json",evidence/"intrinsics_precision_diagnostic.json")
    implementation=root/"implementation_snapshot"
    for name in b.read_json(root/"source_hashes.json"):
        source=Path(name)
        if source.suffix == ".py" and b.TOOL_ROOT.parent in source.parents:
            destination=implementation/source.relative_to(b.TOOL_ROOT.parent)
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination)
    for source in (Path(__file__),d.WS/"test_analytic_depth.py",b.TOOL_ROOT/"tests"/"test_qc_dataset_30.py"):
        dest=implementation/source.relative_to(b.TOOL_ROOT.parent)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)
    report.update({"passed":True,"status":"PASSED_ENGINEERING_QC_NOT_MEDICAL_DATASET",
        "finalized_at":datetime.now().isoformat(timespec="seconds"),"visual_review":"APPROVED_WITH_RECORDED_LIMITATIONS",
        "source_hashes_unchanged":True,"protected_assets":protected,
        "total_point_instances":600,"unique_rgb_count":30,"independent_summaries":summaries,
        "dense_silhouette_pixel_count":edge_count,"dense_silhouette_mismatch_count":0,"dense_silhouette_max_depth_error_m":edge_max,
        "rgb_raster_vs_ray_skin_disagreements_per_image":{"min":min(raster_counts),"max":max(raster_counts),"counts":raster_counts},
        "medical_truth":False,"network_training_performed":False,
        "rgb_quality":"ENGINEERING_ONLY_SINGLE_SAMPLE_SHADOW_DITHER",
        "photorealistic_or_clinical_training_ready":False})
    b.write_json(root/"dataset_qc_report.json",report)
    b.write_json(root/"verification.json",report)
    (root/"README.md").write_text(f"""# SKEL 背部 20 工程点：30 样本质检集

结果：30/30 工程 QC 通过；**不是医学穴位数据集，尚未训练网络**。

## 查看结果

- `overlay_montage_30.png`：30 张标点总览；`overlay_montage_S0/S1/S2.png` 为分体型总览。
- `samples/sample_000001` 至 `sample_000030`：RGB、camera-Z Depth、Valid Mask、Skin Mask、labels、render_metadata、overlay。
- `dataset_index.json`：样本与 Shape/Pose/Camera 的对应关系；`dataset_config_v1.json` 冻结本轮配置。
- `dataset_qc_report.json` / `verification.json`：最终结论；逐样本数值与独立检查在 `qc_reports/`。
- `snapshots/`：每个样本的可重放 Blend（含授权 SKEL，仅限内部使用）；`profiles/` 记录原生 betas 与 pose。
- `repair_evidence/` 记录本轮发现并修复的采样问题；`implementation_snapshot/` 为代码快照，不是可单独安装的运行环境。

## 固定输入与验收

SKEL 女性，6,890 顶点、13,776 三角面。`ENG_BACK_20_V1` 的 E01–E20 只用于工程试验，绑定和左右语义未更换。3 个已单独验证的 Shape × 5 个温和 Pose × 2 个合成针孔相机；1280×1024；床面与刚体俯卧变换固定，没有逐姿态调平。

600 个点实例全部保留原三角面和重心坐标，并可见。相邻像素取样的最大 Z 差 **{report['max_depth_error_m']*1000:.4f} mm**，反投影误差 **{report['max_backprojection_error_m']*1000:.4f} mm**，均小于冻结的 3 mm 阈值。这里用包含连续 UV 的光栅像素深度，不把像素量化误差当成连续点严格恒等式。

每张图均重新打开 Blender 做独立几何/投影/射线检查；3 个代表样本另外精确重导出。完整皮肤轮廓边缘共检查 **{edge_count:,} 个像素**，0 个深度/归属不符，最大边缘深度差 {edge_max*1000:.6f} mm。另有 16,384 像素已知平面/遮挡解析测试通过、13 项 Python 测试通过。外部遮挡未混入本轮 30 张全可见样本，独立报告的相应 SKIP 不代表已经测试。

## 深度与像素约定

`scene_depth_z.npy` 为 float32 米，像素中心场景射线首个可见表面的 OpenCV Zc，未命中为 0。两个 Mask 为 uint8 0/255。坐标为 +X 右/+Y 下/+Z 前；连续像素原点在图像左上边缘，数组 `[row,col]` 的中心是 `(col+0.5,row+0.5)`。相机内参、外参及原生姿态/体型在 labels 中。

本轮修正了默认 Eevee 多采样 Z Pass 的亚像素问题：几何缓冲改为 `CENTER_RAY_DEPTH_V2`；RGB 仍用相同相机、帧和几何的单采样光栅渲染，**不声称 RGB 和深度来自同一次渲染**。GPU 覆盖与射线归属在每张图 {min(raster_counts)}–{max(raster_counts)} 个轮廓像素存在差异，已逐图记录。它们不是点标签错误，也不表示逐 RGB 像素表面归属严格一致。真实相机畸变、噪声、软组织/床面接触均未模拟。

目视检查发现 RGB 的单采样阴影有明显颗粒/抖动噪点；这是渲染采样噪点，不是已标定的真实 RGB-D 噪声。该质量仅接受用于工程链路/过拟合试验，未通过照片真实感质量验收。若进入有泛化目标的训练，应在保留中心射线几何缓冲的前提下，另行提升 RGB 阴影采样质量并复验；不能把本批噪点当作真实传感器噪声模型。

## 使用边界

以后训练应读 `rgb.png` 和 `labels.json`，不能把带绿色点/文字的 `overlay.png` 当输入，避免标签泄漏。本轮尚未切分训练/验证集；近似重复姿态与同体型样本不能随机拆分后据此宣称泛化。

本次未改医生 UI、正式 Atlas、canonical 模板或正式 ZIP，也未保存或关闭用户当前 Blender 场景。旧目录 `2026-08-28_19-41-29`、`2026-08-28_19-48-01`、`2026-08-28_20-02-00`、`2026-08-28_20-12-28` 为失败/诊断或旧检查器记录，不是最终交付。双肘 20 度的旧候选有一个点像素取样误差 3.127 mm，因此收紧至 22 度；未提高阈值。另修正密集轮廓检查器：使用样本声明的高精度 K 发射线，并独立核对 Blender float32 投影矩阵，避免反算精度改变边界命中。场景与参数经哈希检查复用预检，本目录的样本全部重新导出/验收。

配置经过验收筛选，只证明这些离散组合，不证明连续姿态/体型空间或训练泛化。下一步可在用户确认后做工程点过拟合训练；正式医学数据仍需医生试标和传播复核。

`SHA256SUMS.txt` 覆盖本目录文件（自身除外）。
""",encoding="utf-8")
    pending=root/"NOT_RELEASED.json"
    if pending.exists():
        pending.rename(root/"PREFLIGHT_STATUS_SUPERSEDED.json")
    b.manifest(root)
    manifest_ok=True
    for line in (root/"SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest,rel=line.split("  ",1)
        manifest_ok &= b.sha256(root/rel)==digest
    if not manifest_ok:
        raise RuntimeError("Final manifest verification failed")
    print(json.dumps({"passed":True,"root":str(root),"samples":30,"point_instances":600,"manifest_verified":True},ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("root",type=Path)
    main(parser.parse_args().root)
