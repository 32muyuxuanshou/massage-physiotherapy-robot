"""Read-only cache replay, case tables and complete contact sheets; no new fitting."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from replay_delivery import surface

ROOT = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def montage(folder, prefix):
    files = sorted(folder.glob('*.png'))
    pages = []
    for start in range(0, len(files), 6):
        canvas = Image.new('RGB', (1800, 1500), 'white')
        for k, path in enumerate(files[start:start+6]):
            im = Image.open(path).convert('RGB'); im.thumbnail((880, 450))
            x = (k % 2)*900; y = (k // 2)*500
            canvas.paste(im, (x+(900-im.width)//2, y+30))
            ImageDraw.Draw(canvas).text((x+12, y+8), path.stem, fill='black')
        dest = ROOT/'montages'/f'{prefix}_{start//6+1:02d}.jpg'
        dest.parent.mkdir(exist_ok=True); canvas.save(dest, quality=88)
        pages.append(str(dest.relative_to(ROOT)))
    return pages


def main():
    manifest = json.loads((ROOT/'CASE_MANIFEST.json').read_text())
    inputs = {r['subject']: dict(np.load(ROOT/'inputs'/(r['subject']+'.npz'))) for r in manifest}
    reference = json.loads((ROOT/'REFERENCE_ASSIST_RESULTS.json').read_text())
    evaluated = 0
    for row in reference['records']:
        path = ROOT/'reference_predictions'/Path(row['path']).name
        assert sha(path) == row['cache_sha256']
        cache = dict(np.load(path)); data = inputs[row['subject']]
        mask = data['target_valid'].copy(); mask[[1, 4]] = False
        assert np.array_equal(mask, cache['evaluation_mask'])
        assert np.array_equal(cache['reference_xyz_mm'], data['target_xyz_mm'][[1, 4]])
        error = np.linalg.norm((cache['pred_uv']-data['target_uv'])*np.diff(data['xz_bounds_mm'].reshape(2, 2), axis=1).ravel(), axis=1)
        assert np.allclose(error, cache['xz_error_mm'], rtol=0, atol=1e-6)
        assert abs(error[mask].mean()-row['mean_xz_mm']) < 1e-6
        for i, uv in enumerate(cache['pred_uv']):
            xyz = surface(uv, data)
            assert bool(cache['surface_hit'][i]) == (xyz is not None)
            if xyz is not None:
                assert np.allclose(xyz, cache['pred_xyz_mm'][i], rtol=0, atol=1e-6)
        evaluated += int(mask.sum())
    methods = sorted({r['method'] for r in reference['records']})
    case_rows = []
    for m in manifest:
        row = {'subject': m['subject'], 'coordinate_group': 'native_world' if m['native_world_validated'] else 'export_diagnostic'}
        for method in methods:
            values = [r['mean_xz_mm'] for r in reference['records'] if r['subject'] == m['subject'] and r['method'] == method]
            row[method] = float(np.median(values))
        case_rows.append(row)
    with (ROOT/'REFERENCE_CASE_TABLE.csv').open('w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=list(case_rows[0])); writer.writeheader(); writer.writerows(case_rows)
    for group in ['all_source', 'native_world', 'export_diagnostic']:
        rows = [r for r in case_rows if group == 'all_source' or r['coordinate_group'] == group]
        for method in methods:
            mean = np.mean([r[method] for r in rows])
            assert abs(mean-reference['summary'][group][method]['case_equal_mean_xz_mm']) < 1e-6
    # Recreate qualification images solely from committed caches with explicit frame labels.
    folder = ROOT/'qualification_review'; folder.mkdir(exist_ok=True)
    for row in manifest:
        data = inputs[row['subject']]; b = data['xz_bounds_mm']; uv = data['target_uv']; xyz = data['target_xyz_mm']; ok = data['target_valid']
        fig, ax = plt.subplots(figsize=(6, 7))
        ax.imshow(np.ma.masked_where(~data['surface_valid'], data['surface_height_mm']), cmap='viridis', extent=[b[0], b[1], b[2], b[3]], origin='upper')
        ax.scatter(xyz[ok, 0], xyz[ok, 2], c='red', s=25)
        for k, name in enumerate(['C7', 'T3', 'T5', 'T9', 'L2']):
            if ok[k]: ax.text(xyz[k, 0]+5, xyz[k, 2], name, color='white')
        label = 'RAS world' if row['native_world_validated'] else 'Export frame; world orientation unvalidated'
        ax.set_title(row['subject']+'\n'+label+' / CT-to-skin proxies')
        ax.set_xlabel('source X (mm)'); ax.set_ylabel('source Z (mm)'); fig.tight_layout()
        fig.savefig(folder/(row['subject']+'.png'), dpi=120); plt.close(fig)
    pages = montage(ROOT/'figures', 'external')+montage(ROOT/'reference_figures', 'references')+montage(folder, 'source')
    result = dict(status='PASS', reference_caches=len(reference['records']), held_out_target_evaluations=evaluated,
                  two_input_reference_levels_excluded=True, group_aggregation_replayed=True,
                  montage_pages=pages, montage_cases_per_group=len(manifest), source_png_label_correction_only=True,
                  scope='Actual cache hashes/positions/surface/metrics, no model execution or fitting')
    (ROOT/'REFERENCE_DELIVERY_REPLAY.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
