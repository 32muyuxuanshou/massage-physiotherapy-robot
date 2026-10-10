"""Summarize frozen R5 results with raw forward output as the primary result.

Historical frame -> sequence -> identity means are retained. Txyz is diagnostic.
No data fitting, checkpoint selection, or experiment hyperparameter changes.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


METRICS = ['median_mm', 'p95_mm', 'coverage_50mm']
SEEDS = [11, 23, 37]


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def cell_name(cell):
    return cell.removeprefix('repaired__').replace('__', '/')


def hierarchical(rows, accessor):
    identities = {}
    for identity in sorted({r['identity'] for r in rows}):
        rr = [r for r in rows if r['identity'] == identity]
        sequences = {}
        for seq in sorted({r['sequence'] for r in rr}):
            values = [accessor(r) for r in rr if r['sequence'] == seq]
            values = [v for v in values if v is not None]
            if values:
                sequences[seq] = {m: float(np.mean([v[m] for v in values])) for m in METRICS}
        if sequences:
            identities[identity] = {m: float(np.mean([s[m] for s in sequences.values()])) for m in METRICS}
    return dict(per_identity=identities,
                identity_equal_mean={m: float(np.mean([s[m] for s in identities.values()])) for m in METRICS})


def vector_summary(rows, name):
    a = np.asarray([r[name] for r in rows])
    return dict(frames=len(rows), median_xyz_mm=np.median(a, axis=0).tolist(),
                mean_xyz_mm=a.mean(0).tolist(), median_absolute_xyz_mm=np.median(np.abs(a), axis=0).tolist(),
                median_norm_mm=float(np.median(np.linalg.norm(a, axis=1))),
                p95_norm_mm=float(np.quantile(np.linalg.norm(a, axis=1), .95)))


def analyze(source, cache, out):
    out.mkdir(parents=True, exist_ok=True)
    results = {p.stem: load(p) for p in (source/'real_evaluation').glob('*.json')
               if p.stem == 'official' or p.stem.startswith('repaired__')}
    assert len(results) == 16
    official = {r['key']: r for r in results['official']['records']}
    camera_audit = load(cache/'CACHE_CAMERA_AND_FEATURE_AUDIT.json')
    cameras = {(r['cell'], r['key']): r for r in camera_audit['records']}
    frame_rows, identity_rows, overall_rows, regional_rows = [], [], [], []
    frame_maps = {}
    for cell, d in sorted(results.items()):
        assert len(d['records']) == 232 and {r['key'] for r in d['records']} == set(official)
        frame_maps[cell] = {r['key']: r for r in d['records']}
        for role in ['TRAIN', 'VAL']:
            rr = [r for r in d['records'] if r['role'] == role]
            for stage in ['before', 'after']:
                rebuilt = hierarchical(rr, lambda r: r['triangle_'+stage])
                frozen = d['aggregated'][role+'_'+stage]
                for m in METRICS:
                    assert abs(rebuilt['identity_equal_mean'][m]-frozen['identity_equal_mean'][m]) < 1e-9
            o = d['aggregated'][role+'_before']['identity_equal_mean']
            a = d['aggregated'][role+'_after']['identity_equal_mean']
            overall_rows.append(dict(cell=cell_name(cell), role=role, frames=len(rr),
                                     identities=len({r['identity'] for r in rr}),
                                     **{'raw_'+m: o[m] for m in METRICS},
                                     **{'diagnostic_txyz_'+m: a[m] for m in METRICS},
                                     txyz_fallback=sum(r['fallback'] for r in rr)))
            for identity, item in d['aggregated'][role+'_before']['per_identity'].items():
                ref = results['official']['aggregated'][role+'_before']['per_identity'][identity]['metrics']
                ref_t = results['official']['aggregated'][role+'_after']['per_identity'][identity]['metrics']
                raw = item['metrics']
                after = d['aggregated'][role+'_after']['per_identity'][identity]['metrics']
                identity_rows.append(dict(cell=cell_name(cell), role=role, identity=identity,
                                         frames=sum(r['identity'] == identity for r in rr),
                                         sequences=len(item['sequences']),
                                         **{'raw_'+m: raw[m] for m in METRICS},
                                         **{'raw_delta_vs_official_'+m: raw[m]-ref[m] for m in METRICS},
                                         **{'diagnostic_txyz_'+m: after[m] for m in METRICS},
                                         **{'diagnostic_delta_vs_official_txyz_'+m: after[m]-ref_t[m] for m in METRICS}))
            regions = sorted({k for r in rr for k in r['regions_before']})
            for region in regions:
                raw = hierarchical(rr, lambda r: r['regions_before'].get(region))
                after = hierarchical(rr, lambda r: r['regions_after'].get(region))
                regional_rows.append(dict(cell=cell_name(cell), role=role, region=region,
                                          frames_with_points=sum(region in r['regions_before'] for r in rr),
                                          point_count=sum(r['regions_before'].get(region, {}).get('point_count', 0) for r in rr),
                                          **{'raw_'+m: raw['identity_equal_mean'][m] for m in METRICS},
                                          **{'diagnostic_txyz_'+m: after['identity_equal_mean'][m] for m in METRICS}))
        for r in d['records']:
            ref = official[r['key']]
            cr = cameras.get((cell, r['key']))
            row = dict(cell=cell_name(cell), key=r['key'], role=r['role'], identity=r['identity'],
                       sequence=r['sequence'], frame=r['frame'], points=r['triangle_before']['point_count'],
                       **{'raw_'+m: r['triangle_before'][m] for m in METRICS},
                       **{'official_raw_'+m: ref['triangle_before'][m] for m in METRICS},
                       **{'raw_delta_vs_official_'+m: r['triangle_before'][m]-ref['triangle_before'][m] for m in METRICS},
                       **{'diagnostic_txyz_'+m: r['triangle_after'][m] for m in METRICS},
                       diagnostic_txyz_fallback=r['fallback'], official_txyz_fallback=ref['fallback'])
            for field, values in [('model_delta', cr['model_delta_xyz_mm'] if cr else [0]*3),
                                  ('diagnostic_A_txyz', cr['diagnostic_A_txyz_xyz_mm'] if cr else np.asarray(r['applied_translation_m'])*1000),
                                  ('diagnostic_endpoint_difference', cr['diagnostic_endpoint_difference_xyz_mm'] if cr else [0]*3)]:
                for axis, value in zip('xyz', values):
                    row[field+'_'+axis+'_mm'] = float(value)
            row['Body_parameters_changed'] = False
            frame_rows.append(row)
    write_csv(out/'ALL_REAL_FRAMES.csv', frame_rows)
    write_csv(out/'ALL_REAL_IDENTITIES.csv', identity_rows)
    write_csv(out/'ALL_REAL_MODELS.csv', overall_rows)
    write_csv(out/'ALL_REAL_REGIONS.csv', regional_rows)
    main_frames = [r for r in frame_rows if r['cell'].startswith('continuation/mixed')]
    write_csv(out/'MIXED_RAW_FRAMES.csv', main_frames)
    per_frame_regions = []
    for cell, report in results.items():
        if not cell.startswith('repaired__continuation__mixed'):
            continue
        for r in report['records']:
            for region, metric in r['regions_before'].items():
                ref = official[r['key']]['regions_before'][region]
                per_frame_regions.append(dict(cell=cell_name(cell), key=r['key'], identity=r['identity'],
                                              role=r['role'], region=region, points=metric['point_count'],
                                              **{'raw_'+m:metric[m] for m in METRICS},
                                              **{'official_raw_'+m:ref[m] for m in METRICS},
                                              **{'delta_vs_official_'+m:metric[m]-ref[m] for m in METRICS}))
    write_csv(out/'MIXED_FRAME_REGIONS.csv', per_frame_regions)
    main_ids = [r for r in identity_rows if r['cell'].startswith('continuation/mixed')]
    write_csv(out/'MIXED_RAW_IDENTITIES.csv', main_ids)
    main_cameras = [r for r in camera_audit['records'] if r['cell'].startswith('repaired__continuation__mixed')]
    axis_audit = []
    for cell in sorted({r['cell'] for r in main_cameras}):
        for identity in sorted({r['identity'] for r in main_cameras}):
            rr = [r for r in main_cameras if r['cell'] == cell and r['identity'] == identity]
            axis_audit.append(dict(cell=cell_name(cell), identity=identity, role=rr[0]['role'],
                                   model_change=vector_summary(rr, 'model_delta_xyz_mm'),
                                   diagnostic_A_fit=vector_summary(rr, 'diagnostic_A_txyz_xyz_mm'),
                                   diagnostic_endpoint_difference=vector_summary(rr, 'diagnostic_endpoint_difference_xyz_mm')))
    write_json(out/'CAMERA_AXIS_BY_IDENTITY.json', axis_audit)
    training, curves, synthetic_axes, exposures = [], [], [], []
    for stage, directory in [('native', 'native_results'), ('continuation', 'continuation_results')]:
        for folder in sorted((source/directory).iterdir()):
            if not folder.is_dir():
                continue
            result = load(folder/'RESULTS.json'); cc = load(folder/'CURVES.json')
            name = stage+'/'+folder.name
            best = min(cc, key=lambda r: r['val']['camera_mean_mm'])
            training.append(dict(cell=name, epochs_run=len(cc), total_native_epochs=30 if stage == 'native' else 50,
                                 updates=6000 if stage == 'native' else 10000,
                                 best_epoch_in_this_stage=best['epoch'], best_native_val_camera_mm=best['val']['camera_mean_mm'],
                                 last_native_val_camera_mm=cc[-1]['val']['camera_mean_mm'],
                                 last_5_epoch_improvement_mm=cc[-5]['val']['camera_mean_mm']-cc[-1]['val']['camera_mean_mm'],
                                 first_lr=cc[0]['lr'], max_lr=max(r['lr'] for r in cc), last_lr=cc[-1]['lr'],
                                 first_native_loss=cc[0].get('loss', cc[0].get('native_loss')),
                                 last_native_loss=cc[-1].get('loss', cc[-1].get('native_loss')),
                                 last_weak_loss=cc[-1].get('weak_loss'),
                                 **result['best']['identity_equal_mean']))
            for r in cc:
                curves.append(dict(cell=name, epoch=r['epoch'], lr=r['lr'],
                                   native_loss=r.get('loss', r.get('native_loss')),
                                   weak_loss=r.get('weak_loss'), native_val_camera_mm=r['val']['camera_mean_mm']))
            errors = np.asarray([r['camera_xyz_error_mm'] for r in result['best']['records']])
            mse = (errors**2).mean(0)
            synthetic_axes.append(dict(cell=name, samples=len(errors), bias_xyz_mm=errors.mean(0).tolist(),
                                       mean_absolute_xyz_mm=np.abs(errors).mean(0).tolist(),
                                       rmse_xyz_mm=np.sqrt(mse).tolist(), xyz_squared_error_fraction=(mse/mse.sum()).tolist(),
                                       evidence='native synthetic root GT; not HuMMan sensor surface error'))
            if folder.name.startswith('mixed'):
                visits = load(folder/'SCAN_EXPOSURE.json')
                counts = np.asarray([r['count'] for r in visits])
                exposures.append(dict(seed=int(folder.name.split('_s')[1]), draws=int(counts.sum()), unique_seen=int((counts>0).sum()),
                                      unseen=int((counts==0).sum()), train_rows=len(counts), mean_visits=float(counts.mean()),
                                      min_visits=int(counts.min()), max_visits=int(counts.max()),
                                      interpretation='800 scan draws/native epoch; not a full scan-data epoch'))
    write_csv(out/'TRAINING_AUDIT.csv', training); write_csv(out/'ALL_TRAINING_CURVES.csv', curves)
    write_json(out/'SYNTHETIC_TRUE_CAMERA_AXIS_ERRORS.json', synthetic_axes)
    write_json(out/'SCAN_ACTUAL_EXPOSURE.json', exposures)
    dataset_rows, dataset_summary = [], {}
    for name, filename in [('native', 'NATIVE_COMPACT_MANIFEST.json'), ('scan', 'SCAN_COMPACT_MANIFEST.json'), ('real', 'REAL_COMPACT_MANIFEST.json')]:
        mm = load(source/'data_manifests'/filename)['records']
        per = defaultdict(Counter)
        for r in mm:
            per[r['identity']][r['role']] += 1
        for identity, counts in sorted(per.items()):
            assert len(counts) == 1
            role, n = next(iter(counts.items()))
            dataset_rows.append(dict(dataset=name, identity=identity, role=role, rows=n,
                                     used_for_optimization=name != 'real' and role == 'TRAIN',
                                     used_for_best_checkpoint_selection=name == 'native' and role == 'VAL'))
        dataset_summary[name] = dict(rows=len(mm), roles={role:dict(rows=sum(r['role'] == role for r in mm), identities=sorted({r['identity'] for r in mm if r['role'] == role})) for role in sorted({r['role'] for r in mm})})
        if name == 'scan':
            dataset_summary[name].update(source_meshes=len({r['asset_id'] for r in mm}),
                                         camera_configs_per_mesh=len({r['view']['camera_id'] for r in mm}),
                                         truncated_retained=sum(r['image_truncated'] for r in mm),
                                         views={k:sorted({r['view'][k] for r in mm}) for k in ['distance_m','yaw_deg','elevation_deg','roll_deg','focal_px','group']})
    write_csv(out/'DATASET_IDENTITY_ROLES.csv', dataset_rows)
    write_json(out/'DATASET_USAGE.json', dataset_summary)
    shutil.copy2(cache/'CACHE_CAMERA_AND_FEATURE_AUDIT.json', out/'CACHE_CAMERA_AND_FEATURE_AUDIT.json')
    shutil.copy2(cache/'VALID_FRACTION_SENSITIVITY.json', out/'VALID_FRACTION_SENSITIVITY.json')
    subgroup = []
    for seed in SEEDS:
        cell = f'repaired__continuation__mixed_s{seed}'
        for role in ['TRAIN', 'VAL']:
            rr = [r for r in results[cell]['records'] if r['role'] == role]
            ids = [r for r in main_ids if r['cell'] == cell_name(cell) and r['role'] == role]
            subgroup.append(dict(seed=seed, role=role, frames=len(rr), identities=len(ids),
                                  frame_median_worse_than_official=sum(r['triangle_before']['median_mm']>official[r['key']]['triangle_before']['median_mm'] for r in rr),
                                  frame_p95_worse_than_official=sum(r['triangle_before']['p95_mm']>official[r['key']]['triangle_before']['p95_mm'] for r in rr),
                                  identity_median_worse_than_official=sum(r['raw_delta_vs_official_median_mm']>0 for r in ids),
                                  identity_p95_worse_than_official=sum(r['raw_delta_vs_official_p95_mm']>0 for r in ids)))
    worst = {str(seed): sorted([r for r in main_frames if r['cell'].endswith(f'_s{seed}')], key=lambda r: r['raw_p95_mm'], reverse=True)[:10] for seed in SEEDS}
    groups = {}
    for mode in ['native/metric_xyz', 'continuation/native_only', 'continuation/mixed']:
        groups[mode] = {}
        for role in ['TRAIN', 'VAL']:
            rr = [r for r in overall_rows if r['cell'].startswith(mode+'_s') and r['role'] == role]
            groups[mode][role] = {m:dict(mean=float(np.mean([r['raw_'+m] for r in rr])), seed_sample_std=float(np.std([r['raw_'+m] for r in rr], ddof=1))) for m in METRICS}
    summary = dict(status='ANALYZED', primary='raw forward predictions, no Txyz',
                   real_metric='fixed Camera B 2048 points/frame -> exact nearest triangle -> frame/sequence/identity arithmetic means',
                   source_delivery_commit='be5a0f2a585fcd313789ee1ff4e8da8b683b8b08',
                   groups=groups, worsening_counts=subgroup, worst_P95_frames=worst,
                   all_frame_rows=len(frame_rows), all_identity_rows=len(identity_rows),
                   cache_audit_frames=camera_audit['caches_checked'],
                   training=training, test_read=False, new_training=False, fitting=False,
                   note='A-fit correction is supporting diagnostic, not GT Camera error or the proposed final model')
    write_json(out/'ANALYSIS_SUMMARY.json', summary)
    numerical_appendix(out, overall_rows, identity_rows, training, axis_audit, regional_rows)
    lines = ['# 每个seed的严重失败帧', '', '按raw P95排序，仅用于阅读；全帧见CSV，不用这些结果筛选训练/评价样本。位置变化是相对Official，负Z是向相机移动，不是GT误差。', '']
    for role in ['VAL', 'TRAIN']:
        for seed in SEEDS:
            selected=sorted([r for r in main_frames if r['cell'].endswith(f'_s{seed}') and r['role']==role], key=lambda r:r['raw_p95_mm'],reverse=True)[:10]
            lines += [f'## {role} seed{seed}', '', '|帧|Official raw median/P95|新raw median/P95|ΔX/ΔY/ΔZ mm|', '|---|---:|---:|---:|']
            for r in selected:
                xyz=' / '.join(f"{r['model_delta_'+axis+'_mm']:.2f}" for axis in 'xyz')
                lines.append(f"|{r['key']}|{r['official_raw_median_mm']:.2f} / {r['official_raw_p95_mm']:.2f}|{r['raw_median_mm']:.2f} / {r['raw_p95_mm']:.2f}|{xyz}|")
            lines.append('')
    (out/'WORST_FRAMES.md').write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
    plots(source, out, results, main_ids, main_frames, curves, camera_audit)
    print(json.dumps(dict(status='PASS', frame_rows=len(frame_rows), identity_rows=len(identity_rows), training_cells=len(training), figures=5)))


def numerical_appendix(out, overall, identities, training, axes, regions):
    lines = ['# 完整数值附录', '', '所有新模型主结果均为 raw，不加 Txyz。距离单位 mm；coverage 是比例。median/P95 均为既有层级均值，不是合并点集的分位数。', '',
             '## 全部模型与种子', '', '|模型|角色|raw median|raw P95|≤50mm %|诊断 +Txyz median|诊断 +Txyz P95|fallback|', '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in overall:
        lines.append(f"|{r['cell']}|{r['role']}|{r['raw_median_mm']:.3f}|{r['raw_p95_mm']:.3f}|{r['raw_coverage_50mm']*100:.2f}|{r['diagnostic_txyz_median_mm']:.3f}|{r['diagnostic_txyz_p95_mm']:.3f}|{r['txyz_fallback']}|")
    for role in ['VAL', 'TRAIN']:
        lines += ['', f'## 主新模型：{role} 每人对照', '', '每个单元格为 median / P95。三个 seed 没有挑选或删除。', '',
                  '|身份|帧数|Official raw|Official+Txyz 基线|新 raw seed11|新 raw seed23|新 raw seed37|', '|---|---:|---:|---:|---:|---:|---:|']
        for identity in sorted({r['identity'] for r in identities if r['role']==role}):
            lookup = {r['cell']:r for r in identities if r['identity']==identity}
            o = lookup['official']
            values = [f"{o['raw_median_mm']:.2f} / {o['raw_p95_mm']:.2f}", f"{o['diagnostic_txyz_median_mm']:.2f} / {o['diagnostic_txyz_p95_mm']:.2f}"]
            for seed in SEEDS:
                r = lookup[f'continuation/mixed_s{seed}'];values.append(f"{r['raw_median_mm']:.2f} / {r['raw_p95_mm']:.2f}")
            lines.append('|'+identity+'|'+str(o['frames'])+'|'+'|'.join(values)+'|')
    lines += ['', '## 训练逐 cell', '', 'native 为第一阶段30轮；continuation 为额外20轮，总计50轮 native 曝光。best epoch 是当前阶段编号。', '',
              '|cell|本阶段轮次|best epoch|合成 VAL best Camera|last Camera|最后5轮改善|首LR|最高LR|末LR|', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in training:
        lines.append(f"|{r['cell']}|{r['epochs_run']}|{r['best_epoch_in_this_stage']}|{r['best_native_val_camera_mm']:.3f}|{r['last_native_val_camera_mm']:.3f}|{r['last_5_epoch_improvement_mm']:.3f}|{r['first_lr']:.7f}|{r['max_lr']:.7f}|{r['last_lr']:.7f}|")
    lines += ['', '## 主新模型每人的实际 Camera 变化', '', '每单元格为帧中位 ΔX / ΔY / ΔZ，单位 mm，相对 Official。负Z=向 A 相机移动。这是实际模型变化，不是相对真值的三轴误差；对每帧算向量后才统计。', '',
              '|身份|角色|seed11 XYZ|seed23 XYZ|seed37 XYZ|', '|---|---|---:|---:|---:|']
    for identity in sorted({r['identity'] for r in axes}):
        rr = {r['cell']:r for r in axes if r['identity']==identity}
        first = next(iter(rr.values())); values=[]
        for seed in SEEDS:
            values.append(' / '.join(f'{v:.2f}' for v in rr[f'continuation/mixed_s{seed}']['model_change']['median_xyz_mm']))
        lines.append('|'+identity+'|'+first['role']+'|'+'|'.join(values)+'|')
    lines += ['', '## 真实 VAL 分区 raw 误差', '', '旧固定 proxy 标签；不等于纯后背解剖分区。每单元格 median / P95，单位 mm。', '',
              '|分区|Official raw|seed11 raw|seed23 raw|seed37 raw|', '|---|---:|---:|---:|---:|']
    for region in sorted({r['region'] for r in regions}):
        lookup = {r['cell']:r for r in regions if r['role']=='VAL' and r['region']==region}
        values=[]
        for cell in ['official']+[f'continuation/mixed_s{s}' for s in SEEDS]:
            r=lookup[cell];values.append(f"{r['raw_median_mm']:.2f} / {r['raw_p95_mm']:.2f}")
        lines.append('|'+region+'|'+'|'.join(values)+'|')
    (out/'NUMERICAL_APPENDIX.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def plots(source, out, results, identities, frames, curves, audit):
    plt.rcParams.update({'font.size': 10})
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    ids = ['p001194', 'p001196', 'p001199', 'p001201']
    for ax, metric in zip(axes, ['median_mm', 'p95_mm']):
        for i, (cell, label, color) in enumerate([('official', 'Official raw', '#666666')]+[(f'repaired__continuation__mixed_s{s}',f'New raw seed{s}',c) for s,c in zip(SEEDS,['#ca6129','#488a52','#437fc0'])]):
            values = [results[cell]['aggregated']['VAL_before']['per_identity'][k]['metrics'][metric] for k in ids]
            ax.bar(np.arange(4)+(i-1.5)*.18, values, .18, label=label, color=color)
        baseline = [results['official']['aggregated']['VAL_after']['per_identity'][k]['metrics'][metric] for k in ids]
        ax.plot(np.arange(4), baseline, 'kD--', label='Official + Txyz baseline')
        ax.set_xticks(np.arange(4), ids); ax.set_ylabel('mm'); ax.set_title('Independent B: '+metric); ax.grid(axis='y', alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('Same frozen Body; only Camera translation changes | VAL = 4 consumed development identities')
    fig.savefig(out/'RAW_VAL_BY_IDENTITY.png', dpi=150); plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(16, 7), layout='constrained')
    allids = sorted({r['identity'] for r in identities})
    for ax, metric in zip(axes, ['median_mm', 'p95_mm']):
        for i, seed in enumerate(SEEDS):
            lookup = {r['identity']:r for r in identities if r['cell'].endswith(f'_s{seed}')}
            values = [lookup[k]['raw_delta_vs_official_'+metric] for k in allids]
            ax.bar(np.arange(len(allids))+(i-1)*.22, values, .22, label=f'seed {seed}')
        ax.axhline(0, color='black', lw=1); ax.set_ylabel('New raw - Official raw, mm'); ax.set_title(metric+' | negative improves, positive worsens')
        ax.set_xticks(np.arange(len(allids)), allids, rotation=55, ha='right'); ax.legend()
    fig.savefig(out/'ALL_IDENTITY_RAW_CHANGES.png', dpi=140); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5), layout='constrained')
    for ax, seed in zip(axes, SEEDS):
        c = [r for r in curves if r['cell']==f'native/metric_xyz_s{seed}']
        ax.plot([r['epoch'] for r in c], [r['native_val_camera_mm'] for r in c], color='gray', label='Native first30')
        for mode, color in [('native_only','#488a52'),('mixed','#ca6129')]:
            cc = [r for r in curves if r['cell']==f'continuation/{mode}_s{seed}']
            ax.plot([r['epoch']+30 for r in cc], [r['native_val_camera_mm'] for r in cc], color=color, label=mode+' extra20')
        ax.axvline(30, color='black', ls='--', alpha=.5); ax.set_title(f'Seed {seed} | LR reset at31'); ax.set_xlabel('Native data epochs'); ax.set_ylabel('Synthetic GT Camera L2 mm'); ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.savefig(out/'TRAINING_CONVERGENCE.png', dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5), layout='constrained')
    for ax, seed in zip(axes, SEEDS):
        for role, marker in [('TRAIN','o'),('VAL','x')]:
            rr = [r for r in frames if r['cell'].endswith(f'_s{seed}') and r['role']==role]
            ax.scatter([r['model_delta_z_mm'] for r in rr], [r['raw_delta_vs_official_median_mm'] for r in rr], s=25, alpha=.7, marker=marker, label=role)
        ax.axhline(0, color='black', lw=.8); ax.set_title(f'Seed {seed}'); ax.set_xlabel('Camera A Z movement from Official, mm'); ax.set_ylabel('B median change vs Official, mm'); ax.grid(alpha=.2); ax.legend()
    fig.suptitle('Moving closer can rescue large errors and damage good frames; movement is not GT Camera error')
    fig.savefig(out/'DEPTH_MOVEMENT_AND_ERROR.png', dpi=150); plt.close(fig)
    f = audit['feature_distributions'][12]
    fig, ax = plt.subplots(figsize=(9, 4), layout='constrained')
    for i, (name,label,color) in enumerate([('native','Native TRAIN (3200)','#488a52'),('scan','Textured scan TRAIN (2304)','#437fc0'),('real','Real development (232)','#ca6129')]):
        stat = f[name]
        ax.plot([stat['min']*100,stat['max']*100],[i,i], color=color, lw=3)
        ax.plot([stat['q05']*100,stat['q95']*100],[i,i], color=color, lw=10, alpha=.5)
        ax.plot(stat['median']*100,i,'ko');ax.text(stat['max']*100+1,i,f"median {stat['median']*100:.2f}%", va='center')
    ax.set_yticks(range(3),['Native TRAIN','Scan TRAIN','Real A input']); ax.set_xlabel('Valid Depth pixels / whole network crop (%)'); ax.set_title('Input support mismatch: 232/232 real frames below native TRAIN range'); ax.set_xlim(left=0); ax.grid(axis='x',alpha=.2)
    fig.savefig(out/'VALID_DEPTH_DISTRIBUTION.png', dpi=150); plt.close(fig)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--cache-audit', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); analyze(a.source, a.cache_audit, a.out)
