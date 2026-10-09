"""Export the existing native MHR pilot NPZs as images; no inference or fitting."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
from matplotlib import colormaps
from PIL import Image, ImageDraw, ImageFont


def export(source, output, exclude_test=False):
    manifest = json.loads((source / 'MANIFEST.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('DejaVuSans.ttf', 18)
    small = ImageFont.truetype('DejaVuSans.ttf', 14)
    cmap = colormaps['viridis']
    # One physical colour scale for every sample, never normalised per person.
    near, far = 2.0, 6.0
    cards, records, tiles = [], [], []
    for row in manifest['samples']:
        if exclude_test and row['role']=='TEST':continue
        stem = Path(row['file']).stem
        folder = output / stem
        folder.mkdir(exist_ok=True)
        with np.load(source / row['file']) as data:
            rgb = data['rgb']
            depth = data['depth_m']
            mask = data['mask'].astype(bool)
            K = data['K'].tolist()
            cam_t = data['pred_cam_t'].reshape(-1).tolist()
        valid = depth > 0
        colour = (cmap(np.clip((depth - near) / (far - near), 0, 1))[..., :3] * 255).astype(np.uint8)
        colour[~valid] = 0
        images = [Image.fromarray(rgb), Image.fromarray(colour), Image.fromarray(mask.astype(np.uint8) * 255)]
        names = ['rgb.png', 'depth.png', 'mask.png']
        titles = ['Input RGB (stored in NPZ)', 'Input camera-Z depth (2-6 m)', 'True foreground mask']
        for im, name in zip(images, names):
            im.save(folder / name)
        panel = Image.new('RGB', (1152, 388), 'white')
        draw = ImageDraw.Draw(panel)
        view=f"POSE {row['pose_id']} CAMERA {row['camera_id']}" if 'pose_id' in row else ('BACK' if row['back_view'] else 'FRONT')
        draw.text((12, 8), f"{stem} | {row['role']} | {view} | SYNTHETIC MHR", font=font, fill='black')
        for i, (im, title) in enumerate(zip(images, titles)):
            draw.text((i * 384 + 12, 42), title, font=small, fill='black')
            panel.paste(im.resize((384, 288), Image.Resampling.NEAREST if i else Image.Resampling.LANCZOS), (i * 384, 66))
        gradient = np.linspace(0, 1, 330)[None, :]
        bar = (cmap(gradient)[..., :3] * 255).astype(np.uint8)
        panel.paste(Image.fromarray(bar).resize((330, 12)), (402, 358))
        draw.text((390, 372), '2 m     3 m      4 m      5 m      6 m', font=small, fill='black')
        draw.text((12, 364), 'Black depth = no surface', font=small, fill='black')
        panel.save(folder / 'preview.jpg', quality=92)
        record = dict(**row, source_npz=str(source / row['file']),
                      rgb_shape=list(rgb.shape), depth_unit='metre', depth_definition='camera_Z',
                      depth_valid_range_m=[float(depth[valid].min()), float(depth[valid].max())],
                      depth_display_range_m=[near, far], K=K, cam_t_m=cam_t,
                      images={name: f'{stem}/{name}' for name in names + ['preview.jpg']})
        records.append(record)
        tile = Image.new('RGB', (320, 270), 'white')
        tile.paste(images[0].resize((320, 240), Image.Resampling.LANCZOS), (0, 30))
        ImageDraw.Draw(tile).text((6, 6), f"{stem}  {row['role']}", font=small, fill='black')
        tiles.append(tile)
        links = ' | '.join(f'<a href="{stem}/{name}">{name}</a>' for name in names)
        cards.append(f'<article data-role="{row["role"]}" data-name="{stem}"><a href="{stem}/preview.jpg"><img loading="lazy" src="{stem}/rgb.png"></a><b>{stem} · {row["role"]}</b><p>{links} | <a href="{stem}/preview.jpg">RGB / depth / mask</a></p></article>')
    pages = []
    for start in range(0, len(tiles), 16):
        sheet = Image.new('RGB', (1280, 1080), '#dddddd')
        for j, tile in enumerate(tiles[start:start + 16]):
            sheet.paste(tile, ((j % 4) * 320, (j // 4) * 270))
        name = f'contact_{start // 16 + 1:02d}.jpg'
        sheet.save(output / name, quality=92)
        pages.append(name)
    counts={r:sum(s['role']==r for s in records) for r in ['TRAIN','VAL','TEST']}
    title = f'合成 MHR 数据：{len(records)} 张预览'
    page_links = ' '.join(f'<a href="{p}">总览 {i + 1}</a>' for i, p in enumerate(pages))
    document = '''<!doctype html><meta charset="utf-8"><title>Native MHR data preview</title>
<style>body{font:16px system-ui;margin:24px;background:#f4f5f7;color:#20242b}header{position:sticky;top:0;background:#fff;padding:16px;z-index:1}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-top:20px}article{background:#fff;padding:12px;border-radius:8px}img{width:100%;display:block}a{color:#174fa3}input,select{font:inherit;padding:8px}p{line-height:1.6}small{color:#555}</style>
<header><h2>TITLE</h2><p>192 TRAIN / 32 VAL / 32 TEST。TEST 尚未进行模型评价。所有图片均为合成，非真人、非俯卧床上场景。</p>
<p>点击人体图打开 RGB、真值深度、mask 三图对照。深度统一色标 2–6 米，黑色表示无表面；这是生成数据的真值，不是模型预测。</p>
<select id="role"><option>ALL</option><option>TRAIN</option><option>VAL</option><option>TEST</option></select> <input id="query" placeholder="搜索 native_024"><span id="count"></span><p>PAGES</p><small>数据源：SOURCE</small></header><main>CARDS</main>
<script>function filter(){let n=0;document.querySelectorAll('article').forEach(a=>{let show=(role.value==='ALL'||a.dataset.role===role.value)&&a.dataset.name.includes(query.value);a.hidden=!show;a.style.display=show?'':'none';n+=show});document.getElementById('count').textContent=' '+n+' 张'}const role=document.getElementById('role'),query=document.getElementById('query');role.onchange=query.oninput=filter;filter();</script>'''
    document = document.replace('192 TRAIN / 32 VAL / 32 TEST。TEST 尚未进行模型评价。',
        f"{counts['TRAIN']} TRAIN / {counts['VAL']} VAL / {counts['TEST']} TEST 展示。"+('TEST 保持封存，未导出图片。' if exclude_test else 'TEST 尚未进行模型评价。'))
    document = document.replace('这是生成数据的真值，不是模型预测。','这是 NPZ 中实际输入的深度；R3 含噪声和缺测，并非模型预测。')
    document = document.replace('TITLE', title).replace('PAGES', page_links).replace('SOURCE', html.escape(str(source))).replace('CARDS', '\n'.join(cards))
    (output / 'index.html').write_text(document, encoding='utf-8')
    report = dict(status='EXPORTED_NO_MODEL_EXECUTED', source=str(source), output=str(output),
                  count=len(records), roles={r: sum(s['role'] == r for s in records) for r in ['TRAIN', 'VAL', 'TEST']},
                  contact_sheets=pages, records=records)
    (output / 'PREVIEW_MANIFEST.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'records'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--exclude-test',action='store_true')
    args = parser.parse_args()
    export(args.input_dir, args.output_dir,args.exclude_test)
