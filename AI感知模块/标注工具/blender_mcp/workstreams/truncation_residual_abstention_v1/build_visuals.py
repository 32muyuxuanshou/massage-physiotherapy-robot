from __future__ import annotations

import argparse
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


COLORS = {"COMBINATION_HOLDOUT": "#3B82F6", "SHAPE_HOLDOUT": "#10B981", "POSE_HOLDOUT": "#F59E0B"}


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig")))
    image = Image.new("RGB", (1500, 900), "#F8FAFC")
    draw = ImageDraw.Draw(image)
    draw.text((55, 28), "截断残差与热图置信度诊断（V2）", fill="#0F172A", font=font(30))
    draw.text((55, 70), "E01–E20 为非医学工程点；误差单位为原始 1280×1024 像素", fill="#475569", font=font(18))
    # Scatter: confidence versus 2D error.
    x0, y0, width, height = 70, 140, 900, 650
    draw.rectangle((x0, y0, x0 + width, y0 + height), outline="#94A3B8", width=2)
    subset = [r for r in rows if r["version"] == "v2" and r["visible"] == "True"]
    max_error = max(float(r["error_2d_px"]) for r in subset)
    max_peak = max(float(r["peak_probability"]) for r in subset)
    for row in subset:
        x = x0 + float(row["peak_probability"]) / max_peak * width
        y = y0 + height - min(float(row["error_2d_px"]), max_error) / max_error * height
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=COLORS[row["split"]])
    draw.text((x0 + 300, y0 + height + 25), "热图峰值概率 →", fill="#334155", font=font(18))
    draw.text((x0 - 20, y0 - 30), "二维误差 ↑", fill="#334155", font=font(18))
    # Summary cards.
    card_x = 1010
    draw.text((card_x, 140), "关键发现", fill="#0F172A", font=font(25))
    summaries = []
    for split in COLORS:
        q = [r for r in subset if r["split"] == split and r["error_3d_mm"]]
        tail = [r for r in q if float(r["error_3d_mm"]) > 30]
        safe = [r for r in q if float(r["error_3d_mm"]) <= 30]
        tail_peak = sum(float(r["peak_probability"]) for r in tail) / len(tail)
        safe_peak = sum(float(r["peak_probability"]) for r in safe) / len(safe)
        summaries.append((split, len(tail), tail_peak, safe_peak))
    y = 190
    for split, count, tail_peak, safe_peak in summaries:
        draw.rounded_rectangle((card_x, y, 1440, y + 120), radius=12, fill="white", outline=COLORS[split], width=3)
        draw.text((card_x + 18, y + 12), split.replace("_HOLDOUT", ""), fill=COLORS[split], font=font(18))
        draw.text((card_x + 18, y + 46), f">30mm 尾部：{count} 个", fill="#1E293B", font=font(17))
        draw.text((card_x + 18, y + 76), f"尾部峰值 {tail_peak:.3f}  >  非尾部 {safe_peak:.3f}", fill="#B91C1C", font=font(16))
        y += 145
    draw.rounded_rectangle((card_x, 650, 1440, 790), radius=12, fill="#FFF7ED", outline="#EA580C", width=3)
    draw.text((card_x + 18, 670), "结论", fill="#9A3412", font=font(22))
    draw.multiline_text((card_x + 18, 710), "当前 softmax 峰值反向校准：\n网络对错误常见位置反而更自信。\n不能直接作为机器人拒答阈值。", fill="#7C2D12", font=font(17), spacing=7)
    image.save(args.output / "confidence_vs_2d_error.png")


if __name__ == "__main__":
    main()
