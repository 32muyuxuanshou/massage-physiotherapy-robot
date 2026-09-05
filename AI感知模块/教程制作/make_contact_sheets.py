"""Create contact sheets for fast visual review of every rendered tutorial page."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SOURCE = Path(__import__("os").environ.get("TUTORIAL_RENDER_DIR", ROOT / "rendered_v1"))
OUT = Path(__import__("os").environ.get("TUTORIAL_CONTACT_DIR", ROOT / "contact_sheets_v1"))
OUT.mkdir(exist_ok=True)

font_path = Path("C:/Windows/Fonts/msyh.ttc")
font = ImageFont.truetype(str(font_path), 26) if font_path.exists() else ImageFont.load_default()
pages = sorted(SOURCE.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[1]))

for sheet_index in range(0, len(pages), 4):
    canvas = Image.new("RGB", (1700, 2300), "#C9D3DF")
    draw = ImageDraw.Draw(canvas)
    for slot, path in enumerate(pages[sheet_index : sheet_index + 4]):
        page = Image.open(path).convert("RGB")
        page.thumbnail((790, 1050), Image.Resampling.LANCZOS)
        x = 40 + (slot % 2) * 830
        y = 60 + (slot // 2) * 1120
        canvas.paste(page, (x, y))
        draw.text((x, y - 38), f"第 {int(path.stem.split('-')[1])} 页", font=font, fill="#102A43")
    canvas.save(OUT / f"sheet-{sheet_index // 4 + 1}.jpg", quality=92)

print(f"SHEETS={len(list(OUT.glob('*.jpg')))}")
