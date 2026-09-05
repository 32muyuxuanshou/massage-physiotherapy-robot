#!/usr/bin/env python3
"""Run the frozen natural-prone scene across each SKEL beta at +/-0.5."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


AI_ROOT = Path(r"E:\项目-按摩理疗机器人\AI感知模块")
TOOL_ROOT = AI_ROOT / "标注工具" / "blender_mcp"
WS = Path(__file__).resolve().parent
NATURAL_WS = TOOL_ROOT / "workstreams" / "natural_prone_pose"
PRONE_WS = TOOL_ROOT / "workstreams" / "prone_rgbd"
WORKBENCH = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_完整版" / "医生穴位标注工作台_v2.3.0_完整版"
BLENDER = WORKBENCH / "runtime" / "blender" / "blender.exe"
PYTHON = TOOL_ROOT / ".venv" / "Scripts" / "python.exe"
CANONICAL = AI_ROOT / "模型资源" / "SKEL与SMPL-X独立模型包_v2.3.0_内部授权_禁止外发" / "templates" / "SKEL" / "SKEL_FEMALE_TRUNK_LIMB_v2.3.blend"
FORMAL_ATLAS = WORKBENCH / "workspace" / "导出结果" / "20260824_173250_skel_female_1_1" / "20260824_173250_skel_female_1_1_正式标注_最新.json"
OFFICIAL_ZIP = AI_ROOT / "发布" / "医生穴位标注工作台_v2.3.0_正式完整版.zip"
PROFILE_BASE = NATURAL_WS / "natural_prone_pose_profile.json"
FIXTURE = PRONE_WS / "prone_engineering_fixture.json"
CONTRACT = NATURAL_WS / "fixed_scene_contract.json"
GENERATE = NATURAL_WS / "generate_native_pose.py"
PREPARE = PRONE_WS / "prepare_prone_scene.py"
PROBE = NATURAL_WS / "probe_pose_snapshot.py"
RENDER = NATURAL_WS / "render_preview.py"
EXPECTED_TOPOLOGY = "dc8b3f270680f4a66d1010713a49d771850ddb0850f9151d74cb10bbc90b7733"
DORSAL = {"ENG_BACK_C7", "ENG_BACK_SCAPULA_L", "ENG_BACK_SCAPULA_R", "ENG_BACK_THORACIC_L", "ENG_BACK_THORACIC_R", "ENG_BACK_LUMBAR"}
VENTRAL = {"ENG_FRONT_CHEST", "ENG_FRONT_ABDOMEN"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(command: list[str], *, env=None, sentinel=None, timeout=900) -> str:
    result = subprocess.run(command, cwd=str(TOOL_ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    combined = result.stdout + "\n" + result.stderr
    if result.returncode != 0 or (sentinel and sentinel not in combined):
        raise RuntimeError(combined[-10000:])
    return combined


def environment() -> dict[str, str]:
    value = os.environ.copy()
    value.update({"BLENDER_USER_RESOURCES": str(WORKBENCH / "user_resources"), "ACUPOINT_MCP_PROJECT_ROOT": str(AI_ROOT), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    return value


def make_profile(base: dict, beta_index: int | None, beta_value: float) -> dict:
    profile = json.loads(json.dumps(base))
    betas = [0.0] * 10
    if beta_index is not None:
        betas[beta_index] = beta_value
    profile.update({
        "schema": "skel-native-prone-shape-smoke-profile-v1",
        "profile_id": "shape-zero" if beta_index is None else f"beta-{beta_index + 1:02d}-{beta_value:+.1f}",
        "medical_truth": False,
        "betas": betas,
        "shape_test": {"beta_index_zero_based": beta_index, "value": beta_value},
    })
    return profile


def vector_delta(left, right) -> float:
    return max((math.dist(a, b) for a, b in zip(left, right)), default=0.0)


def point_map(probe: dict) -> dict:
    return {item["point_id"]: item for item in probe["points"]}


def analyse_case(name: str, baseline: dict, candidate: dict, fixture: dict) -> dict:
    bindings = {item["point_id"]: item for item in fixture["anchors"]}
    candidate_points = point_map(candidate)
    binding_ok = set(candidate_points) == set(bindings)
    for point_id, point in candidate_points.items():
        frozen = bindings[point_id]
        binding_ok = binding_ok and point["face_index"] == frozen["face_index"] and point["vertex_indices"] == frozen["vertex_indices"]
        binding_ok = binding_ok and max(abs(float(a) - float(b)) for a, b in zip(point["barycentric"], frozen["barycentric"])) <= 1e-12
    topology_ok = candidate["model"]["vertex_count"] == 6890 and candidate["model"]["polygon_count"] == 13776 and candidate["model"]["topology_signature_sha256"] == EXPECTED_TOPOLOGY
    contract_ok = candidate["camera"] == baseline["camera"] and candidate["bed"] == baseline["bed"] and candidate["model"]["target_matrix_world"] == baseline["model"]["target_matrix_world"]
    finite_ok = all(math.isfinite(float(value)) for vertex in candidate["world_vertices_m"] for value in vertex)
    dorsal_visible = all(candidate_points[point_id]["visible"] for point_id in DORSAL)
    ventral_hidden = all(not candidate_points[point_id]["visible"] for point_id in VENTRAL)
    bed_top = float(candidate["bed"]["top_z_m"])
    clearance = float(candidate["bounds_world_m"]["min"][2]) - bed_top
    extents_base = [baseline["bounds_world_m"]["max"][axis] - baseline["bounds_world_m"]["min"][axis] for axis in range(3)]
    extents_case = [candidate["bounds_world_m"]["max"][axis] - candidate["bounds_world_m"]["min"][axis] for axis in range(3)]
    ratios = [case / base for case, base in zip(extents_case, extents_base)]
    mesh_delta = vector_delta(baseline["world_vertices_m"], candidate["world_vertices_m"])
    anchor_deltas = {point_id: math.dist(point_map(baseline)[point_id]["xyz_world_m"], candidate_points[point_id]["xyz_world_m"]) for point_id in sorted(candidate_points)}
    checks = {
        "topology_stable": topology_ok,
        "frozen_bindings": binding_ok,
        "same_scene_contract": contract_ok,
        "finite_geometry": finite_ok,
        "shape_changes_mesh": mesh_delta >= 1e-5,
        "dorsal_visible": dorsal_visible,
        "ventral_hidden": ventral_hidden,
        "bed_clearance_range": -0.005 <= clearance <= 0.03,
        "coarse_extent_sanity": all(0.80 <= ratio <= 1.20 for ratio in ratios),
    }
    return {
        "case": name,
        "betas": candidate.get("betas", []),
        "passed_automatic_gate": all(checks.values()),
        "visual_review_required": True,
        "checks": checks,
        "metrics": {
            "body_clearance_m": clearance,
            "max_mesh_delta_m": mesh_delta,
            "extent_ratios_xyz": ratios,
            "anchor_delta_m": anchor_deltas,
        },
    }


def make_montage(previews: list[tuple[str, Path]], output: Path) -> None:
    thumb_size = (320, 256)
    cell_h = 286
    columns = 4
    rows = math.ceil(len(previews) / columns)
    canvas = Image.new("RGB", (columns * thumb_size[0], rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, (label, path) in enumerate(previews):
        with Image.open(path) as source:
            image = source.convert("RGB").resize(thumb_size, Image.Resampling.LANCZOS)
        x = (index % columns) * thumb_size[0]
        y = (index // columns) * cell_h
        canvas.paste(image, (x, y + 24))
        draw.text((x + 8, y + 7), label, fill="black", font=font)
    canvas.save(output)


def manifest(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    required = [CANONICAL, FORMAL_ATLAS, OFFICIAL_ZIP, PROFILE_BASE, FIXTURE, CONTRACT, GENERATE, PREPARE, PROBE, RENDER, BLENDER, PYTHON]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    output = AI_ROOT / "outputs" / "BlenderMCP" / "workstreams" / "prone_shape_regression" / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_shape_smoke")
    output.mkdir(parents=True, exist_ok=False)
    temp_root = AI_ROOT / "outputs" / "BlenderMCP" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp = temp_root / f"shape_smoke_{uuid.uuid4().hex}"
    temp.mkdir()
    protected = {"canonical_skel": CANONICAL, "formal_atlas": FORMAL_ATLAS, "official_zip": OFFICIAL_ZIP}
    before = {key: sha256(path) for key, path in protected.items()}
    fixture = read_json(FIXTURE)
    base = read_json(PROFILE_BASE)
    cases = [("A_BASE", None, 0.0)] + [(f"B{index + 1:02d}_{suffix}", index, value) for index in range(10) for suffix, value in (("NEG", -0.5), ("POS", 0.5))] + [("R_BASE", None, 0.0)]
    probes = {}
    previews = []
    for name, beta_index, beta_value in cases:
        case_dir = output / "cases" / name
        case_dir.mkdir(parents=True)
        profile_path = case_dir / "profile.json"
        write_json(profile_path, make_profile(base, beta_index, beta_value))
        native = temp / f"native_{name}"
        run([str(PYTHON), str(GENERATE), "--profile", str(profile_path), "--output", str(native)])
        snapshot = temp / f"{name}.blend"
        prepare_result = case_dir / "prepare.json"
        run([str(BLENDER), "--background", str(CANONICAL), "--python", str(PREPARE), "--", "--snapshot", str(snapshot), "--result", str(prepare_result), "--native-pose-dir", str(native), "--pose-profile", str(profile_path), "--fixed-scene-contract", str(CONTRACT), "--width", "640", "--height", "512"], env=environment(), sentinel="ACU_PREPARE_PRONE_SCENE=PASS")
        probe_path = case_dir / "probe.json"
        run([str(BLENDER), "--background", str(snapshot), "--python", str(PROBE), "--", "--fixture", str(FIXTURE), "--output", str(probe_path), "--width", "1280", "--height", "1024"], env=environment(), sentinel="ACU_POSE_SNAPSHOT_PROBE=PASS")
        preview_path = case_dir / "preview.png"
        run([str(BLENDER), "--background", str(snapshot), "--python", str(RENDER), "--", str(preview_path)], env=environment(), sentinel="ACU_NATURAL_PRONE_PREVIEW=PASS")
        probes[name] = read_json(probe_path)
        previews.append((name, preview_path))
    baseline, restored = probes["A_BASE"], probes["R_BASE"]
    restoration = {
        "max_mesh_error_m": vector_delta(baseline["world_vertices_m"], restored["world_vertices_m"]),
        "max_anchor_xyz_error_m": max(math.dist(a["xyz_world_m"], b["xyz_world_m"]) for a, b in zip(baseline["points"], restored["points"])),
        "max_anchor_uv_error_px": max(math.dist(a["uv_pixel_opencv"], b["uv_pixel_opencv"]) for a, b in zip(baseline["points"], restored["points"])),
    }
    results = [analyse_case(name, baseline, probes[name], fixture) for name, _index, _value in cases if name.startswith("B")]
    automatic_pass = all(item["passed_automatic_gate"] for item in results)
    restoration_pass = restoration["max_mesh_error_m"] <= 1e-7 and restoration["max_anchor_xyz_error_m"] <= 1e-7 and restoration["max_anchor_uv_error_px"] <= 1e-4
    after = {key: sha256(path) for key, path in protected.items()}
    protected_pass = before == after
    report = {
        "schema": "skel-natural-prone-shape-smoke-v1",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "passed_automatic_gate": automatic_pass and restoration_pass and protected_pass,
        "medical_truth": False,
        "beta_test_values": [-0.5, 0.0, 0.5],
        "case_count": len(results),
        "case_pass_count": sum(item["passed_automatic_gate"] for item in results),
        "case_fail_count": sum(not item["passed_automatic_gate"] for item in results),
        "restoration": restoration,
        "restoration_passed": restoration_pass,
        "protected_assets_before": before,
        "protected_assets_after": after,
        "protected_assets_unchanged": protected_pass,
        "cases": results,
        "limitations": [
            "Automatic gate does not prove absence of all self-intersections; every candidate preview still requires visual review.",
            "Fixed rigid placement and rigid bed do not simulate soft-tissue support or mattress deformation.",
            "Engineering anchors are not medical acupoints.",
        ],
    }
    write_json(output / "shape_smoke_report.json", report)
    make_montage(previews, output / "shape_preview_montage.png")
    (output / "README.md").write_text(
        "# SKEL 自然俯卧 Shape ±0.5 冒烟测试\n\n"
        f"自动门：{'PASS' if report['passed_automatic_gate'] else 'FAIL'}；20 个逐维案例中 {report['case_pass_count']} 个通过、{report['case_fail_count']} 个失败。\n\n"
        "自动门检查拓扑、冻结绑定、相机/床面/刚体变换、有限几何、背部/前侧可见性、床面间隙和粗略外形比例。所有预览仍需人工检查；该结果不证明医学传播或软组织接触正确。\n",
        encoding="utf-8",
    )
    manifest(output)
    print(json.dumps({"passed": report["passed_automatic_gate"], "output": str(output), "pass": report["case_pass_count"], "fail": report["case_fail_count"]}, ensure_ascii=False))
    raise SystemExit(0 if report["passed_automatic_gate"] else 2)


if __name__ == "__main__":
    main()
