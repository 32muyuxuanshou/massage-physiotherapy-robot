"""Interpret completed fixed contrasts without ranking/selecting new models."""
import argparse,json
from pathlib import Path
import numpy as np


def main(root):
    out=root/'reports';cells=json.loads((out/'RESULTS.json').read_text());frames=json.loads((out/'FRAME_RESULTS.json').read_text());pairs=json.loads((out/'PAIRED_CONTRASTS.json').read_text())
    index={(r['dataset'],r['seed'],r['key'],r['method']):r for r in frames}
    cohorts=sorted({(r['dataset'],r['role']) for r in cells})
    def values(method,dataset,role,metric):return np.array([r['metrics'][metric]['equal_mean'] for r in sorted(cells,key=lambda r:r['seed']) if r['method']==method and r['dataset']==dataset and r['role']==role])
    md='# 结果解释与下一步判断\n\n本轮固定Body，只改变平移求解。没有训练、没有新Body能力，也没有对B拟合。下列变化不代表Pose、Shape、解剖或穴位更准。\n\n'
    md+='## 先说结论\n\n'
    md+='1. **直接用完整Txyz替掉Fine，不成立为通用升级。** 同Coarse的密集6步使HuMMan VAL 14.359→12.736mm，但BEHAVE 19.827→21.246mm。BEHAVE seed37退化4.731mm；HuMMan VAL P95也从44.550升到45.322mm。不能只交VAL median。\n'
    md+='2. **三维NN不自动优于投影对应。** 在相同Depth格点、相同可见Query、相同一步中位数下，NN相对真实像素投影的误差变化：Native +3.709mm、HuMMan TRAIN +1.771mm、VAL +1.347mm、BEHAVE +2.387mm；四组均3/3seed变差。这否定本对照中“只缺三维最近邻”的解释，不证明所有三维关联方法都无效。\n'
    md+='3. **更多Anchor并非总更好。** 256全部相比16384，在HuMMan VAL为11.460对12.736mm；BEHAVE却为21.268对21.246mm。可见子集在HuMMan大幅变差、在BEHAVE改善，说明候选近似、覆盖和方向有明显域依赖，不能统一归因于数量。\n'
    md+='4. **点面LS值得留下，但还不是胜出的新模型。** Coarse＋点面LS6步，HuMMan VAL为10.646/42.409mm（median/P95），旧Official＋Txyz为11.226/41.604mm：median略好，P95略差。BEHAVE为18.564/82.194mm，仍弱于旧基线16.524/78.497mm；且BEHAVE seed37比原Fine更差。旧方向衰减在HuMMan仅约0.003mm变化，没有带来新突破。\n'
    md+='5. **Coarse的大偏移救回价值保住了。** 原HuMMan 11个fallback帧，在三个seed的Coarse＋历史6步中都不再fallback，子组表面median帧均值降到约12mm。p001195整体从原Fine18.800到12.204mm；但p001196从19.309到19.133mm时P95反而52.150→55.234mm。\n'
    md+='6. **顶点更近与Camera参数更准仍有取舍。** Native密集6步顶点94.524→88.375mm，但Camera20.610→44.761mm；点面LS的Camera更到58.610mm。不能把表面拟合量当相机真值。\n\n'
    md+='## 1. 主问题：同Coarse＋完整历史算子能恢复多少\n\n|数据|原Fine|Coarse＋历史6步|Official＋历史6步|相对Fine逐seed变化|\n|---|---:|---:|---:|---|\n'
    primary=[]
    for d,role in cohorts:
        metric='vertex_camera_mm' if d=='native' else 'median_mm';a=values('fine',d,role,metric);b=values('hist_med6',d,role,metric);c=values('official_hist6',d,role,metric)
        md+='|'+d+'/'+role+'|'+f'{a.mean():.3f}|{b.mean():.3f}|{c.mean():.3f}|'+'/'.join(f'{x:+.3f}' for x in b-a)+'|\n'
        primary.append(dict(dataset=d,role=role,metric=metric,fine=a.tolist(),coarse_historical6=b.tolist(),official_historical6=c.tolist(),delta_vs_fine=(b-a).tolist(),delta_vs_official=(b-c).tolist()))
    md+='\nNative为对应顶点均值；真实为独立表面median的层级均值。负变化表示改善。原Fine是Full Last，不能把它写成R5.1 E1的14.20mm。\n\n'
    tradeoff=[]
    for seed in [11,23,37]:
        for method in ['hist_med6','hist_plane6','lattice_nn_vis_med1']:
            rr=[r for r in frames if r['dataset']=='native' and r['seed']==seed and r['method']==method]
            cam=np.array([r['camera_mm']-index['native',seed,r['key'],'fine']['camera_mm'] for r in rr])
            vertex=np.array([r['vertex_camera_mm']-index['native',seed,r['key'],'fine']['vertex_camera_mm'] for r in rr])
            tradeoff.append(dict(seed=seed,method=method,frames=len(rr),camera_better_vertex_worse=int(np.sum((cam<0)&(vertex>0))),camera_worse_vertex_better=int(np.sum((cam>0)&(vertex<0))),camera_mean_mm=float(np.mean([r['camera_mm'] for r in rr]))))
    md+='Native Camera参数误差与对应顶点的相反变化，逐seed/方法见NATIVE_OBJECTIVE_TRADEOFF.json。不能把任何表面较好的平移直接当作Camera GT。\n\n'
    md+='## 2. 逐因子事实\n\n每个数是三个seed的配对差值均值；after减before，负数更好。不是全因子实验，后续对应会随前面更新改变。\n\n|对照|Native顶点|HuMMan TRAIN|HuMMan VAL|BEHAVE独立表面|\n|---|---:|---:|---:|---:|\n'
    for name in dict.fromkeys(r['contrast'] for r in pairs):
        cols=[]
        for d,role0 in [('native','VAL'),('real','TRAIN'),('real','VAL'),('behave',None)]:
            rr=[r for r in pairs if r['contrast']==name and r['dataset']==d and (role0 is None or r['role']==role0)]
            cols.append(f"{np.mean([r['aggregate_delta_mm'] for r in rr]):+.3f}")
        md+='|'+name+'|'+'|'.join(cols)+'|\n'
    md+='\n密集/256改变的是NN的候选Mesh近似；初始可见子集另改变覆盖范围。Mesh→Obs与Obs→Mesh改变配对数量与方向。投影/格点NN控制共享Depth，并分离原Fine将Z赋给Query射线的像素量化差别；但直接中位数更新不是最优投影求解，不能证明投影信息本身的上限。点面LS和衰减的效果也不能从单个例子推广。\n\n'
    md+='## 3. 已知失败身份与P95\n\n|人物|Coarse median/P95|Fine median/P95|Coarse＋历史6 median/P95|Official＋历史6 median/P95|\n|---|---:|---:|---:|---:|\n'
    for identity in ['p001195','p001196']:
        cols=[]
        for method in ['coarse','fine','hist_med6','official_hist6']:
            vals=[]
            for metric in ['median_mm','p95_mm']:
                rr=[c['metrics'][metric]['per_identity'][identity]['mean'] for c in cells if c['dataset']=='real' and c['method']==method and identity in c['metrics'][metric]['per_identity']]
                vals.append(f'{np.mean(rr):.3f}')
            cols.append('/'.join(vals))
        md+='|'+identity+'|'+'|'.join(cols)+'|\n'
    md+='\n## 4. 原Txyz fallback与初始化范围\n\nfallback上限相对于各自起点。学习的Coarse可先移动超过177.888mm，随后几何修正仍在自身177.888mm内；这不等于几何求解在同一个Official半径内击败旧优化。以下保留原fallback子组，不从总分剔除。\n\n'
    fallbacks=[]
    for seed in [11,23,37]:
        rr=[r for r in frames if r['dataset']=='real' and r['seed']==seed and r['method']=='official_hist6'];bad=[r for r in rr if r['fallback']]
        row=dict(seed=seed,original_fallback_frames=[r['key'] for r in bad],methods={})
        for method in ['coarse','fine','hist_med6','official_hist6']:
            selected=[index[r['dataset'],seed,r['key'],method] for r in bad]
            row['methods'][method]=dict(count=len(selected),mean_frame_median_mm=float(np.mean([r['median_mm'] for r in selected])),mean_frame_p95_mm=float(np.mean([r['p95_mm'] for r in selected])),fallback=sum(r['fallback'] for r in selected))
        fallbacks.append(row)
        md+='seed'+str(seed)+'：原fallback '+str(len(bad))+'帧；'+ '；'.join(m+' median帧均值 '+f"{v['mean_frame_median_mm']:.3f} mm（本方法fallback {v['fallback']}）" for m,v in row['methods'].items())+'。\n\n'
    md+='这里是固定fallback子组的帧均值，不与总体的序列/人物等权均值混称同一口径。全部原fallback帧名、每方法和每seed保存在FALLBACK_SUBGROUP.json。\n\n'
    # Report primary P95 identities that deteriorate, not just mean medians.
    identity_changes=[]
    for c in [c for c in cells if c['dataset']!='native' and c['method']=='fine']:
        b=next(b for b in cells if b['method']=='hist_med6' and all(b[k]==c[k] for k in ['dataset','role','seed']))
        for identity,value in c['metrics']['p95_mm']['per_identity'].items():
            identity_changes.append(dict(dataset=c['dataset'],role=c['role'],seed=c['seed'],identity=identity,p95_delta_mm=b['metrics']['p95_mm']['per_identity'][identity]['mean']-value['mean'],median_delta_mm=b['metrics']['median_mm']['per_identity'][identity]['mean']-c['metrics']['median_mm']['per_identity'][identity]['mean']))
    md+='## 5. 判断边界与下一步\n\n本轮主对照是预先固定的hist_med6，不依据B从18组挑一个新正式模型。若某分支分数更小，只能证明这套观测/求解在已消费开发集的可见表面评价更好；不能把其平移当Camera GT。Native Camera L2与对应顶点必须单独读。\n\n'
    md+='本轮不能将约3mm差距按比例归到MLP、点数、射线或优化步数。原Fine同时使用RGB并受Camera/表面混合训练目标约束；几何算子不使用相同训练目标。没有进行同输入、同监督的head训练替换，因此“MLP不会精确求解”仍未得到证明。已经成立的是这几个固定几何干预的实际效果，以及简单“三维NN必更好”解释的反例。\n\n'
    md+='下一阶段优先考虑受约束的几何求解与对应可靠性，保留投影信息，不整体替换成三维最近邻。不再将“MLP不会算几何”“点数少就是唯一原因”当已证实机制。点面LS可作为候选参考，必须同时针对真实P95和跨域退化验证；学习权重只有超过这些不学习的稳健算子才有增量意义。此次结束，不自动重构、组合或训练。DGR/PointDSC已有学习权重与几何求解路线，采用这类模块本身不是足够的新颖性证明。\n\n'
    md+='POST_INTEGRITY、逐人P95、所有失败与完整seed结果是本次交付的一部分。负收益转移Native按对应顶点误差定义，真实按表面median定义，不冒充旧Native Camera负收益计数。完整RGB→Mesh端到端耗时本轮仍未测，缓存求解的吞吐不能替代它。\n'
    (out/'ANALYSIS.md').write_text(md,encoding='utf-8')
    for name,v in [('PRIMARY_CONTRAST.json',primary),('FALLBACK_SUBGROUP.json',fallbacks),('PRIMARY_IDENTITY_CHANGES.json',identity_changes),('NATIVE_OBJECTIVE_TRADEOFF.json',tradeoff)]:
        (out/name).write_text(json.dumps(v,indent=2),encoding='utf-8')
    print('ANALYSIS_COMPLETE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
