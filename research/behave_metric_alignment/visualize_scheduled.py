"""Fixed-range private review; exact frozen renderer, only scheduling differs from final cached meshes and frozen residuals."""
import os
os.environ.setdefault('PYOPENGL_PLATFORM', 'egl')
import argparse
import json
from pathlib import Path
import numpy as np
import cv2
import torch
import nvdiffrast.torch as dr
from PIL import Image, ImageDraw, ImageOps
import matplotlib
from dataset_io import camera, project


def shading(ctx, vertices, faces, K, h, w):
    # Pinhole perspective z-buffer. Rasterization is for display, not evaluation.
    v = torch.from_numpy(vertices[None]).float().cuda()
    k = torch.from_numpy(K[None]).float().cuda()
    x, y, z = v.unbind(-1)
    near, far = .05, 20.
    clip = torch.stack((2*k[:, 0, 0, None]/w*x+(2*(k[:, 0, 2, None]+.5)/w-1)*z,
                        -2*k[:, 1, 1, None]/h*y+(1-2*(k[:, 1, 2, None]+.5)/h)*z,
                        (far+near)/(far-near)*z-2*far*near/(far-near), z), -1).contiguous()
    f = torch.from_numpy(faces).int().cuda().contiguous()
    tri = v[0, f.long()]
    n = torch.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0], dim=1)
    n = n/n.norm(dim=1, keepdim=True).clamp_min(1e-12)
    intensity = .35+.65*(n@torch.tensor([.3, -.4, -.866], device='cuda')).abs()
    rast, _ = dr.rasterize(ctx, clip, f, resolution=[h, w], grad_db=False)
    ids = rast[0, :, :, 3].long().flip(0)-1
    return (ids >= 0).cpu().numpy(), intensity[ids.clamp_min(0)].cpu().numpy()


def overlay(ctx, rgb, vertices, faces, K):
    hit, intensity = shading(ctx, vertices, faces, K, *rgb.shape[:2])
    result = rgb.astype(float)
    result[hit] = .3*result[hit]+.7*intensity[hit, None]*np.array([65, 185, 235])
    return Image.fromarray(np.uint8(np.clip(result, 0, 255)))


def heat(rgb, points, cam, distances, crop, size):
    uv = project(points, cam)
    colors = np.uint8(matplotlib.colormaps['inferno'](np.clip(distances/150, 0, 1))[:, :3]*255)
    image = Image.fromarray(rgb.copy())
    draw = ImageDraw.Draw(image)
    for (u, v), color in zip(uv, colors):
        draw.ellipse((u-3, v-3, u+3, v+3), fill=tuple(color))
    return ImageOps.pad(image.crop(crop), size, color='white')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--data-root', type=Path, required=True)
    p.add_argument('--start',type=int,required=True)
    p.add_argument('--stop',type=int,required=True)
    p.add_argument('--part',required=True)
    a = p.parse_args()
    torch.set_num_threads(2)
    ctx = dr.RasterizeCudaContext()
    root, data = a.root.resolve(), a.data_root.resolve()
    rows = json.loads((root/'inputs/INPUT_MANIFEST.json').read_text())['records'][a.start:a.stop]
    paths = json.loads((root/'PATHS.json').read_text())
    faces = np.load(paths['faces'])
    cams = [camera(data/'calibs', 'Date03', k) for k in range(4)]
    out = root/'visualizations'
    out.mkdir(exist_ok=True)
    reports = {}
    predictions = {}
    for directory in (root/'evaluation').iterdir():
        if not (directory/'RESULTS.json').exists():
            continue
        for row in json.loads((directory/'RESULTS.json').read_text())['records']:
            reports[row['cell'], row['sequence'], row['frame']] = row
    for mode in ['rgb_only', 'g1', 'coarse', 'full']:
        for seed in [11, 23, 37]:
            for ck in ['best', 'last']:
                cell = f'{mode}_s{seed}_{ck}'
                for row in json.loads((root/'predictions'/cell/'PREDICTION_MANIFEST.json').read_text())['records']:
                    predictions[cell, row['sequence'], row['frame']] = row['prediction_file']
    records = []
    size = (280, 340)
    labels = ['Official', 'Official + Txyz', 'RGB-only', 'G1', 'R5 Coarse', 'R5 Full']
    for row in rows:
        seq, frame = row['sequence'], row['frame']
        key = seq+'_'+frame
        z = np.load(row['input_file'])
        rgb, K = z['rgb'], z['K']
        y, x = np.where(z['mask'])
        margin = .15*max(x.max()-x.min(), y.max()-y.min())
        cropA = (max(0, x.min()-margin), max(0, y.min()-margin),
                 min(rgb.shape[1], x.max()+margin), min(rgb.shape[0], y.max()+margin))
        held = np.load(row['heldout_file'])
        rgbB, crops = {}, {}
        for k in [1, 2, 3]:
            rgbB[k] = cv2.cvtColor(cv2.imread(str(data/'sequences'/seq/frame/f'k{k}.color.jpg')), cv2.COLOR_BGR2RGB)
            uv = project(held[f'K{k}_points_m'], cams[k])
            lo, hi = uv.min(0), uv.max(0)
            pad = .15*max(hi-lo)
            crops[k] = (max(0, lo[0]-pad), max(0, lo[1]-pad),
                        min(rgbB[k].shape[1], hi[0]+pad), min(rgbB[k].shape[0], hi[1]+pad))
        for seed in [11, 23, 37]:
            for ck in ['best', 'last']:
                cells = [f'official_s{seed}', f'official_s{seed}_txyz']+[f'{m}_s{seed}_{ck}' for m in ['rgb_only', 'g1', 'coarse', 'full']]
                canvas = Image.new('RGB', (7*280, 4*390+42), 'white')
                draw = ImageDraw.Draw(canvas)
                draw.text((8, 6), f'{key} | seed {seed} | {ck.upper()} | BLUE = cached predicted surface; heat = independent sensor residual, clipped 150 mm', fill='black')
                draw.text((8, 22), 'A uses undistorted input RGB/K; B/C/D use original distorted RGB/projectPoints. No alignment or refitting for display.', fill='black')
                canvas.paste(ImageOps.pad(Image.fromarray(rgb).crop(cropA), size, color='white'), (0, 42+40))
                draw.text((8, 48), 'K0 RGB model input', fill='black')
                for k in [1, 2, 3]:
                    yy = 42+k*390
                    canvas.paste(ImageOps.pad(Image.fromarray(rgbB[k]).crop(crops[k]), size, color='white'), (0, yy+40))
                    draw.text((8, yy+4), f'K{k} independent RGB', fill='black')
                metrics = {}
                for col, (cell, label) in enumerate(zip(cells, labels), 1):
                    if cell == f'official_s{seed}':
                        pred = root/'cache'/f's{seed}'/(key+'.npz')
                    elif cell.endswith('_txyz'):
                        pred = root/'evaluation'/f'official_s{seed}'/(key+'_txyz.npz')
                    else:
                        pred = Path(predictions[cell, seq, frame])
                    values = np.load(pred)
                    report = reports[cell, seq, frame]
                    picture = overlay(ctx, rgb, values['vertices_camera_A'], faces, K)
                    canvas.paste(ImageOps.pad(picture.crop(cropA), size, color='white'), (col*280, 82))
                    mm = report['pve']
                    draw.text((col*280+4, 46), label, fill='black')
                    draw.text((col*280+4, 62), f"PVE {mm['pve_absolute_mm']:.1f}; centered {mm['pve_centroid_centered_mm']:.1f} mm", fill='black')
                    residual = np.load(report['distances_file'])
                    for k in [1, 2, 3]:
                        yy = 42+k*390
                        canvas.paste(heat(rgbB[k], held[f'K{k}_points_m'], cams[k], residual[f'K{k}_distance_mm'], crops[k], size), (col*280, yy+40))
                        score = report['heldout_surface'][f'K{k}']
                        draw.text((col*280+4, yy+4), f"K{k} med {score['median_mm']:.1f} / P95 {score['p95_mm']:.1f} mm", fill='black')
                        draw.text((col*280+4, yy+20), f"50 mm coverage {100*score['coverage_50mm']:.1f}%", fill='black')
                    metrics[label] = dict(pve=mm, heldout=report['heldout_surface'])
                file = f'{key}_s{seed}_{ck}.jpg'
                canvas.save(out/file, quality=87)
                records.append(dict(sequence=seq, frame=frame, subject=row['subject'], seed=seed, checkpoint=ck,
                                    file=file, methods=metrics))
        print('FRAME_VISUALIZED', len(records)//6, len(rows), flush=True)
    (out/('VISUALIZATION_MANIFEST.'+a.part+'.json')).write_text(json.dumps(dict(status='COMPLETE', records=records,
        panels=len(records), expected=len(rows)*6, selection='Every fixed frame x all three seeds x Best/Last; no positive-case filtering',
        images_private=True, meshes_refitted=False), indent=2))


if __name__ == '__main__':
    main()
