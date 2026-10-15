"""Post-execution paired interpretation; does not fit or select a new model."""
import json
from pathlib import Path
import numpy as np

ROOT=Path('output/r51_fine_supervision_ablation_v1')
OLD=Path('output/r5_focused_diagnostics_v1/reports')
ARMS=['Parent','E0','E1_half','E1_zero','E2_l2']
SEEDS=[11,23,37]


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def main():
    out=ROOT/'reports';cells=read(out/'REAL_RESULTS.json');jobs=read(out/'REAL_JOBS.json')
    old=read(OLD/'SUMMARY.json');old_rows=read(OLD/'Q1_RECORDS.json')
    old_by={(r['dataset'],r['seed'],r['key']):r for r in old_rows}
    def cell(arm,seed,selection='last'):
        return next(r for r in cells if r['arm']==arm and r['seed']==seed and r['selection']==('parent' if arm=='Parent' else selection))
    def records(arm,seed,selection='last'):return jobs[cell(arm,seed,selection)['job']['name']]['records']
    def group(arm,seed,dataset,role='VAL',selection='last'):
        return next(g for g in cell(arm,seed,selection)['groups'] if g['dataset']==dataset and (dataset=='behave' or g['role']==role))
    reconciliation=[]
    for seed in SEEDS:
        rows=[r for r in records('Parent',seed) if r['dataset']=='behave']
        c=next(c for c in old['cells'] if c['dataset']=='behave' and c['seed']==seed)
        new_id=group('Parent',seed,'behave')['metrics']['pve_mm']['equal_mean']
        new_frame=float(np.mean([r['pve_mm'] for r in rows]))
        diffs=[abs(r['pve_mm']-old_by['behave',seed,r['key']]['stages']['final']['pve_mm']) for r in rows]
        reconciliation.append(dict(seed=seed,old_identity_equal=c['stages']['final']['pve_mm']['identity_equal_mean'],
            new_identity_equal=new_id,old_frame_equal=c['stages']['final']['pve_mm']['frame_equal_mean'],new_frame_equal=new_frame,
            max_per_frame_reproduction_difference_mm=max(diffs),
            official_txyz_frame_equal=float(np.mean([old_by['behave',seed,r['key']]['official_txyz']['pve_mm'] for r in rows]))))
    ref=read(out/'OFFICIAL_TXYZ_REFERENCE.json')
    for r in reconciliation:r['official_txyz_identity_equal']=next(b for b in ref if b['dataset']=='behave' and b['seed']==r['seed'])['metrics']['pve_mm']['equal_mean']
    rec=dict(reason='Historical 61.06 and 56.24 are frame-equal; current frozen report uses sequence then identity equal. Same frame predictions, different weights; no scientific improvement implied.',
        rows=reconciliation,three_seed_means={k:float(np.mean([r[k] for r in reconciliation])) for k in reconciliation[0] if k!='seed'})
    (out/'AGGREGATION_RECONCILIATION.json').write_text(json.dumps(rec,indent=2),encoding='utf-8')
    identity_rows=[];region_rows=[];paired=[]
    for seed in SEEDS:
        for dataset,role in [('real','TRAIN'),('real','VAL'),('behave',None)]:
            base=group('E0',seed,dataset,role)
            for arm in ARMS:
                g=group(arm,seed,dataset,role)
                for identity in g['metrics']['median_mm']['per_identity']:
                    row=dict(arm=arm,seed=seed,dataset=dataset,role=g['role'],identity=identity)
                    for metric in g['metrics']:
                        a=g['metrics'][metric]['per_identity'][identity]['mean'];b=base['metrics'][metric]['per_identity'][identity]['mean']
                        row[metric]=a;row[metric+'_minus_E0']=a-b
                    identity_rows.append(row)
        e0={(r['dataset'],r['key']):r for r in records('E0',seed)}
        for arm in ARMS[2:]:
            for r in records(arm,seed):
                b=e0[r['dataset'],r['key']]
                paired.append(dict(arm=arm,seed=seed,dataset=r['dataset'],role=r['role'],identity=r['identity'],key=r['key'],
                    delta_median_mm=r['metrics']['median_mm']-b['metrics']['median_mm'],delta_p95_mm=r['metrics']['p95_mm']-b['metrics']['p95_mm']))
        for arm in ARMS:
            rr=[r for r in records(arm,seed) if r['dataset']=='real']
            for role in ['TRAIN','VAL']:
                rr_role=[r for r in rr if r['role']==role]
                for region in sorted({k for r in rr_role for k in r['regions']}):
                    ids={}
                    for identity in sorted({r['identity'] for r in rr_role}):
                        sequences={}
                        for r in rr_role:
                            if r['identity']==identity and region in r['regions']:sequences.setdefault(r['sequence'],[]).append(r['regions'][region]['median_mm'])
                        if sequences:ids[identity]=float(np.mean([np.mean(v) for v in sequences.values()]))
                    region_rows.append(dict(arm=arm,seed=seed,role=role,region=region,median_mm=float(np.mean(list(ids.values()))),per_identity=ids))
    (out/'PER_IDENTITY_LAST.json').write_text(json.dumps(identity_rows,indent=2),encoding='utf-8')
    (out/'REGION_LAST.json').write_text(json.dumps(region_rows,indent=2),encoding='utf-8')
    (out/'WORST_PAIRED_FRAMES.json').write_text(json.dumps(sorted(paired,key=lambda r:r['delta_p95_mm'],reverse=True)[:30],indent=2),encoding='utf-8')
    # Do not overwrite the original incomplete restore receipt: Scan came separately.
    post=read(ROOT/'POST_INTEGRITY.json');scan=read(ROOT/'SCAN_TRANSFER_RECEIPT.json');restore=read(ROOT/'DATA_RESTORE_RECEIPT.json')
    ready=dict(status='PASS',native_restore_initial_status=restore['status'],initial_issue='Historical archive omitted Scan, not a failed experiment. Original MISSING receipt retained.',
        scan_resolution=dict(status=scan['status'],count=scan['count'],bytes=scan['bytes'],receipt='SCAN_TRANSFER_RECEIPT.json'),
        final_actual_integrity_status=post['status'],prepared_records=post['prepared_records'],actual_files_verified=post['actual_files_verified'],sealed_TEST_read=False)
    (ROOT/'DATA_READY.json').write_text(json.dumps(ready,indent=2),encoding='utf-8')
    md='# 结果解释与逐人复核\n\n'
    md+='本轮检验的是固定Coarse后Fine的监督取舍，没有证明新架构、没有优化Camera B、没有重训Body。真实变化只能来自最终平移；不能解释为姿态、体型或解剖对应变准。\n\n'
    md+='## 三项判断\n\n1. **Camera监督不能一删了之。** 权重0在Native上使顶点94.33→84.64mm、全mask轴向Z 77.13→67.17mm；但Camera 20.71→45.76mm，正交分量均值10.92→29.25mm。真实HuMMan VAL三seed相对E0全部变差，P95平均增加0.521mm。合成表面收益未迁移成真实稳定收益。\n2. **权重0.5只有小幅收益。** HuMMan VAL median 14.246→14.202mm，平均仅0.044mm；BEHAVE独立表面19.682→19.640mm，2/3 seed改善。它可以留作后续候选，尚不足以宣布方法升级或大规模训练。\n3. **本次简单L2无独立正面证据。** HuMMan VAL median三seed全部变差，BEHAVE独立表面也全部变差；联合选模三seed均回到epoch0。不能据此否定全部正则，但没有依据把它和E1组合。\n\n'
    md+='## HuMMan VAL逐人：同预算末轮，三seed平均\n\n每行是各seed内部先frame→sequence等权，再将seed平均。小于0表示比E0好。\n\n|身份|E0 median|权重.5 Δmedian/ΔP95|权重0 Δmedian/ΔP95|L2 Δmedian/ΔP95|\n|---|---:|---:|---:|---:|\n'
    for identity in sorted({r['identity'] for r in identity_rows if r['dataset']=='real' and r['role']=='VAL'}):
        def rows(a):return [r for r in identity_rows if r['dataset']=='real' and r['role']=='VAL' and r['identity']==identity and r['arm']==a]
        parts=[identity,f"{np.mean([r['median_mm'] for r in rows('E0')]):.3f}"]
        for a in ARMS[2:]:parts.append('/'.join(f"{np.mean([r[k] for r in rows(a)]):+.3f}" for k in ['median_mm_minus_E0','p95_mm_minus_E0']))
        md+='|'+'|'.join(parts)+'|\n'
    md+='\n## 已知失败身份与部位\n\n'
    for identity in ['p001195','p001196']:
        rr=[r for r in identity_rows if r['dataset']=='real' and r['identity']==identity]
        md+=identity+'：'+ '；'.join(a+' median/P95 '+ '/'.join(f"{np.mean([r[k] for r in rr if r['arm']==a]):.3f}" for k in ['median_mm','p95_mm']) for a in ARMS)+' mm。\n\n'
    md+='部位标签为旧的工程proxy，未经解剖标注，不是临床后背区域。全部部位、人物和seed见REGION_LAST.json；三张失败图保留已知失败人物及权重0相对E0最坏VAL帧，不挑最好看的。\n\n'
    md+='## 选模与梯度解释\n\n原顶点选模、联合选模、末轮全部保留。联合规则没有显示一致真实优势：例如权重0.5、seed23原规则选epoch4，HuMMan VAL为14.939mm；联合规则选epoch6，为15.056mm。不能看了B后改称另一规则是正式主结果。\n\nE0固定Native TRAIN探针的12个Camera/Surface最后层梯度余弦均为负，支持局部目标竞争；不证明衣物噪声底限、所有层损失冲突，或所有历史失败的唯一原因。不同seed是原三父模型的配对续训，6轮不等于已经收敛。\n\n'
    md+='## 61.06与59.64的对账\n\n'
    md+=f"原R5 Full Last按270帧平均为{rec['three_seed_means']['new_frame_equal']:.6f}mm；按本轮冻结的sequence→identity等权为{rec['three_seed_means']['new_identity_equal']:.6f}mm。旧报告已保存这两种结果，本轮逐帧重新计算相符；没有把差额计为改善。Official+Txyz同理：帧均值{rec['three_seed_means']['official_txyz_frame_equal']:.6f}mm，层级等权{rec['three_seed_means']['official_txyz_identity_equal']:.6f}mm。详情见AGGREGATION_RECONCILIATION.json。\n\n"
    md+='## 下一步判断\n\n本轮结束，不自动追加组合或扩大训练。保留原R5和权重0.5候选，E2不进入组合。当前最值得推进的不是继续扫描权重，而是在现有冻结Body框架下检查Fine的观测对应与几何信息表达；先提出能超过0.04mm微小收益的明确假设。若重启下一阶段，应以独立表面和失败率为主，保持Camera参数误差独立报告，不能拿Txyz当相机GT。工程与论文均仍缺真正俯卧后背和解剖传播的独立验证；本轮不能补上该缺口。\n'
    (out/'ANALYSIS.md').write_text(md,encoding='utf-8')
    print('ANALYSIS_COMPLETE',json.dumps(rec['three_seed_means']))


if __name__=='__main__':main()
