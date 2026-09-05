from pathlib import Path
import shutil
import sys

from PIL import Image


workspace = Path(sys.argv[1])
deck = Path(sys.argv[2])


def ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


slide01 = ensure(deck / "assets" / "slide_01")
slide02 = ensure(deck / "assets" / "slide_02")
slide04 = ensure(deck / "assets" / "slide_04")
slide05 = ensure(deck / "assets" / "slide_05")
slide06 = ensure(deck / "assets" / "slide_06")
slide07 = ensure(deck / "assets" / "slide_07")

skel_source = workspace / "AI感知模块" / "教程制作" / "screenshots" / "raw" / "skel_01_skin_annotation_panel.jpg"
pose_panel_source = deck / "assets" / "slide_03" / "04_Pose更新面板.png"
rgbd_source = workspace / "组会汇报PPT素材_2026-09-02" / "04_RGBD数据生成" / "RGB_Depth_Mask_Overlay四联图.png"
visibility_source = workspace / "组会汇报PPT素材_2026-09-02" / "07_CameraVisibility结果" / "四类Camera_Visibility案例对比.png"
shape_source = workspace / "AI感知模块" / "outputs" / "交付文件" / "2026-08-31_14-37-36_GPT网页端审查包" / "08_A_Shape对比图.png"
pose_source = workspace / "AI感知模块" / "outputs" / "交付文件" / "2026-08-31_14-37-36_GPT网页端审查包" / "09_B_Pose对比图.png"
matrix_source = workspace / "组会汇报PPT素材_2026-09-02" / "06_ShapePose验证" / "17合格_1警戒_ShapePose矩阵.png"

skel = Image.open(skel_source).convert("RGB")
skel_crop = skel.crop((35, 80, 1585, 945))
skel_crop.save(slide01 / "skel_plugin_crop.jpg", quality=92, optimize=True)

rgbd = Image.open(rgbd_source).convert("RGB")
pose_panel = Image.open(pose_panel_source).convert("RGB")
process_board = Image.new("RGB", (1536, 864), "white")
left = skel_crop.copy()
left.thumbnail((850, 610))
process_board.paste(left, (0, 70))
panel = pose_panel.copy()
panel.thumbnail((230, 610))
process_board.paste(panel, (880, 70))
quad = rgbd.copy()
quad.thumbnail((1536, 240))
process_board.paste(quad, (0, 624))
process_board.save(slide02 / "process_source_board.jpg", quality=90, optimize=True)

shutil.copy2(rgbd_source, slide04 / "rgbd_quad.png")
shutil.copy2(visibility_source, slide05 / "visibility_cases.png")
shutil.copy2(visibility_source, slide07 / "camera_visibility_cases.png")

shape = Image.open(shape_source).convert("RGB")
pose = Image.open(pose_source).convert("RGB")
matrix = Image.open(matrix_source).convert("RGB")
evidence = Image.new("RGB", (1536, 864), "white")
shape.thumbnail((750, 500))
pose.thumbnail((750, 500))
matrix.thumbnail((1536, 330))
evidence.paste(shape, (0, 30))
evidence.paste(pose, (786, 30))
evidence.paste(matrix, ((1536 - matrix.width) // 2, 530))
evidence.save(slide06 / "shape_pose_evidence_board.jpg", quality=90, optimize=True)
