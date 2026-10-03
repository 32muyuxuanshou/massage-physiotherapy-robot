"""Export every result/figure, and descriptive paired audits; never fit or select cases."""
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--history-csv', type=Path, required=True)
    a = p.parse_args()
    result = read(a.source / 'AGGREGATED_RESULTS.json')
    assert result['status'] == 'FORMAL_COMPLETE' and result['row_count'] == 300
    assert read(a.source / 'CACHE_RECOMPUTE_AUDIT.json')['status'] == 'PASS'
    assert read(a.source / 'INTEGRITY_full.json')['status'] == 'PASS'
    visual = []
    copies = []
    for path in sorted(a.source.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(a.source)
        if path.suffix.lower() == '.png':
            dest_rel = rel.with_suffix('.jpg')
            dest = a.out / 'results' / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(path) as im:
                size = list(im.size)
                im.convert('RGB').save(dest, quality=92, subsampling=0, optimize=True)
            visual.append(dict(server_relative_path=rel.as_posix(), public_path='results/' + dest_rel.as_posix(),
                source_sha256=digest(path), exported_sha256=digest(dest), size=size,
                conversion='full-resolution JPEG quality 92; display export only; metrics use original caches'))
        else:
            dest = a.out / 'results' / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            copies.append(dict(path='results/' + rel.as_posix(), sha256=digest(dest)))
            if path.suffix.lower() in ['.jpg', '.jpeg']:
                with Image.open(path) as im:
                    size = list(im.size)
                visual.append(dict(server_relative_path=rel.as_posix(), public_path='results/' + rel.as_posix(),
                    source_sha256=digest(path), exported_sha256=digest(dest), size=size, conversion='none'))
    write(a.out / 'VISUALIZATION_EXPORT_MANIFEST.json', dict(
        policy='all subjects, all methods, all seeds; no numerical-quality selection',
        count=len(visual), files=visual))

    subjects = result['per_subject']
    methods = result['methods']
    pairs = []
    for s in result['subjects']:
        rows = {x['method']: x for x in subjects if x['subject'] == s}
        for after, before in [(methods[1], methods[0]), (methods[2], methods[1]),
                              (methods[3], methods[0]), (methods[4], methods[3])]:
            x, y = rows[after], rows[before]
            pairs.append(dict(subject=s, split=x['split'], after=after, before=before,
                back_median_delta_mm=x['posterior_d3d_median_mm']-y['posterior_d3d_median_mm'],
                back_p95_delta_mm=x['posterior_d3d_p95_mm']-y['posterior_d3d_p95_mm'],
                common_ray_median_delta_mm=x['posterior_ray_common_hit_absolute_median_mm']-y['posterior_ray_common_hit_absolute_median_mm'],
                common_ray_p95_delta_mm=x['posterior_ray_common_hit_absolute_p95_mm']-y['posterior_ray_common_hit_absolute_p95_mm'],
                silhouette_iou_delta=x['silhouette_iou']-y['silhouette_iou']))
    summary = {}
    for split in ['dev', 'test', 'all']:
        summary[split] = {}
        for after, before in sorted(set((r['after'], r['before']) for r in pairs)):
            rows = [r for r in pairs if r['after']==after and r['before']==before and (split=='all' or r['split']==split)]
            summary[split][after + ' vs ' + before] = dict(subjects=len(rows),
                median_improved=sum(r['back_median_delta_mm']<0 for r in rows),
                p95_improved=sum(r['back_p95_delta_mm']<0 for r in rows),
                common_ray_median_improved=sum(r['common_ray_median_delta_mm']<0 for r in rows),
                common_ray_p95_improved=sum(r['common_ray_p95_delta_mm']<0 for r in rows),
                silhouette_worsened=sum(r['silhouette_iou_delta']<0 for r in rows),
                median_paired_back_delta_mm=float(np.median([r['back_median_delta_mm'] for r in rows])))
    per_seed=[]
    for s in result['subjects']:
        for row in read(a.source/'evaluation'/s/'results.json'):
            if row['method'] == 'Official+Txyz':
                op=row['optimization'];raw=np.asarray(op['raw_translation_m']);applied=np.asarray(op['applied_translation_m'])
                per_seed.append(dict(subject=s,split=row['split'],seed=row['seed'],fallback=op['fallback'],
                    raw_translation_mm=(raw*1000).tolist(),applied_translation_mm=(applied*1000).tolist(),
                    raw_norm_mm=float(np.linalg.norm(raw)*1000),applied_norm_mm=float(np.linalg.norm(applied)*1000)))
    fallback={group:dict(n=len([r for r in per_seed if group=='all' or r['split']==group]),
        fallback=sum(r['fallback'] for r in per_seed if group=='all' or r['split']==group)) for group in ['dev','test','all']}
    write(a.out/'DESCRIPTIVE_PAIRED_AUDIT.json',dict(
        interpretation='post-execution descriptive counts; no new gates, thresholds or p-values',
        paired_summary=summary,paired_subjects=pairs,txyz_fallback_summary=fallback,txyz_translations=per_seed))

    with a.history_csv.open(encoding='utf-8-sig',newline='') as f:
        historical=list(csv.DictReader(f))
    with (a.source/'per_method_subject_seed.csv').open(encoding='utf-8-sig',newline='') as f:
        current=list(csv.DictReader(f))
    old_index={(r['subject'],int(r['seed']),r['method']):r for r in historical}
    mapping={'Official':'Official','Official+Rigid':'O+Rigid','Official+Rigid+D':'O+Rigid+D'}
    diffs=[]
    for r in current:
        if r['method'] not in mapping:
            continue
        old=old_index[r['subject'],int(r['seed']),mapping[r['method']]]
        diffs.append(dict(subject=r['subject'],split=r['split'],seed=int(r['seed']),method=r['method'],
            old_torso_d3d_median_mm=float(old['torso_d3d_med']),new_torso_d3d_median_mm=float(r['torso_d3d_median_mm']),
            torso_d3d_median_delta_mm=float(r['torso_d3d_median_mm'])-float(old['torso_d3d_med']),
            old_torso_ray_median_mm=float(old['torso_ray_med']),new_torso_ray_median_mm=float(r['torso_ray_absolute_median_mm']),
            torso_ray_median_delta_mm=float(r['torso_ray_absolute_median_mm'])-float(old['torso_ray_med']),
            old_torso_hit=float(old['torso_hit']),new_torso_hit=float(r['torso_ray_hit_fraction'])))
    historical_summaries={}
    for split in ['dev','test','all']:
        historical_summaries[split]={}
        for method in mapping:
            rows=[r for r in diffs if r['method']==method and (split=='all' or r['split']==split)]
            means=[]
            for s in sorted({r['subject'] for r in rows}):
                part=[r for r in rows if r['subject']==s]
                means.append({key:float(np.mean([r[key] for r in part])) for key in [
                    'old_torso_d3d_median_mm','new_torso_d3d_median_mm','old_torso_ray_median_mm','new_torso_ray_median_mm']})
            historical_summaries[split][method]={key:float(np.median([r[key] for r in means])) for key in means[0]}
    write(a.out/'OLD_NEW_PAIRED_AUDIT.json',dict(historical_source_sha256=digest(a.history_csv),
        note='same old torso-band summary; fresh Official precision and exact ray fixes are mixed in the comparison. Old lifted Txyz / all-cloud T+Pose are not comparable and excluded. Old P90 must not be compared with new P95.',
        summary=historical_summaries,rows=diffs))
    dest=a.out/'historical'/'l1_eval_rows.csv';dest.parent.mkdir(exist_ok=True)
    shutil.copyfile(a.history_csv,dest)

    table=['# 全量可视化索引','','20 人 × 3 种子；每页包含 RGB 和全部五组方法。没有按好坏筛选。',
           '', '紫色填充、绿色轮廓均来自预测 Mesh；青色为过滤点云投影；黄色为冻结后背 ROI。',
           '', '| 人物 | 角色 | seed 0 | seed 1 | seed 2 | 原始数据对应核查 |', '|---|---|---|---|---|---|']
    for s in result['subjects']:
        split=next(r['split'] for r in subjects if r['subject']==s)
        links=[f'[对照](results/visualizations/{s}/seed_{k}/comparison.jpg)' for k in result['seeds']]
        table.append('| '+ ' | '.join([s,split,*links,f'[RGB/Depth/点云](results/camera_audit/{s}_sources.jpg)'])+' |')
    table += ['', '每页同目录还包含五组独立叠图、后背残差图、相机 X 切片及三轴平移图。',
              'PNG 转成同分辨率 JPEG 仅供网页展示；服务器保留原 PNG 与渲染深度数组，完整映射见 `VISUALIZATION_EXPORT_MANIFEST.json`。','']
    (a.out/'VISUAL_INDEX.md').write_text('\n'.join(table),encoding='utf8')
    print(json.dumps(dict(rows=result['row_count'],visualizations=len(visual),copied_files=len(copies),fallback=fallback),ensure_ascii=False))


if __name__=='__main__':
    main()
