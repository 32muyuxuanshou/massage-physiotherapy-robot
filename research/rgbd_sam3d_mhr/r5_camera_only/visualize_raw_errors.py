"""Raw new-model evidence from cached meshes; no additional fitting."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from visualize_real import shaded, project


EXAMPLES = ['p001195_a000053_000037', 'p001196_a000388_000011',
            'p100072_a001242_000048', 'p001202_a001230_000021']


def run(inputs, source, out):
    faces = np.load(inputs/'faces.npy')
    cells = ['official']+[f'repaired__continuation__mixed_s{s}' for s in [11, 23, 37]]
    names = ['Official raw', 'New raw seed11', 'New raw seed23', 'New raw seed37']
    records = {c:{r['key']:r for r in json.loads((source/'real_evaluation'/(c+'.json')).read_text())['records']} for c in cells}
    manifest = []
    for key in EXAMPLES:
        with np.load(inputs/'inputs'/(key+'.npz')) as z:
            K = z['A_K']; points = z['points_camera_A']
        rgb = np.asarray(Image.open(inputs/'rgb'/(key+'_A.png')))
        meshes = [np.load(inputs/'predictions'/c/(key+'.npz'))['vertices_camera_A'] for c in cells]
        fig, axes = plt.subplots(2, 5, figsize=(18, 9), layout='constrained')
        axes[0, 0].imshow(rgb); axes[0, 0].set_title('Camera A RGB input')
        axes[1, 0].scatter(points[:, 1], points[:, 2], c='black', s=.5, label='Measured A points')
        axes[1, 0].set_title('A measured Y-Z profile')
        uv = project(points, K); lo = uv.min(0); hi = uv.max(0); pad = .1*np.max(hi-lo)
        yz = np.concatenate([points]+meshes)[:, [1, 2]]
        low = yz.min(0)-.08; high = yz.max(0)+.08
        metrics = {}
        for i, (cell, name, mesh) in enumerate(zip(cells, names, meshes), 1):
            metric = records[cell][key]['triangle_before']; metrics[name] = metric
            axes[0, i].imshow(shaded(rgb, mesh, faces, K))
            axes[0, i].set_title(f"{name}\nB median / P95: {metric['median_mm']:.1f} / {metric['p95_mm']:.1f} mm")
            axes[1, i].scatter(mesh[::3, 1], mesh[::3, 2], c='#3288b4', s=.5, alpha=.5, label='Predicted mesh vertices')
            axes[1, i].scatter(points[:, 1], points[:, 2], c='black', s=.5, alpha=.6, label='Measured A points')
            axes[1, i].set_title(name+' vs measured depth')
        for a in axes[0]:
            a.set_xlim(max(0,lo[0]-pad), min(rgb.shape[1],hi[0]+pad))
            a.set_ylim(min(rgb.shape[0],hi[1]+pad),max(0,lo[1]-pad));a.axis('off')
        for a in axes[1]:
            a.set_xlim(low[0], high[0]);a.set_ylim(high[1],low[1]);a.set_aspect('equal');a.grid(alpha=.2)
            a.set_xlabel('A camera Y (m)');a.set_ylabel('A camera Z (m), farther down')
        axes[1, 1].legend(fontsize=7, markerscale=3)
        fig.suptitle(key+' | All Body parameters unchanged; new model shifts the whole mesh\nTop: perspective RGB overlay. Bottom: orthographic Y-Z diagnostic projection, NOT a cross-sectional slice or GT mesh.', fontsize=12)
        name = key+'_RAW_ALL_SEEDS.jpg';fig.savefig(out/name, dpi=120);plt.close(fig)
        manifest.append(dict(key=key, file=name, cells=cells, metrics=metrics,
                             rendering='actual frozen mesh perspective z-buffer; bottom explicitly YZ orthographic profile',
                             selection='two explanatory cases plus two historical large-error examples; all3seeds',
                             refitting=False, Body_changed=False))
        print('RAW_VISUAL', key, flush=True)
    (out/'RAW_VISUALIZATION_MANIFEST.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for name in ['inputs','source','out']:
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.inputs,a.source,a.out)
