from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent


official_teaser = Image.open(ROOT / "01_研究目标" / "SKEL官方论文Teaser.png").convert("RGB")
official_teaser.crop((0, 0, int(official_teaser.width * 0.43), official_teaser.height)).save(
    ROOT / "01_研究目标" / "SKEL官方论文Teaser_仅模型.png"
)


def fit_image(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.paste(image, (x, y))
    return canvas


def make_panel(paths: list[Path], labels: list[str], out: Path) -> None:
    tile_w, tile_h, header_h = 600, 480, 54
    panel = Image.new("RGB", (tile_w * len(paths), tile_h + header_h), "white")
    draw = ImageDraw.Draw(panel)
    font = ImageFont.load_default(size=24)
    for i, (path, label) in enumerate(zip(paths, labels)):
        panel.paste(fit_image(path, (tile_w, tile_h)), (i * tile_w, header_h))
        draw.text((i * tile_w + 18, 14), label, fill=(25, 38, 55), font=font)
    panel.save(out, quality=95)


rgbd = ROOT / "04_RGBD数据生成"
depth = np.load(rgbd / "02_Depth原始数据_scene_depth_z.npy")
valid = depth > 0
lo, hi = np.percentile(depth[valid], [2, 98])
norm = np.zeros_like(depth, dtype=np.float32)
norm[valid] = np.clip((depth[valid] - lo) / max(hi - lo, 1e-6), 0, 1)
# Compact blue-cyan-yellow-red ramp without an external plotting dependency.
stops = np.array([0.0, 0.33, 0.66, 1.0], dtype=np.float32)
colors = np.array(
    [[38, 52, 148], [37, 189, 196], [250, 221, 58], [180, 4, 38]],
    dtype=np.float32,
)
depth_rgb = np.empty((*depth.shape, 3), dtype=np.uint8)
for channel in range(3):
    depth_rgb[..., channel] = np.interp(norm, stops, colors[:, channel]).astype(np.uint8)
depth_rgb[~valid] = (31, 31, 31)
Image.fromarray(depth_rgb).save(rgbd / "02_Depth可视化.png")

make_panel(
    [
        rgbd / "01_RGB.png",
        rgbd / "02_Depth可视化.png",
        rgbd / "03_Skin_Mask.png",
        rgbd / "04_穴位Overlay.png",
    ],
    ["RGB", "Depth (visualized)", "Skin Mask", "2D Keypoint Overlay"],
    rgbd / "RGB_Depth_Mask_Overlay四联图.png",
)

camera = ROOT / "07_CameraVisibility结果"
make_panel(
    [
        camera / "C1_MILD_OBLIQUE_Overlay.png",
        camera / "C2_EDGE_CROP_Overlay.png",
        camera / "C3_EXTERNAL_OCCLUDER_Overlay.png",
        camera / "C4_SELF_OCCLUSION_STRESS_Overlay.png",
    ],
    ["Mild oblique", "Out of frame", "External occlusion", "Extreme side view"],
    camera / "四类Camera_Visibility案例对比.png",
)
