"""Post-hoc descriptive audit of existing outputs; no model execution or selection."""
import hashlib
import json
from pathlib import Path
from statistics import median
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'error-audit-v1'
CONDITIONS = ('FULL', 'UPPER', 'LOCAL_TORSO')

def key(r):
    return tuple(r['spec'][x] for x in ('subject', 'sequence', 'frame')) + (r['condition'],)

def held(r, method, metric='median_mm', evidence='sensor'):
    return median(r['methods'][method][f'K{k}'][evidence][metric] for k in (1, 2, 3))

def hierarchy(rows, value):
    subjects = {}
    for subject in sorted({r['spec']['subject'] for r in rows}):
        sequences = {}
        for sequence in sorted({r['spec']['sequence'] for r in rows if r['spec']['subject'] == subject}):
            sequences[sequence] = median(value(r) for r in rows if r['spec']['sequence'] == sequence)
        subjects[subject] = {'value': median(sequences.values()), 'sequences': sequences}
    return {'primary': median(x['value'] for x in subjects.values()), 'subjects': subjects}

def main():
    OUT.mkdir(exist_ok=True)
    sources = sorted((ROOT/'attribution_v1').glob('Sub*_ATTRIBUTION_RESULTS.json'))
    attr = [r for p in sources for r in json.loads(p.read_text())['rows']]
    formal_files = sorted((ROOT/'formal-back-local-model-evaluation-continuation-v1'/'formal_eval_v3_complete').glob('Sub*/raw/*/*/*/*.json'))
    formal = [json.loads(p.read_text()) for p in formal_files]
    assert len(formal) == len(attr) == 54
    assert len({key(r) for r in formal}) == len({key(r) for r in attr}) == 54
    assert {key(r) for r in formal} == {key(r) for r in attr}
    fby = {key(r): r for r in formal}
    afull = {key(r)[:3]: r for r in attr if r['condition'] == 'FULL'}
    rows = []
    for r in attr:
        h = {m: held(r, m) for m in r['methods']}
        f = fby[key(r)]
        fh = {m: held(f, m) for m in f['methods']}
        k0_delta = f['methods']['T+Pose']['K0']['sensor']['median_mm'] - f['methods']['Txyz']['K0']['sensor']['median_mm']
        sid = '__'.join(key(r)[:3])
        images = [f'visual_v3/{sid}_FULL_K0K1K2K3.png', f'visual_v3/{sid}_K1_conditions.png']
        assert all((ROOT/p).is_file() for p in images)
        rows.append({
            'subject': key(r)[0], 'sequence': key(r)[1], 'frame': key(r)[2], 'condition': r['condition'],
            'attribution_heldout_mm': h,
            'txyz_gain_mm': h['Official'] - h['Txyz'],
            't_only_incremental_gain_mm': h['Txyz'] - h['T_only'],
            'body_branch_vs_t_only_gain_mm': h['T_only'] - h['T_bodypose'],
            'rotation_branch_vs_t_only_gain_mm': h['T_only'] - h['T_globalrot'],
            'joint_incremental_gain_mm': h['Txyz'] - h['T+Pose'],
            'local_minus_full_mm': {m: h[m] - held(afull[key(r)[:3]], m) for m in h},
            'txyz_fallback': r['txyz_fallback'],
            'joint_translation_delta_mm': 1000*math.sqrt(sum(v*v for v in r['parameters']['T+Pose']['translation_delta_m'])),
            'joint_camera_medians_mm': {k: v['sensor']['median_mm'] for k,v in r['methods']['T+Pose'].items()},
            'joint_camera_p95_mm': {k: v['sensor']['p95_mm'] for k,v in r['methods']['T+Pose'].items()},
            'formal_v3_k0_full_person_median_delta_mm': k0_delta,
            'formal_v3_heldout_delta_mm': fh['T+Pose'] - fh['Txyz'],
            'formal_v3_k0_better_heldout_worse': k0_delta < 0 and fh['T+Pose'] > fh['Txyz'],
            'formal_v3_optimization_loss_decreased': f['o2_final_loss'] < f['o2_initial_loss'],
            'formal_v3_loss_better_heldout_worse': f['o2_final_loss'] < f['o2_initial_loss'] and fh['T+Pose'] > fh['Txyz'],
            'formal_v3_vs_attribution_abs_difference_mm': {m: abs(fh[m] - h[m]) for m in fh},
            'visuals_from_formal_v3_not_attribution_rerun': images,
        })
    summary = {}
    for c in CONDITIONS:
        q = [r for r in rows if r['condition'] == c]
        summary[c] = {'frame_count': len(q), 'txyz_fallback': sum(r['txyz_fallback'] for r in q)}
        for label in ('txyz_gain_mm', 't_only_incremental_gain_mm', 'body_branch_vs_t_only_gain_mm', 'rotation_branch_vs_t_only_gain_mm', 'joint_incremental_gain_mm'):
            vals = [r[label] for r in q]
            summary[c][label] = {'positive_count': sum(v>0 for v in vals), 'negative_count': sum(v<0 for v in vals), 'median_paired_frame_gain_mm': median(vals), 'min_mm': min(vals), 'max_mm': max(vals)}
        summary[c]['formal_v3_k0_better_heldout_worse'] = sum(r['formal_v3_k0_better_heldout_worse'] for r in q)
        summary[c]['formal_v3_loss_better_heldout_worse'] = sum(r['formal_v3_loss_better_heldout_worse'] for r in q)
    formal_hierarchy = []
    for c in CONDITIONS:
        q = [r for r in formal if r['condition']==c]
        for m in ('Official','Txyz','T+Pose'):
            for e in ('sensor','reference'):
                formal_hierarchy.append({'condition':c,'method':m,'evidence':e,**hierarchy(q,lambda r:held(r,m,evidence=e))})
    result = {'status':'ANALYZED_EXISTING_OUTPUTS_ONLY', 'aggregation':'median cameras -> median frames per sequence -> median sequences per subject -> median subjects',
        'interpretation':'Post-hoc descriptive comparisons, non-exclusive signs, no new acceptance threshold; positive gain means lower error. Branch contrasts include reoptimized translation, not isolated anatomical causality.',
        'missing_evidence':['attribution K0 metrics and vertices','per-point residual coordinates / anatomical regions','crop-only K0 evaluation metric','clinical point ground truth'],
        'counts':{'subjects':3,'sequences':9,'timestamps':18,'condition_rows':54,'attribution_camera_method_rows':972,'formal_camera_method_rows':648,'visual_files_linked':36},
        'summary':summary,'formal_hierarchy':formal_hierarchy,'rows':rows}
    (OUT/'ERROR_AUDIT.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    report_files = sorted((ROOT/'formal-back-local-model-evaluation-continuation-v1'/'formal_eval_v3_complete').glob('Sub*/report/per_frame_results.json'))
    report_rows = [r for p in report_files for r in json.loads(p.read_text())]
    assert len(report_rows)==54 and all(r==fby[key(r)] for r in report_rows)
    manifest = {str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources+formal_files+report_files+sorted((ROOT/'visual_v3').glob('*.png'))}
    (OUT/'SOURCE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
    lines = ['# 逐帧数值与叠图索引', '', '全部 54 条件行，未按效果筛选。数值来自 attribution rerun，叠图来自 formal V3；二者差异保存在 ERROR_AUDIT.json。', '',
             'gain > 0 表示误差下降；Pose gain 是联合优化相对 Txyz 的增益，不是纯姿态贡献。单位 mm。', '',
             '| 人物 / sequence / timestamp | 输入 | Official | Txyz | T+Pose | Joint gain | Body vs T-only gain | 图片 |',
             '|---|---|---:|---:|---:|---:|---:|---|']
    for r in rows:
        h=r['attribution_heldout_mm']; ident=f"{r['sequence']}/{r['frame']}"
        lines.append(f"| {ident} | {r['condition']} | {h['Official']:.2f} | {h['Txyz']:.2f} | {h['T+Pose']:.2f} | {r['joint_incremental_gain_mm']:.2f} | {r['body_branch_vs_t_only_gain_mm']:.2f} | [FULL四机位](../{r['visuals_from_formal_v3_not_attribution_rerun'][0]}) / [K1三输入](../{r['visuals_from_formal_v3_not_attribution_rerun'][1]}) |")
    (OUT/'FRAME_INDEX.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__':
    main()
