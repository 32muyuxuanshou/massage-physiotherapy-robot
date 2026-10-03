"""Package completed outputs for review. No inference, optimization, or metric change."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def files_manifest(root):
    rows = [dict(path=p.relative_to(root).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(root.rglob('*')) if p.is_file()
            and '__pycache__' not in p.parts and p.name != 'FILES_MANIFEST.json']
    write(root / 'FILES_MANIFEST.json', dict(files=rows, self_excluded=True))


def package(workspace):
    delivery = workspace / 'docs/handoffs/real-scene-2026-10-03/prone-back-point-validation-v1'
    source = workspace / 'output/prone_back_point_validation_v1'
    names = dict(p0='p0_assets', p1='p1_cached_transfer',
                 p2='p2_behave_crossview', p4='p4_rule_comparison')
    for token, folder in names.items():
        for path in (source / folder).iterdir():
            if path.suffix in ('.json', '.jsonl', '.csv'):
                copy(path, delivery / 'results' / token / path.name)
    for path in (source / 'assets').glob('*.json'):
        copy(path, delivery / 'results/config' / path.name)
    for path in (source / 'p4_rule_comparison/reference_frames').rglob('*.json'):
        copy(path, delivery / 'results/p4/reference_frames' / path.relative_to(source / 'p4_rule_comparison/reference_frames'))

    p3 = source / 'p3_data_qualification'
    dst = delivery / 'results/p3'
    for name in ('IMAGE_LABEL_IDENTITY_AUDIT.json', 'DMD_205_VISUAL_QUALIFICATION.csv',
                 'DMD_VISUAL_REVIEW.json', 'DMD_EMBEDDED_PIXEL_DIAGNOSIS.json',
                 'PCDARE_UNIT_AND_PROVENANCE.json'):
        copy(p3 / name, dst / name)
    labels = Counter()
    for row in read(p3 / 'IMAGE_LABEL_IDENTITY_AUDIT.json')['rows']:
        labels.update(row['point_label_counts'])
    write(dst / 'DMD_POINT_CLASS_INVENTORY.json', dict(
        distinct_raw_labels=len(labels), raw_label_point_counts=dict(sorted(labels.items())),
        medical_names_normalized=False, training_approved=False,
        note='Original spellings retained; back/rushu and suspected typos have no automatic medical mapping.'))
    scans = csv_rows(p3 / 'SCAN_REFERENCE_BINDING.csv')
    fields = [k for k in scans[0] if k not in ('path', 'matching_json_paths')]
    with (dst / 'SCAN_REFERENCE_BINDING_PUBLIC.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: row[k] for k in fields} for row in scans)
    candidates = read(p3 / 'SCAN_REFERENCE_CANDIDATES.json')
    public = [dict(candidate_id=f'candidate_{i:04d}', **{k: v for k, v in row.items() if k != 'json_path'})
              for i, row in enumerate(candidates)]
    write(dst / 'SCAN_REFERENCE_CANDIDATES_PUBLIC.json', public)
    lookup = {(r['scan_id'], r['json_sha256']): f'candidate_{i:04d}' for i, r in enumerate(candidates)}
    rebound = read(p3 / 'PCDARE_LINE_REBINDING_DIAGNOSIS.json')
    rebound['rows'] = [dict(candidate_id=lookup[(r['scan_id'], r['json_sha256'])],
                            **{k: v for k, v in r.items() if k != 'json_path'}) for r in rebound['rows']]
    rebound['public_export'] = 'Original individual file paths removed; unredacted binding table retained on authorized server.'
    write(dst / 'PCDARE_LINE_REBINDING_PUBLIC.json', rebound)

    frozen = read(source / 'p2_behave_crossview/P2_RUNTIME_FREEZE.json')
    baseline = workspace / 'docs/handoffs/real-scene-2026-10-03/pressurepose-prone-corrected-comparison-v2/code'
    identities = []
    for path in sorted(baseline.glob('*.py')):
        key = next(k for k in frozen if k.endswith('/delivery/code/' + path.name))
        assert sha(path) == frozen[key], path
        target = delivery / 'frozen_baseline_code' / path.name
        copy(path, target)
        identities.append(dict(path=target.relative_to(delivery).as_posix(), sha256=sha(target)))
    copy(source / 'assets/EXPERIMENT_CONTRACT.json', delivery / 'frozen_baseline_code/EXPERIMENT_CONTRACT.json')
    assert len(identities) == 21
    for key, expected in frozen.items():
        if '/prone_back_point_validation_20261003/code/' in key:
            actual = delivery / 'code' / Path(key).name
            assert sha(actual) == expected, actual
            identities.append(dict(path=actual.relative_to(delivery).as_posix(), sha256=sha(actual)))
    supplemental = read(source / 'p2_behave_crossview/P2_SUPPLEMENTAL_EXECUTION_FREEZE_PRE.json')
    for field, filename in [('launcher_sha256', 'launch_behave_jobs.py'),
                            ('runner_sha256', 'run_behave_rigid_d.py'),
                            ('postprocessor_sha256', 'summarize_behave_cached.py')]:
        assert sha(delivery / 'code' / filename) == supplemental[field]
    assert sha(delivery / 'frozen_baseline_code/EXPERIMENT_CONTRACT.json') == next(
        v for k, v in frozen.items() if k.endswith('/delivery/EXPERIMENT_CONTRACT.json'))

    pictures = []
    p1figs = read(source / 'p1_cached_transfer/PUBLIC_POINT_FIGURE_MANIFEST.json')
    for row in p1figs:
        suffix = Path(row['subject']) / f"seed_{row['seed']}.jpg"
        origin = source / 'p1_cached_transfer/public_point_figures' / suffix
        target = delivery / 'figures/p1' / suffix
        assert sha(origin) == row['sha256']
        copy(origin, target)
        pictures.append(dict(group='p1', case=f"{row['subject']} / seed {row['seed']}",
                             path=target.relative_to(delivery).as_posix(), sha256=sha(target)))
    p2figs = read(source / 'p2_behave_crossview/VISUALIZATION_MANIFEST.json')
    for row in p2figs:
        if row['original_rgb_included']:
            continue
        suffix = Path(row['sequence']) / (row['frame'] + '.jpg')
        origin = source / 'p2_behave_crossview/public_prediction_figures' / suffix
        target = delivery / 'figures/p2' / suffix
        assert sha(origin) == row['sha256']
        copy(origin, target)
        pictures.append(dict(group='p2', case=f"{row['sequence']} / {row['frame']}",
                             path=target.relative_to(delivery).as_posix(), sha256=sha(target)))
    for origin, target in [('p0_assets/canonical_seed_audit.jpg', 'figures/canonical_seed_audit.jpg'),
                           ('p4_rule_comparison/candidate_proxy_review.png', 'figures/candidate_proxy_review.png'),
                           ('p2_behave_crossview/per_subject_posterior_distance.png', 'figures/per_subject_posterior_distance.png')]:
        copy(source / origin, delivery / target)
    lines = ['# 全量可视化索引', '',
             '105 页全部预测图均由最终缓存生成，不含原始 RGB。可看模型形状/点位变化，不能单凭这些白底图判断图像对齐。', '',
             '颜色：紫色面/绿色轮廓是预测，不是数据集真值；旧点名仅为语义 HOLD 的回归标识。', '',
             '[旧 canonical 审计](figures/canonical_seed_audit.jpg) · [新工程 proxy 候选](figures/candidate_proxy_review.png) · [逐人独立机位结果](figures/per_subject_posterior_distance.png)', '',
             '完整原图叠加保留在本地及服务器：', '',
             '- `E:/项目-按摩理疗机器人/output/prone_back_point_validation_v1/p1_cached_transfer/visualizations/`（60 页）',
             '- `E:/项目-按摩理疗机器人/output/prone_back_point_validation_v1/p2_behave_crossview/private_rgb_review/`（45 页）',
             '- 服务器 `/raid5/xuhd/datasets/prone_back_point_validation_20261003/` 下对应目录。', '',
             '## PressurePose：20 人 × 3 seeds', '', '| 人物/种子 | 缓存预测与点位图 |', '|---|---|']
    for row in pictures:
        if row['group'] == 'p1':
            lines.append(f"| {row['case']} | [图]({row['path']}) |")
    lines += ['', '## BEHAVE：固定全部 45 帧', '',
              '无可用后背参考的 17 帧也保留，不按好坏筛图。有效 ROI/评价见逐相机表；原图的青色小块是冻结参考区域。', '',
              '| sequence/timestamp | 五方法 × 四相机预测图 |', '|---|---|']
    for row in pictures:
        if row['group'] == 'p2':
            lines.append(f"| {row['case']} | [图]({row['path']}) |")
    (delivery / 'VISUALIZATION_INDEX.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    write(delivery / 'PUBLIC_VISUALIZATION_MANIFEST.json', pictures)

    p2 = source / 'p2_behave_crossview'
    camera = csv_rows(p2 / 'PER_CAMERA_METHOD.csv')
    subject = csv_rows(p2 / 'PER_SUBJECT_HELDOUT.csv')
    results = read(p2 / 'RESULTS.json')
    metric_fields = ('surface_median_mm', 'surface_p95_mm', 'surface_coverage_50mm',
                     'ray_hit_fraction', 'ray_common_median_mm', 'ray_common_p95_mm')
    level = [r for r in camera if r['camera'] != 'K0']
    aggregation_checks = []
    for keys, filename in [(['subject', 'sequence', 'frame', 'method'], 'PER_FRAME_HELDOUT.csv'),
                           (['subject', 'sequence', 'method'], 'PER_SEQUENCE_HELDOUT.csv'),
                           (['subject', 'method'], 'PER_SUBJECT_HELDOUT.csv')]:
        groups = defaultdict(list)
        for row in level:
            groups[tuple(row[k] for k in keys)].append(row)
        calculated = {}
        for identity, group in groups.items():
            packed = dict(zip(keys, identity))
            for field in metric_fields:
                values = [float(row[field]) for row in group if row[field] not in ('', None)]
                packed[field] = statistics.median(values) if values else None
            calculated[identity] = packed
        saved = csv_rows(p2 / filename)
        assert len(saved) == len(calculated)
        for row in saved:
            actual = calculated[tuple(row[k] for k in keys)]
            for field in metric_fields:
                if row[field] == '':
                    assert actual[field] is None
                else:
                    assert abs(float(row[field]) - actual[field]) < 1e-10
        aggregation_checks.append(dict(file=filename, rows=len(saved), status='PASS'))
        level = list(calculated.values())
    for method in results['methods']:
        group = [r for r in subject if r['method'] == method['method']]
        assert len(group) == 5
        for key in metric_fields:
            assert abs(statistics.mean(float(r[key]) for r in group) - method[key]) < 1e-10
    bundle = read(p2 / 'ALL_FRAME_EVALUATIONS_AND_METADATA.json')
    assert len(bundle['frames']) == 45
    assert sum(len(r['evaluation']) for r in bundle['frames']) == 900
    assert len(camera) == 900
    assert sum(r['camera'] != 'K0' and int(r['posterior_point_count']) > 0 for r in camera) == 180
    assert len(read(p2 / 'FINAL_MESH_CACHE_MANIFEST.json')) == 225
    assert len(read(p2 / 'FROZEN_POSTERIOR_EVALUATION_INDICES.json')['rows']) == 180
    assert len(csv_rows(source / 'p1_cached_transfer/PER_POINT_DIAGNOSTICS.csv')) == 480
    assert sum(1 for _ in (source / 'p1_cached_transfer/PROPAGATED_POINTS.jsonl').open(encoding='utf-8')) == 2400
    assert sum(1 for _ in (source / 'p4_rule_comparison/RULE_PROXY_POINTS.jsonl').open(encoding='utf-8')) == 2400
    private1 = list((source / 'p1_cached_transfer/visualizations').rglob('*.jpg'))
    private2 = list((source / 'p2_behave_crossview/private_rgb_review').rglob('*.jpg'))
    assert len(p1figs) == 60 and len(pictures) == 105 and len(private1) == 60 and len(private2) == 45
    post = read(p2 / 'P2_SUPPLEMENTAL_EXECUTION_INTEGRITY_POST.json')
    assert post['status'] == 'PASS' and all(r['returncode'] == 0 for r in post['jobs'])
    for name in ('p1_cached_transfer', 'p4_rule_comparison'):
        assert read(source / name / 'SOURCE_PRE_POST_IDENTITY.json')['status'] == 'PASS'
    for path in p2.glob('INTEGRITY_*.json'):
        assert read(path)['status'] == 'PASS'
    assert len(scans) == 324 and len(public) == 1326 and len(labels) == 25
    write(delivery / 'DELIVERY_VALIDATION.json', dict(status='PASS', date='2026-10-03',
        p1=dict(source_meshes=300, point_records=2400, paired_records=480, private_rgb_pages=60, public_prediction_pages=60),
        p2=dict(formal_frames=45, method_meshes=225, all_camera_records=900,
                heldout_potential_records=675, heldout_valid_method_records=180,
                heldout_valid_views=36, heldout_valid_frames=28, private_rgb_pages=45,
                public_prediction_pages=45, cache_recomputation_views=3, cache_recomputation_method_groups=15),
        p3=dict(dmd_pairs=205, raw_label_classes=25, scan_rows=324, line_candidates=1326,
                unique_independent_reference_bindings=0),
        p4=dict(point_records=2400, shared_frames=60), source_and_input_integrity='PASS',
        jobs_returncode_zero=5, aggregate_subject_equal_mean_recomputed='PASS',
        camera_frame_sequence_subject_recomputed=aggregation_checks,
        frozen_source_identity_checks=identities, training_started=False, clinical_accuracy_validated=False))
    write(delivery / 'KNOWLEDGE_CLOSEOUT.json', dict(date='2026-10-03',
        code=dict(status='verified-current', evidence='Actual P0/P1/P2/P3/P4 outputs and frozen code hashes'),
        runtime=dict(status='verified-current', evidence='Five completed server jobs and pre/post integrity; offline, not deployed'),
        documents=dict(status='changed-and-verified', authoritative='FINAL_REPORT.md',
                       updated=['README.md', 'docs/CURRENT_STATUS.md', 'AI感知模块/README.md', 'deliverables/README.md']),
        rules=dict(status='verified-current', evidence='Root AGENTS.md read; unchanged'),
        memory=dict(status='out-of-scope', policy='Host-generated memory read-only; not edited'),
        workspace=dict(status='out-of-scope', evidence='Unrelated existing modifications and untracked artifacts preserved; no cleanup'),
        deployment=dict(status='not-applicable', evidence='No deployed camera, clinical or robot execution'),
        scientific_pending=['Atlas anatomical semantics', 'Independent prone calibrated reference', 'Medical acupoint accuracy'],
        publication='Git review delivery; push identity verified separately after commit'))

    acquisition = delivery.parent / 'back-data-acquisition-v1'
    files_manifest(acquisition)
    files_manifest(delivery)
    # Verify only newly authored/updated handoff links, not unrelated historical docs.
    for root in (delivery, acquisition):
        for path in root.rglob('*.md'):
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):
                    continue
                clean = target.split('#')[0].strip('<>')
                assert (path.parent / clean).exists(), (path, clean)
    print(json.dumps(dict(status='PASS', files=len(read(delivery / 'FILES_MANIFEST.json')['files']),
                          bytes=sum(p.stat().st_size for p in delivery.rglob('*') if p.is_file() and '__pycache__' not in p.parts),
                          figures=len(pictures)), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    package(parser.parse_args().workspace)
