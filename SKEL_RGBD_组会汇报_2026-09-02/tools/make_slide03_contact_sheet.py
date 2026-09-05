from pathlib import Path
import sys

from PIL import Image


asset_dir = Path(sys.argv[1])
main = Image.open(asset_dir / "01_标注视口.png").convert("RGB")
annotation = Image.open(asset_dir / "02_标注插件面板.png").convert("RGB")
json_panel = Image.open(asset_dir / "03_JSON导入导出.png").convert("RGB")
pose = Image.open(asset_dir / "04_Pose更新面板.png").convert("RGB")

canvas = Image.new("RGB", (1536, 864), "white")
main.thumbnail((1040, 720))
annotation.thumbnail((210, 610))
pose.thumbnail((210, 610))
json_panel.thumbnail((210, 150))

canvas.paste(main, (0, 72))
canvas.paste(annotation, (1070, 72))
canvas.paste(pose, (1300, 72))
canvas.paste(json_panel, (1070, 702))
canvas.save(asset_dir / "00_截图证据板.jpg", quality=88, optimize=True)
