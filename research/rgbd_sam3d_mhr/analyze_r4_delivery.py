"""Read-only paired R4 diagnostics from delivered full result tables."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def stats(values):
    return dict(mean=float(np.mean(values)), sample_std=float(np.std(values, ddof=1)), values=values)


def main(d, baseline):
    summary = read(d / 'summary/R4_SUMMARY.json')
    cheap = read(baseline)['methods']['official']
    official, txyz = cheap['before'], cheap['after']
    report = dict(test_used=False, checkpoint_selection='synthetic VAL only',
                  aggregation='frame metrics -> sequence mean -> equal identity mean; then mean/sample SD over seeds',
                  warning='Real Camera B is surface observation, not root Camera GT or anatomical/acupoint GT.',
                  baselines=dict(Official=official, Official_Txyz=txyz), paired={}, physical={}, depth={}, attribution={})
    rows, identity_rows = [], []
    for seed in [11, 23, 37]:
        a = read(d / f'formal/g0_seed{seed}/real/HUMMAN_RESULTS.json')
        b = read(d / f'formal/g1_seed{seed}/real/HUMMAN_RESULTS.json')
        assert a['heldout_points_manifest_sha256'] == b['heldout_points_manifest_sha256']
        report['paired'][str(seed)] = {}
        for role in ['TRAIN', 'VAL']:
            ar, br = a['results'][role], b['results'][role]
            ai = {(r['sequence'], r['frame']): r for r in ar['records']}
            bi = {(r['sequence'], r['frame']): r for r in br['records']}
            assert set(ai) == set(bi)
            assert len(ai) == (192 if role == 'TRAIN' else 40)
            frame_rows = []
            for key in ai:
                x, y = ai[key], bi[key]
                delta = {k: y['triangle'][k] - x['triangle'][k] for k in ['median_mm', 'p95_mm', 'coverage_50mm']}
                r = dict(seed=seed, role=role, identity=x['identity'], sequence=key[0], frame=key[1],
                         g0=x['triangle'], g1=y['triangle'], delta_g1_minus_g0=delta)
                rows.append(r); frame_rows.append(r)
            identities = []
            for identity, x in ar['per_identity'].items():
                y = br['per_identity'][identity]
                delta = {k: y['metrics'][k] - x['metrics'][k] for k in x['metrics']}
                r = dict(seed=seed, role=role, identity=identity, g0=x['metrics'], g1=y['metrics'], delta_g1_minus_g0=delta,
                         official=official[role]['per_identity'][identity]['metrics'],
                         official_txyz=txyz[role]['per_identity'][identity]['metrics'])
                identities.append(r); identity_rows.append(r)
            report['paired'][str(seed)][role] = dict(frame_count=len(frame_rows), identity_count=len(identities),
                aggregate_g0=ar['identity_equal_mean'], aggregate_g1=br['identity_equal_mean'],
                median_improved_frames=sum(r['delta_g1_minus_g0']['median_mm'] < 0 for r in frame_rows),
                p95_worse_frames=sum(r['delta_g1_minus_g0']['p95_mm'] > 0 for r in frame_rows),
                p95_worse_over5mm_frames=sum(r['delta_g1_minus_g0']['p95_mm'] > 5 for r in frame_rows),
                p95_over150mm_frames_g0=sum(r['g0']['p95_mm'] > 150 for r in frame_rows),
                p95_over150mm_frames_g1=sum(r['g1']['p95_mm'] > 150 for r in frame_rows),
                p95_improved_identities=sum(r['delta_g1_minus_g0']['p95_mm'] < 0 for r in identities),
                identities=identities)
        attribution = d / f'formal_camera_attribution_seed{seed}.json'
        if attribution.exists():
            x = read(attribution)
            report['attribution'][str(seed)] = {method: {role: result['identity_equal_mean'] for role, result in rr.items()}
                                                for method, rr in x['results'].items()}
    report['all_paired_frames'] = rows
    report['all_paired_identities'] = identity_rows
    for mode in ['g0', 'g1']:
        physical = [read(d / f'formal/{mode}_seed{s}/physical.json')['identity_equal_mean'] for s in [11, 23, 37]]
        report['physical'][mode] = {k: stats([p[k] for p in physical]) for k in physical[0]}
        report['depth'][mode] = {}
        for domain in ['synthetic_VAL', 'real_TRAIN_VAL']:
            cells = [read(d / f'formal/{mode}_seed{s}/ablations/DEPTH_ABLATIONS.json')['conditions'][domain] for s in [11, 23, 37]]
            report['depth'][mode][domain] = {}
            for condition in cells[0]:
                entry = dict(response={role: {k: stats([x[condition]['responses'][role][k] for x in cells])
                                               for k in cells[0][condition]['responses'][role]
                                               if k != 'camera_change_xyz_mm'}
                                       for role in cells[0][condition]['responses']})
                entry['signed_camera_xyz_mm'] = {role: [stats([x[condition]['responses'][role]['camera_change_xyz_mm'][i] for x in cells])
                                                          for i in range(3)] for role in cells[0][condition]['responses']}
                if domain == 'synthetic_VAL':
                    entry['pve_mm'] = stats([x[condition]['synthetic']['identity_equal_mean']['vertex_camera_mm'] for x in cells])
                report['depth'][mode][domain][condition] = entry
    (d / 'FINAL_DIAGNOSTICS.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = ['# 三个配对 seed：全部逐人对照', '', 'Δ = G1 − G0；距离负值为改善。所有失败样本保留。', '',
             '|Seed|Role|Identity|G0 med/P95|G1 med/P95|Δ med/P95|Official+Txyz med/P95|', '|---|---|---|---:|---:|---:|---:|']
    pair = lambda r: '/'.join(f'{r[k]:.2f}' for k in ['median_mm', 'p95_mm'])
    for r in identity_rows:
        lines.append(f"|{r['seed']}|{r['role']}|{r['identity']}|{pair(r['g0'])}|{pair(r['g1'])}|{pair(r['delta_g1_minus_g0'])}|{pair(r['official_txyz'])}|")
    (d / 'PER_IDENTITY_REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    out = d / 'summary'
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), layout='constrained')
    specs = [('Synthetic camera-frame PVE', 'synthetic', None, 'vertex_camera_mm'),
             ('Real VAL: independent B median', 'real', 'VAL', 'median_mm'),
             ('Real VAL: independent B P95', 'real', 'VAL', 'p95_mm')]
    for ax, (title, domain, role, key) in zip(axes, specs):
        for i, mode in enumerate(['g0', 'g1']):
            x = summary['multiseed'][mode][domain]
            if role: x = x[role]
            ax.bar(i, x[key]['mean'], yerr=x[key]['sample_std'], color=['#728b9c', '#1eaa92'][i], capsize=5, alpha=.7)
            values = [summary['formal'][f'{mode}_seed{s}'][('best' if domain == 'synthetic' else 'real')] for s in [11, 23, 37]]
            ys = [v[key] if role is None else v[role][key] for v in values]
            ax.scatter([i-.08, i, i+.08], ys, color='black', s=18, zorder=5)
        if role:
            ax.axhline(txyz[role]['identity_equal_mean'][key], color='#ba4a00', linestyle='--', label='Official+Txyz')
            ax.legend(fontsize=8)
        ax.set_xticks([0, 1], ['G0', 'G1']); ax.set_title(title); ax.set_ylabel('mm'); ax.grid(axis='y', alpha=.2)
    fig.suptitle('Three paired training seeds: mean +/- sample SD (development evidence)')
    fig.savefig(out / 'FORMAL_MULTI_SEED_COMPARISON.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    for ax, role in zip(axes, ['TRAIN', 'VAL']):
        for seed, colour in zip([11, 23, 37], ['#2374ab', '#1eaa92', '#c45b30']):
            rr = [r for r in identity_rows if r['role'] == role and r['seed'] == seed]
            ax.scatter([r['g0']['p95_mm'] for r in rr], [r['g1']['p95_mm'] for r in rr], label=f'seed{seed}', color=colour)
            for r in rr:
                if r['identity'] == 'p001196': ax.annotate('p001196', (r['g0']['p95_mm'], r['g1']['p95_mm']), fontsize=8)
        ax.axline((0, 0), slope=1, color='gray', linestyle='--'); ax.set_title(role+' identity-level P95')
        ax.set_xlabel('G0 (mm)'); ax.set_ylabel('G1 (mm), above line = worse'); ax.legend(); ax.grid(alpha=.2)
    fig.savefig(out / 'FORMAL_TAIL_BY_IDENTITY.png', dpi=160); plt.close(fig)
    print('FINAL_DIAGNOSTICS_COMPLETE', len(rows), 'paired frame records')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--delivery', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    a = p.parse_args()
    main(a.delivery, a.baseline)
