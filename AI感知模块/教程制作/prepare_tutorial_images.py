"""Prepare legible, numbered Blender screenshots for the doctor tutorial."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "screenshots" / "raw"
OUT = ROOT / "screenshots" / "prepared"
OUT.mkdir(parents=True, exist_ok=True)

INK = "#102A43"
BLUE = "#1F5A94"
CYAN = "#1FB6B2"
GOLD = "#F4B942"
RED = "#D64545"
PAPER = "#F7F9FC"
WHITE = "#FFFFFF"


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


F_TITLE = font(40, True)
F_LABEL = font(27, True)
F_SMALL = font(21)
F_NUM = font(29, True)


def fit(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    copy = image.copy()
    copy.thumbnail(box, Image.Resampling.LANCZOS)
    return copy


def number(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: int, color=GOLD):
    x, y = xy
    r = 25
    draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline=WHITE, width=3)
    text = str(value)
    bbox = draw.textbbox((0, 0), text, font=F_NUM)
    draw.text((x - (bbox[2] - bbox[0]) / 2, y - (bbox[3] - bbox[1]) / 2 - 3), text, font=F_NUM, fill=INK)


def text_box(draw, xy, text, width=500, fill=WHITE, outline="#D9E2EC"):
    x, y = xy
    lines = []
    current = ""
    for char in text:
        trial = current + char
        if draw.textlength(trial, font=F_SMALL) > width - 30 and current:
            lines.append(current)
            current = char
        else:
            current = trial
    if current:
        lines.append(current)
    height = 18 + len(lines) * 32
    draw.rounded_rectangle((x, y, x + width, y + height), radius=12, fill=fill, outline=outline, width=2)
    for idx, line in enumerate(lines):
        draw.text((x + 15, y + 9 + idx * 32), line, font=F_SMALL, fill=INK)
    return height


def overview_with_panel(source: str, output: str, title: str, notes: list[str], panel_x=(1310, 1565)):
    src = Image.open(RAW / source).convert("RGB")
    canvas = Image.new("RGB", (1920, 1120), PAPER)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1920, 86), fill=INK)
    draw.text((40, 20), title, font=F_TITLE, fill=WHITE)

    overview = fit(src.crop((0, 45, 1310, 990)), (1260, 970))
    canvas.paste(overview, (30, 110))
    panel = src.crop((panel_x[0], 75, panel_x[1], 950))
    panel = fit(panel, (570, 760))
    panel_x0 = 1320
    canvas.paste(panel, (panel_x0, 110))
    draw.rounded_rectangle((1310, 100, 1565, 885), radius=14, outline=CYAN, width=6)

    y = 115
    for idx, note in enumerate(notes, 1):
        number(draw, (1590, y + 25), idx)
        height = text_box(draw, (1625, y), note, width=270)
        y += height + 22
    canvas.save(OUT / output, quality=94, subsampling=0)


def full_figure(source: str, output: str, title: str, notes: list[str]):
    src = Image.open(RAW / source).convert("RGB")
    canvas = Image.new("RGB", (1920, 1120), PAPER)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1920, 86), fill=INK)
    draw.text((40, 20), title, font=F_TITLE, fill=WHITE)
    view = fit(src.crop((185, 80, 1310, 950)), (1330, 970))
    canvas.paste(view, (25, 105))
    draw.rounded_rectangle((1380, 105, 1900, 1070), radius=14, fill=WHITE, outline="#D9E2EC", width=3)
    y = 140
    for idx, note in enumerate(notes, 1):
        number(draw, (1420, y + 25), idx, color=CYAN)
        height = text_box(draw, (1460, y), note, width=400, fill="#F7FBFF")
        y += height + 32
    canvas.save(OUT / output, quality=94, subsampling=0)


overview_with_panel(
    "smplx_02_annotation_panel.jpg",
    "01_smplx_open_and_annotate.jpg",
    "SMPL-X：打开模型并进入穴位标注",
    [
        "单击人体后，在视图区按 Home，把人体完整显示在中央。",
        "按 N 打开右侧栏；选择“项目/Item”标签，展开“全身穴位标注”。",
        "先选人体；填写标准编码、中文名称、身体分区、经脉/区域、侧别和备注。",
        "单击“在人体表面选点”，鼠标变为准星后，再单击目标皮肤表面。",
    ],
)

overview_with_panel(
    "smplx_03_body_shape_panel.jpg",
    "02_smplx_shape_pose.jpg",
    "SMPL-X：按身高体重近似调整体型与姿态",
    [
        "切到右侧“SMPL模型”标签；模板已是 SMPL-X，不要按“添加”再生成第二个人体。",
        "输入目标身高（米）和目标体重（千克），单击“根据身高体重生成体型”。",
        "这是统计体型近似，不等同患者扫描；不满意可按“重置”。",
        "姿态调整后保留“启用姿态修正”，并执行“更新姿态修正”。",
    ],
)

full_figure(
    "smplx_04_three_points_front.jpg",
    "03_smplx_three_points_front.jpg",
    "SMPL-X：三个演示点（正面）",
    [
        "图中名称均写明“非医学”，只示范完整软件流程。",
        "小十字是标记点；旁边直接显示医生填写的中文名称与标准编码。",
        "SMPL-X 可标全身、手部和头面部；精细位置请放大后再落点。",
    ],
)

full_figure(
    "smplx_05_three_points_back.jpg",
    "04_smplx_three_points_back.jpg",
    "SMPL-X：切到背面复核点位",
    [
        "按“后”切到背面；左右侧别以人体自身左右为准，不以屏幕左右为准。",
        "逐点复核名称、编码、身体分区和侧别；插件不会自动生成镜像点。",
        "落点错误不能直接拖动：删除该点后，在正确位置重新标注。",
    ],
)


def smplx_pose_slider_figure():
    src = Image.open(ROOT.parent / "标注工具" / "图文教程素材" / "04_姿态滑动条.jpg").convert("RGB")
    canvas = Image.new("RGB", (1920, 1120), PAPER)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1920, 86), fill=INK)
    draw.text((40, 20), "SMPL-X：滑动条不在“SMPL模型”页签", font=F_TITLE, fill=WHITE)

    view = fit(src.crop((0, 45, 1580, 930)), (1450, 960))
    canvas.paste(view, (25, 115))
    draw.rounded_rectangle((1490, 105, 1900, 1070), radius=14, fill=WHITE, outline="#D9E2EC", width=3)
    y = 135
    notes = [
        "鼠标放在三维视图区，按 N 打开右侧栏。",
        "切到“项目/Item”页签；不要停留在“SMPL模型”页签。",
        "向下滚动“全身穴位标注”面板，找到蓝色按钮“显示姿态滑动条”。",
        "单击按钮后才会展开脊柱、肩、肘、腕和下颌的角度滑条。若按钮也不存在，请关闭 Blender 后重新用项目的一键 .cmd 打开模板。",
    ]
    for idx, note in enumerate(notes, 1):
        number(draw, (1530, y + 25), idx)
        height = text_box(draw, (1565, y), note, width=300)
        y += height + 40
    canvas.save(OUT / "03_smplx_pose_sliders.jpg", quality=94, subsampling=0)


smplx_pose_slider_figure()

overview_with_panel(
    "skel_01_skin_annotation_panel.jpg",
    "05_skel_open_and_annotate.jpg",
    "SKEL：默认仅显示皮肤后标注",
    [
        "打开女性或男性 SKEL 模板；性别来自所选模板，不是软件对患者的判断。",
        "医生标点时建议只显示皮肤，避免骨骼和关节名称遮挡。",
        "穴位标注方法与 SMPL-X 相同：填写信息，再在皮肤表面单击。",
        "SKEL 没有独立手指关节和面部表情；手部、头面部精细标注请用 SMPL-X。",
    ],
)

overview_with_panel(
    "skel_02_shape_visibility_panel.jpg",
    "06_skel_shape_visibility.jpg",
    "SKEL：体型参数与骨骼显示",
    [
        "展开“SKEL 生物力学控制”；默认勾选皮肤、关闭骨骼和关节名称。",
        "需要解剖对照时才勾选内部骨骼，再单击“应用显示设置”。",
        "β0 约为身高方向，β1 约为体重方向；其余为统计体型分量，建议先限制在 -2～2。",
        "SKEL 体型参数也不是患者扫描结果，记录时要保留所用参数。",
    ],
)

overview_with_panel(
    "skel_03_pose_update_panel.jpg",
    "07_skel_pose_update.jpg",
    "SKEL：姿态滑条、计算与刷新",
    [
        "常用姿态以“度”为单位；先小幅调整，避免一次改变过大。",
        "参数改变后不会自动重算：标点前必须执行一次更新。",
        "仅需皮肤标注时用“快速更新皮肤”；查看骨骼时用“完整更新皮肤和骨骼”。",
        "“恢复默认体型与姿势”会清除当前参数，请先另存工作副本。",
    ],
)

print(f"PREPARED={len(list(OUT.glob('*.jpg')))}")


def explorer_figure():
    """Show the real folder breadcrumb and the exact one-click launchers."""
    top = Image.open(ROOT / "screenshots" / "explorer_model_resources.jpg").convert("RGB")
    bottom = Image.open(ROOT / "screenshots" / "explorer_smplx_launchers.jpg").convert("RGB")
    canvas = Image.new("RGB", (1920, 1300), PAPER)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1920, 86), fill=INK)
    draw.text((40, 20), "从文件夹打开模板：不需要手工输入完整路径", font=F_TITLE, fill=WHITE)

    top_view = top.crop((150, 35, 1185, 390)).resize((1420, 488), Image.Resampling.LANCZOS)
    bottom_view = bottom.crop((150, 35, 1185, 960)).resize((1420, 666), Image.Resampling.LANCZOS)
    canvas.paste(top_view, (30, 105))
    canvas.paste(bottom_view, (30, 615))
    draw.rounded_rectangle((1475, 105, 1890, 1260), radius=14, fill=WHITE, outline="#D9E2EC", width=3)

    y = 145
    notes = [
        "先打开项目文件夹 AI感知模块，再双击黄色文件夹“模型资源”。",
        "常规全身、手部和头面部标注：双击“SMPL-X”文件夹。",
        "把列表滚到底部，双击“打开_中性_SMPL-X全身标注.cmd”；任务单指定女性/男性时改开对应文件。",
        "不要双击 .blend 模板；不要打开 SMPL 文件夹。需要骨骼对照时返回上一层，进入 SKEL。",
    ]
    for idx, note in enumerate(notes, 1):
        number(draw, (1515, y + 25), idx)
        height = text_box(draw, (1550, y), note, width=300)
        y += height + 38
    canvas.save(OUT / "00_explorer_launch.jpg", quality=94, subsampling=0)


explorer_figure()
print("EXPLORER_FIGURE=1")
