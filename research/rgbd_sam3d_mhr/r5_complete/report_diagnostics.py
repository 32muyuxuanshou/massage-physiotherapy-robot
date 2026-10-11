"""Plain paired evidence, Depth interventions and residual scope from saved results."""
import json
from collections import defaultdict
import numpy as np


def write_diagnostics(root,out,csv_write):
    official=json.loads((root/'evaluation/official/real_B/RESULTS.json').read_text())
    native=json.loads((root/'evaluation/official/native/RESULTS.json').read_text())
    methods=['rgb_only','residual','cross_attention','g1','pooled_mlp','coarse','full']
    real_pairs=[];frames=[];native_pairs=[];interventions=[];common=[];conclusions=[]
    for seed in [11,23,37]:
        real={m:json.loads((root/'evaluation'/f'{m}_s{seed}_best/real_B/RESULTS.json').read_text()) for m in methods}
        reference_frames={v['key']:v for v in official['records']}
        for method,data in real.items():
            for role in ['TRAIN','VAL']:
                for identity,value in data['aggregated'][role]['per_identity'].items():
                    for baseline,reference in [('Official',official['aggregated'][role]['per_identity'][identity]['metrics']),
                        ('Official+Txyz',official['aggregated'][role+'_Txyz']['per_identity'][identity]['metrics']),
                        ('coarse',real['coarse']['aggregated'][role]['per_identity'][identity]['metrics'])]:
                        values=value['metrics']
                        real_pairs.append(dict(mode=method,seed=seed,role=role,identity=identity,baseline=baseline,
                            **values,**{'delta_'+k:values[k]-reference[k] for k in values}))
            for row in data['records']:
                base=reference_frames[row['key']]['triangle_txyz'];values=row['triangle']
                frames.append(dict(mode=method,seed=seed,key=row['key'],identity=row['identity'],role=row['role'],
                    median_mm=values['median_mm'],p95_mm=values['p95_mm'],
                    delta_vs_Official_Txyz_median_mm=values['median_mm']-base['median_mm'],
                    delta_vs_Official_Txyz_p95_mm=values['p95_mm']-base['p95_mm']))
            n=json.loads((root/'evaluation'/f'{method}_s{seed}_best/native/RESULTS.json').read_text())
            for identity,values in n['aggregated']['per_identity'].items():
                reference=native['aggregated']['per_identity'][identity]
                native_pairs.append(dict(mode=method,seed=seed,identity=identity,**values,
                    **{'delta_vs_Official_'+k:values[k]-reference[k] for k in values if values[k] is not None and reference[k] is not None}))
            abl=json.loads((root/'ablations'/f'{method}_s{seed}/RESULTS.json').read_text())
            grouped=defaultdict(list)
            for row in abl['records']:grouped[row['dataset'],row['variant'],row['role']].append(row)
            for (dataset,variant,role),rows in grouped.items():
                per=[]
                for identity in sorted({v['identity'] for v in rows}):
                    rr=[v for v in rows if v['identity']==identity]
                    keys=[k for k,v in rr[0]['response'].items() if isinstance(v,(int,float))]
                    per.append({k:float(np.mean([v['response'][k] for v in rr])) for k in keys})
                result=dict(mode=method,seed=seed,dataset=dataset,role=role,variant=variant,frames=len(rows),identities=len(per),
                    **{k:float(np.mean([v[k] for v in per])) for k in per[0]})
                if dataset=='native':result.update(abl['native_aggregated'][variant]['identity_equal_mean'])
                interventions.append(result)
            scan=json.loads((root/'evaluation'/f'{method}_s{seed}_best/scan/RESULTS.json').read_text())
            # These rows are pairwise on identical pixels, with missing-hit counts.
            # No-hit values stay empty; full-mask/missing penalty is reported separately.
            for row in scan['records']:
                item=dict(mode=method,seed=seed,sample_id=row['sample_id'],identity=row['identity'],asset_id=row['asset_id'],
                    camera_group=row['camera_group'],hit_rate=row['hit_rate'],common_points=row['common_points'],
                    total_person_points=row['total_person_points'],full_mask_median_mm=row['full_mask_median_mm'],
                    full_mask_p95_mm=row['full_mask_p95_mm'])
                for prefix in ['own_hit','common_hit','official_on_common_hit']:
                    item.update({prefix+'_'+k:(row[prefix][k] if row[prefix] is not None else None) for k in ['median_mm','p95_mm']})
                common.append(item)
        for role in ['TRAIN','VAL']:
            full=real['full']['aggregated'][role]['identity_equal_mean']
            for name,baseline in [('coarse',real['coarse']['aggregated'][role]['identity_equal_mean']),
                ('Official+Txyz',official['aggregated'][role+'_Txyz']['identity_equal_mean'])]:
                paired=[v for v in real_pairs if v['mode']=='full' and v['seed']==seed and v['role']==role and v['baseline']==name]
                conclusions.append(dict(seed=seed,role=role,baseline=name,full_median_mm=full['median_mm'],
                    delta_median_mm=full['median_mm']-baseline['median_mm'],delta_p95_mm=full['p95_mm']-baseline['p95_mm'],
                    identities=len(paired),identities_median_improved=sum(v['delta_median_mm']<0 for v in paired),
                    identities_P95_worsened=sum(v['delta_p95_mm']>0 for v in paired)))
    csv_write(out/'PAIRED_REAL_IDENTITIES.csv',real_pairs)
    csv_write(out/'PAIRED_REAL_FRAMES.csv',frames)
    csv_write(out/'PAIRED_NATIVE_IDENTITIES.csv',native_pairs)
    csv_write(out/'DEPTH_INTERVENTIONS_ALL_SEEDS.csv',interventions)
    csv_write(out/'SCAN_COMMON_HITS.csv',common)
    (out/'R5_COMPARISON_FACTS.json').write_text(json.dumps(conclusions,indent=2))
    text=['## 完整 R5 是否比粗定位和工程基线更好','',
        '负的差值代表完整R5更好；这里列出每个seed，不以最好seed替代全部结果。','',
        '|人群|seed|比较对象|median变化(mm)|P95变化(mm)|median改善人数|P95恶化人数|',
        '|---|---:|---|---:|---:|---:|---:|']
    for row in conclusions:
        text.append(f"|{row['role']}|{row['seed']}|{row['baseline']}|{row['delta_median_mm']:.3f}|{row['delta_p95_mm']:.3f}|{row['identities_median_improved']}/{row['identities']}|{row['identities_P95_worsened']}/{row['identities']}|")
    text+=['','## 误差来自位置还是人体','',
        'pooled/coarse/full的Body逐字段严格等于Official，因此它们的新增改善或恶化来自Camera平移；它们不能修复Official已有的姿态/体型错误。',
        'native有对应真值，可分别看Camera L2、Body顶点、去平移顶点、关节和Pose/Shape/Scale。三维顶点误差不是各分量误差相加，不能把Camera L2直接当作总误差的贡献百分比。',
        '真实数据没有原生MHR人体参数真值。Camera B点到面只说明可见表面一致性，不能把真实误差唯一分解为Pose/Shape真值误差。',
        '逐身份和逐帧差值在PAIRED_REAL_*中；所有负面样本均保留。','',
        '## 扫描表面分数的特殊含义','',
        'full_mask含未命中惩罚：预测Z=0时计入目标距离。这会产生米级P95，它不是米级已命中表面误差。请连同hit_rate、own_hit及SCAN_COMMON_HITS中的配对共同命中结果阅读；共同命中为空的样本仍保留。',
        '共同命中表中每个模型与Official使用相同像素；不同模型的共同像素集合可能不同，不将其直接当统一排名。','',
        '## Depth是否真的有用','',
        'DEPTH_INTERVENTIONS_ALL_SEEDS列出正确、错配、局部扰乱、缺失、绝对/相对Z和±100mm干预。native可直接比较真值误差；真实44帧这里只报告输出响应。',
        'full的fine关闭/方向处理关闭是固定已训练权重上的机制干预，不冒充分别重训的消融。RGB-only对Depth输入的响应应为零。']
    return text
