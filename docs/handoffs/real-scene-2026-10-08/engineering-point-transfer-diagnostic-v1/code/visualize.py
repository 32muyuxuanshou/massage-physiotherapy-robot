"""Full-cohort figures from saved point caches; never fit geometry for a picture."""
import argparse, csv, hashlib, json, time
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from PIL import Image, ImageDraw
from analyze import ROOT, REPO, CONTROL, SITE, ATLAS_ROOT, Sources, read, write, sha

COLORS = ['#d44b43', '#2479bc', '#924bb6']
POINT_COLORS = plt.get_cmap('tab10')(np.arange(8))
MARKERS = ['o', '^', 's']


def save(fig, folder, name, rows, **identity):
    dest = ROOT / 'figures' / folder / name; dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=110); plt.close(fig)
    rows.append(dict(path=dest.relative_to(ROOT).as_posix(), sha256=sha(dest), **identity))


def equal_limits(axes, arrays, dims):
    p = np.concatenate(arrays); low = p[:, dims].min(0); high = p[:, dims].max(0)
    margin = np.maximum((high - low) * .1, 8)
    for ax in axes:
        ax.set_xlim(low[0] - margin[0], high[0] + margin[0]); ax.set_ylim(high[1] + margin[1], low[1] - margin[1])
        ax.set_aspect('equal', adjustable='box')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--private-input', type=Path); parser.add_argument('--private-out', type=Path)
    a = parser.parse_args(); start = time.monotonic(); cfg = read(ROOT / 'EXECUTION_CONFIG.json'); out = []
    src = Sources(); old_manifest = read(ROOT / 'SOURCE_MANIFEST.json')
    for r in old_manifest['rows']:
        src.rows[(REPO / r['path']).resolve()] = r
    canonical = dict(np.load(ROOT / 'canonical_cache.npz')); native = REPO / 'output/prone_back_point_validation_v1/assets'
    v = np.load(src.add(native / 'mhr_rest_vertices.npy')).astype(float) * 10
    f = np.load(src.add(native / 'mhr_faces.npy'))
    ids = src.json(ATLAS_ROOT / 'results/a_atlas/ENGINEERING_WORK_REGION_V2.json')['face_ids']
    fig, axes = plt.subplots(1, 2, figsize=(10, 7))
    for ax, dims, title in [(axes[0], [0, 1], 'Canonical back: X / Y'), (axes[1], [2, 1], 'Canonical side: Z / Y')]:
        ax.add_collection(PolyCollection(v[f[ids]][:, :, dims], facecolors='#ccd8df', edgecolors='none', alpha=.7))
        p = canonical['xyz_m'] * 1000
        ax.scatter(p[:, dims[0]], p[:, dims[1]], c=POINT_COLORS, s=45, edgecolors='black')
        for j, pos in enumerate(p): ax.annotate(str(j + 1), pos[dims], xytext=(5, 4), textcoords='offset points')
        ax.autoscale(); ax.set_aspect('equal'); ax.set_title(title); ax.set_xlabel('mm'); ax.set_ylabel('mm')
    fig.suptitle('8 frozen geometric probes; no acupoint or vertebral semantics\nCanonical raw cm -> mm x10; posterior working region only')
    fig.tight_layout(rect=[0, 0, 1, .92]); save(fig, '', 'CANONICAL_8_POINTS.png', out, kind='canonical')

    z = dict(np.load(ROOT / 'controlled_cache.npz')); cache = 0
    per = list(csv.DictReader((ROOT / 'CONTROLLED_PER_SUBJECT.csv').open(encoding='utf-8')))
    for subject in cfg['subjects']:
        for case in cfg['controlled_cases']:
            ix = np.arange(cache, cache + 4); cache += 4
            p = z['xyz_m'][ix] * 1000; ref = z['reference_xyz_m'][ix] * 1000
            err = np.linalg.norm(p - ref, axis=2)
            fig, axes = plt.subplots(3, 4, figsize=(15, 10), gridspec_kw={'height_ratios': [1, 1, .7]})
            for k, method in enumerate(cfg['controlled_methods']):
                row = next(r for r in per if (r['subject'], r['case'], r['method']) == (subject, case, method))
                axes[0, k].set_title(f"{method}\nPoint med {float(row['point_median_mm']):.2f} mm / surface {float(row['surface_median_mm']):.2f} mm", fontsize=10)
                for ax, dims in [(axes[0, k], [0, 1]), (axes[1, k], [2, 1])]:
                    ax.scatter(ref[k, :, dims[0]], ref[k, :, dims[1]], c='#1c9b7a', s=25, label='Known reference')
                    ax.scatter(p[k, :, dims[0]], p[k, :, dims[1]], c='#d4474e', s=26, marker='x', label='Transferred point')
                    for j in range(8):
                        ax.plot([ref[k, j, dims[0]], p[k, j, dims[0]]], [ref[k, j, dims[1]], p[k, j, dims[1]]], c='#777', lw=.7)
                        ax.annotate(str(j + 1), ref[k, j, dims], xytext=(3, 3), textcoords='offset points', fontsize=7)
                    ax.set_xlabel(('X' if dims[0] == 0 else 'Z') + ' / mm'); ax.set_ylabel('Y / mm')
                axes[2, k].bar(np.arange(8) + 1, err[k], color=POINT_COLORS); axes[2, k].set_ylim(0, max(55, err.max() * 1.05))
                axes[2, k].set_xticks(np.arange(8) + 1); axes[2, k].set_ylabel('3D point error / mm'); axes[2, k].set_xlabel('Frozen point ID')
            equal_limits(axes[0], [p.reshape(-1, 3), ref.reshape(-1, 3)], [0, 1])
            equal_limits(axes[1], [p.reshape(-1, 3), ref.reshape(-1, 3)], [2, 1])
            axes[0, 0].legend(fontsize=7)
            fig.suptitle(f'{subject} / {case} / known digital reference\nCoordinate-cache replay; no new fit; INITIAL = injected mesh, not a new SAM inference', fontsize=12)
            fig.tight_layout(rect=[0, 0, 1, .94])
            save(fig, 'controlled', f'{subject}_{case}.png', out, kind='controlled_points', subject=subject, case=case)

    z = dict(np.load(ROOT / 'real_cache.npz')); spans = np.max([np.linalg.norm(z['xyz_m'][:, x] - z['xyz_m'][:, y], axis=-1) * 1000 for x, y in [(0, 1), (0, 2), (1, 2)]], axis=0)
    roi_entries = src.json(REPO / 'docs/handoffs/real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2/POSTERIOR_RGB_ROI.json')['entries']
    roi = {r['subject']: r for r in roi_entries}
    for i, subject in enumerate(cfg['subjects']):
        back = src.json(SITE / 'site/cases' / (subject + '.json'))
        v = np.asarray(back['vertices_m']) * 1000; f = np.asarray(back['faces'])
        p = z['xyz_m'][i] * 1000; K = z['K'][i]
        fig, axes = plt.subplots(2, 2, figsize=(12, 12))
        for ax, dims in [(axes[0, 0], [0, 1]), (axes[0, 1], [2, 1])]:
            ax.add_collection(PolyCollection(v[f][:, :, dims], facecolors='#d5dfe5', edgecolors='none', alpha=.5))
            for method in range(3):
                for seed in range(3):
                    ax.scatter(p[seed, method, :, dims[0]], p[seed, method, :, dims[1]], s=32,
                        c=COLORS[method], marker=MARKERS[seed], label=f"{cfg['real_methods'][method]} / split{seed}")
            for j in range(8): ax.annotate(str(j + 1), p[0, 2, j, dims], xytext=(4, 3), textcoords='offset points', fontsize=8)
            equal_limits([ax], [v, p.reshape(-1, 3)], dims)
            ax.set_xlabel(('X' if dims[0] == 0 else 'Z') + ' / mm'); ax.set_ylabel('Y / mm')
            ax.set_title('Camera-coordinate geometry view; NOT a photograph', fontsize=9)
        ax = axes[1, 0]; polygon = np.asarray(roi[subject]['polygon_xy_px']); polygon = np.vstack([polygon, polygon[0]])
        ax.fill(polygon[:, 0], polygon[:, 1], color='#c7e5cd', alpha=.55, label='Frozen visible-back ROI')
        for method in range(3):
            for seed in range(3):
                h = (p[seed, method] / 1000) @ K.T; uv = h[:, :2] / h[:, 2:]
                ax.scatter(uv[:, 0], uv[:, 1], c=COLORS[method], marker=MARKERS[seed], s=30)
        h = p[0, 2] / 1000 @ K.T; uv = h[:, :2] / h[:, 2:]
        for j, xy in enumerate(uv): ax.annotate(str(j + 1), xy, xytext=(4, 3), textcoords='offset points', fontsize=8)
        ax.set_xlim(0, back['image_width']); ax.set_ylim(back['image_height'], 0); ax.set_aspect('equal')
        ax.set_xlabel('Original-image u / px'); ax.set_ylabel('Original-image v / px'); ax.set_title('Perspective point projection / approximate K / RGB omitted', fontsize=9); ax.legend(fontsize=7)
        ax = axes[1, 1]
        for k in [1, 2]: ax.bar(np.arange(8) + 1 + (k - 1.5) * .3, spans[i, k], width=.3, color=COLORS[k], label=cfg['real_methods'][k])
        ax.set_xticks(np.arange(8) + 1); ax.set_xlabel('Frozen point ID'); ax.set_ylabel('Max pairwise split span / mm')
        ax.set_title('Stability, NOT point accuracy\nOfficial shares one initial mesh: span = 0 by construction', fontsize=9); ax.legend(fontsize=8)
        axes[0, 0].legend(fontsize=6, loc='best')
        fig.suptitle(f'{subject}: all 8 points / all 3 input splits / 3 methods\nGrey context in BOTH views = RigidD split0 cached posterior; no independent patient target GT', fontsize=11)
        fig.tight_layout(rect=[0, 0, 1, .95]); save(fig, 'real', f'{subject}.png', out, kind='real_stability', subject=subject)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for k in [1, 2]:
        axes[0].plot(np.arange(20), np.median(spans[:, k], axis=1), 'o-', color=COLORS[k], label=cfg['real_methods'][k])
    axes[0].set_xticks(np.arange(20), cfg['subjects'], rotation=90); axes[0].set_ylabel('8-point median split span / mm'); axes[0].legend()
    agg = read(ROOT / 'CONTROLLED_AGGREGATED.json')
    for k, method in enumerate(cfg['controlled_methods'][1:]):
        q = [next(r for r in agg if (r['role'], r['case'], r['method']) == ('consumed_test', case, method)) for case in cfg['controlled_cases']]
        axes[1].bar(np.arange(3) + (k - 1) * .22, [r['subject_equal_point_median_mm'] for r in q], width=.22, label=method)
    axes[1].set_xticks(np.arange(3), ['Position', 'Normal bump', 'Tangential shift']); axes[1].set_ylabel('Known-reference point error / mm'); axes[1].legend(fontsize=8)
    fig.suptitle('Two different questions: real-data stability (left), digital-reference accuracy (right)')
    fig.tight_layout(); save(fig, '', 'ALL_SUBJECT_SUMMARY.png', out, kind='summary')
    assert len(out) == 82
    write('VISUALIZATION_MANIFEST.json', dict(new_pages=out, counts=dict(canonical=1, controlled=60, real=20, summary=1), all_subjects_preserved=True))
    write('SOURCE_MANIFEST.json', dict(rows=list(src.rows.values()), historical_hash_checks=sum(r['historical_hash_checked'] for r in src.rows.values())))
    index = ['# 全量复查索引', '', '数字图只显示点坐标；原实验完整 Mesh 叠图在右列。原叠图未重新渲染。', '', '| 人物 | 点位受控对照 | 历史 Mesh 叠图 | 真人三方法/三划分 |', '|---|---|---|---|']
    for subject in cfg['subjects']:
        for j, case in enumerate(cfg['controlled_cases']):
            index.append(f'| {subject} / {case} | [逐点图](figures/controlled/{subject}_{case}.png) | [历史 Mesh 图](../../../real-scene-2026-10-04/controlled-back-reference-v1/figures/{subject}_{case}.jpg) | ' + (f'[真人稳定性图](figures/real/{subject}.png)' if j == 0 else '') + ' |')
    # From this delivery, date directory is one level up, handoffs two levels up.
    index = [s.replace('../../../real-scene', '../../real-scene') for s in index]
    (ROOT / 'VISUAL_INDEX.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    if a.private_input:
        from scipy.spatial import cKDTree
        a.private_out.mkdir(parents=True, exist_ok=True)
        data = dict(np.load(a.private_input)); i = cfg['subjects'].index('S107'); p = z['xyz_m'][i, 0]; K = z['K'][i]
        np.testing.assert_array_equal(data['K'], K); image = Image.fromarray(data['rgb'])
        page = Image.new('RGB', (image.width * 3, image.height + 80), 'white'); draw = ImageDraw.Draw(page)
        near = cKDTree(data['points_m']).query(p.reshape(-1, 3))[0].reshape(3, 8) * 1000
        for k, method in enumerate(cfg['real_methods']):
            pic = image.copy(); d = ImageDraw.Draw(pic); h = p[k] @ K.T; uv = h[:, :2] / h[:, 2:]
            for j, (x, y) in enumerate(uv):
                c = tuple(int(x * 255) for x in POINT_COLORS[j, :3]); d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=c, outline='black'); d.text((x + 5, y), str(j + 1), fill='yellow')
            page.paste(pic, (k * image.width, 80)); draw.text((k * image.width + 8, 8), f'S107 / {method} / split0', fill='black')
            draw.text((k * image.width + 8, 28), 'Transferred points only; approximate camera', fill='black')
            draw.text((k * image.width + 8, 48), 'No independent target-point truth', fill='black')
        path = a.private_out / 'S107_RGB_POINT_TRANSFER.png'; page.save(path)
        write('PRIVATE_VISUAL_RECORD.json', dict(subject='S107', source_sha256=sha(a.private_input), path=str(path), sha256=sha(path),
            raw_RGB_in_git=False, nearest_all_cloud_mm=near.tolist(), reference='same-source sensor support, NOT point accuracy', other_subjects_RGB='NOT_REGENERATED'))
    write('VISUAL_EXECUTION.json', dict(status='COMPLETE', seconds=time.monotonic() - start, new_figures=82, new_fits=0, new_inferences=0))
    print('VISUAL_COMPLETE', len(out), round(time.monotonic() - start, 2), flush=True)


if __name__ == '__main__':
    main()
