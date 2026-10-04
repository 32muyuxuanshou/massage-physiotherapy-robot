"""Report registered per-level/P95 and paired cases without selecting best seeds."""
import csv
import json

import numpy as np

from prepare_pilot import OUT, LEVELS, write


def main():
    rows=json.loads((OUT/'PER_CASE_RESULTS.json').read_text());summary=json.loads((OUT/'RESULTS.json').read_text())
    records=[]
    for role in ['train','dev','test','author_val_supporting']:
        for method in ['TRAIN_MEDIAN_POSITION','GLOBAL_REGRESSION','INDEPENDENT_HEATMAP','ORDERED_QUERY']:
            mr=[r for r in rows if r['role']==role and r['method']==method]
            for i,level in enumerate(LEVELS):
                subjects=sorted(set(r['subject'] for r in mr if r['per_level_xz_mm'][i] is not None))
                values=[np.median([r['per_level_xz_mm'][i] for r in mr if r['subject']==s]) for s in subjects]
                records.append(dict(role=role,method=method,level=level,cases=len(values),median_xz_mm=float(np.median(values)) if values else None,
                                    p95_xz_mm=float(np.percentile(values,95)) if values else None))
    write(OUT/'PER_LEVEL_SUMMARY.json',records)
    with (OUT/'PER_LEVEL_SUMMARY.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    comparisons=[]
    for role,data in summary['summary'].items():
        baseline=data['TRAIN_MEDIAN_POSITION']['per_subject'];global_scores=data['GLOBAL_REGRESSION']['per_subject']
        for method in ['GLOBAL_REGRESSION','INDEPENDENT_HEATMAP','ORDERED_QUERY']:
            scores=data[method]['per_subject']
            comparisons.append(dict(role=role,method=method,cases=len(scores),better_than_median=sum(v<baseline[s] for s,v in scores.items()),
                                     better_than_global=sum(v<global_scores[s] for s,v in scores.items()),
                                     deltas_vs_median={s:v-baseline[s] for s,v in scores.items()},deltas_vs_global={s:v-global_scores[s] for s,v in scores.items()}))
    write(OUT/'PAIRED_CASE_CHANGES.json',comparisons)
    report=['# CT解剖参考查询原型V1：实际结果','',
            '输入只有CT派生后表面高度/有效mask/物理图像平面坐标；目标为逐节标签后侧极值的体表投影代理。下列毫米不是穴位或俯卧RGB-D精度。','',
            '|角色|例数|训练中位位置|全局回归|独立热图|有序查询|','|---|---:|---:|---:|---:|---:|']
    for role,data in summary['summary'].items():
        values=[data[m]['subject_equal_mean_xz_mm'] for m in ['TRAIN_MEDIAN_POSITION','GLOBAL_REGRESSION','INDEPENDENT_HEATMAP','ORDERED_QUERY']]
        report.append('|'+role+'|'+str(data['TRAIN_MEDIAN_POSITION']['case_count'])+'|'+ '|'.join('NA' if v is None else f'{v:.3f}' for v in values)+'|')
    report+=['','上述为每例内部目标均值、每例跨初始化中位、角色内例均值的X/Z误差。所有有效CT目标参与主指标；没有因未命中表面而排除困难目标。',
             '','逐初始化、逐例、逐等级median/P95、命中率和所有方法共同命中3D对照见对应JSON/CSV。三个seed全部保留，不挑最好一次。',
             '','来源限制：CT扫描体位/外皮压力与俯卧不同，HU外边界不是RGB-D传感器测量，CT分割标签有误标风险；CT参考仍不等于WHO棘突下凹陷。',
             '','这是新的监督定位任务原型。即使有序decoder改善，也不足以声称强论文创新或上线；若未改善，保留失败，不在本考试集调模型。']
    (OUT/'GENERATED_REPORT.md').write_text('\n'.join(report),encoding='utf-8')
    print('\n'.join(report[:12]),flush=True)


if __name__=='__main__':main()
