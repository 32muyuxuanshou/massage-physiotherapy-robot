"""Readable, offline HTML/Markdown plus dataset-separated scientific figures."""
import argparse
import csv
import html
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,
    'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130,'savefig.dpi':160})


def mean_sd(values):return f'{np.mean(values):.2f} ± {np.std(values,ddof=1):.2f}'


def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+html.escape(str(v))+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'


def main(a):
    out=a.root/'reports';out.mkdir(exist_ok=True)
    summary=json.loads((out/'SUMMARY.json').read_text())
    records=json.loads((out/'Q1_RECORDS.json').read_text())
    rigid=json.loads((out/'RIGID_RECORDS.json').read_text())
    cells=summary['cells']
    behave_role=next(c['role'] for c in cells if c['dataset']=='behave')
    panels=[('native','VAL','camera_mm','Native VAL：Camera 向量误差'),
        ('real','TRAIN','median_mm','HuMMan TRAIN：独立 B 表面误差'),
        ('real','VAL','median_mm','HuMMan VAL：独立 B 表面误差'),
        ('behave',behave_role,'pve_mm','BEHAVE：拟合参考对应顶点 PVE')]
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for ax,(d,role,k,title) in zip(axes.flat,panels):
        rr=[c for c in cells if c['dataset']==d and c['role']==role]
        agg='frame_equal_mean' if d=='behave' else 'identity_equal_mean'
        for j,stage in enumerate(['coarse','final']):
            values=[c['stages'][stage][k][agg] for c in rr]
            ax.bar(j,np.mean(values),yerr=np.std(values,ddof=1),color=['#91a7c1','#167d9a'][j],capsize=5)
            ax.text(j,np.mean(values)+np.std(values,ddof=1)+1,mean_sd(values),ha='center',fontsize=9)
        if d!='native':
            values=[c['baseline'][k][agg] for c in rr]
            ax.bar(2,np.mean(values),color='#df9c35');ax.text(2,np.mean(values)+1,f'{np.mean(values):.2f}',ha='center')
        ax.set_xticks(range(2 if d=='native' else 3),['Full 内部 Coarse','Full 最终 Fine']+([] if d=='native' else ['Official+Txyz']))
        ax.set_title(title,fontsize=11);ax.set_ylabel('mm，越低越好');ax.set_ylim(0,ax.get_ylim()[1]*1.16)
    fig.suptitle('同一个 Full Last 的粗定位与细修：三个 seed 分开计算后汇总',fontsize=14)
    fig.savefig(out/'coarse_fine_summary.png');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for ax,(d,role,k,title) in zip(axes.flat,panels):
        for seed in [11,23,37]:
            rr=[r for r in records if r['dataset']==d and r['role']==role and r['seed']==seed]
            for stage,color in [('coarse','#91a7c1'),('final','#167d9a')]:
                values=np.sort([r['stages'][stage][k] for r in rr]);ax.plot(values,np.arange(1,len(values)+1)/len(values),color=color,alpha=.65,label=stage if seed==11 else None)
            if d!='native':
                values=np.sort([r['official_txyz'][k] for r in rr]);ax.plot(values,np.arange(1,len(values)+1)/len(values),color='#df9c35',alpha=.5,label='Official+Txyz' if seed==11 else None)
        ax.set_title(title,fontsize=11);ax.set_xlabel('每帧误差 mm，保留全部长尾');ax.set_ylabel('累计帧比例');ax.legend(fontsize=8)
    fig.savefig(out/'all_frame_cdf.png');plt.close(fig)
    native=[r for r in records if r['dataset']=='native']
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    x=np.array([r['stages']['final']['camera_mm']-r['stages']['coarse']['camera_mm'] for r in native])
    y=np.array([r['stages']['final']['vertex_camera_mm']-r['stages']['coarse']['vertex_camera_mm'] for r in native])
    axes[0].scatter(x,y,s=8,alpha=.4,color='#167d9a');axes[0].axhline(0,color='gray',lw=.8);axes[0].axvline(0,color='gray',lw=.8)
    axes[0].set(xlabel='Camera 误差变化 mm（负数=改善）',ylabel='顶点误差变化 mm（负数=改善）',title='Camera 变准，不保证整个人体顶点变准')
    axes[1].hist([r['native_direction']['parallel_fraction'] for r in native],bins=50,color='#167d9a')
    axes[1].axvline(1,color='#df9c35',label='沿真值 Camera 方向的足量修正');axes[1].legend(fontsize=8)
    axes[1].set(xlabel='Fine 在所需 Camera 修正方向上的投影比例',ylabel='样本×seed 数（不是独立受试者数）',title='方向/幅度诊断仅限有原生真值的 Native')
    fig.savefig(out/'native_camera_vs_surface.png');plt.close(fig)
    # Entire failure index, including cases that improve one metric and harm another.
    failure=[];associations=[]
    for r in records:
        key='camera_mm' if r['dataset']=='native' else 'median_mm' if r['dataset']=='real' else 'pve_mm'
        p95='p95_mm' if r['dataset']=='real' else 'surface_p95_mm' if r['dataset']=='behave' else None
        failure.append(dict(dataset=r['dataset'],role=r['role'],seed=r['seed'],key=r['key'],identity=r['identity'],
            metric=key,coarse=r['stages']['coarse'][key],final=r['stages']['final'][key],
            delta=r['stages']['final'][key]-r['stages']['coarse'][key],
            p95_delta=(r['stages']['final'][p95]-r['stages']['coarse'][p95]) if p95 else '',
            visible_queries=r['visible_queries'],fine_norm_mm=r['fine_norm_mm']))
    with (out/'ALL_FRAME_CHANGE_INDEX.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(failure[0]));w.writeheader();w.writerows(failure)
    for d,role,k,title in panels:
        for seed in [11,23,37]:
            rr=[r for r in records if r['dataset']==d and r['role']==role and r['seed']==seed]
            gain=[r['stages']['coarse'][k]-r['stages']['final'][k] for r in rr]
            for name,values in [('visible_queries',[r['visible_queries'] for r in rr]),('minimum_normal_eigenvalue',[min(r['eigenvalues']) for r in rr])]:
                rho,p=spearmanr(values,gain)
                associations.append(dict(dataset=d,role=role,seed=seed,feature=name,
                    spearman_rho=float(rho),p_unadjusted_descriptive_only=float(p)))
    (out/'FEATURE_ASSOCIATIONS.json').write_text(json.dumps(associations,indent=2))
    qrows=[]
    for d,role,k,title in panels:
        rr=[c for c in cells if c['dataset']==d and c['role']==role]
        agg='frame_equal_mean' if d=='behave' else 'identity_equal_mean'
        qrows.append([title.replace('：',' / '),mean_sd([c['stages']['coarse'][k][agg] for c in rr]),
            mean_sd([c['stages']['final'][k][agg] for c in rr]),
            '—' if d=='native' else f"{rr[0]['baseline'][k][agg]:.2f}（固定参考）" if d=='real' else mean_sd([c['baseline'][k][agg] for c in rr])])
    srows=[]
    for c in cells:
        k='camera_mm' if c['dataset']=='native' else 'median_mm' if c['dataset']=='real' else 'pve_mm'
        agg='frame_equal_mean' if c['dataset']=='behave' else 'identity_equal_mean'
        pair=c['paired'][k]
        srows.append([c['dataset'],c['role'].replace(behave_role,'已消费 TEST 子集'),c['seed'],
            f"{c['stages']['coarse'][k][agg]:.3f}",f"{c['stages']['final'][k][agg]:.3f}",
            f"{pair['improved']} / {pair['worse']}",f"{c['fine_norm_median_mm']:.2f}"])
    rigid_rows=[]
    for role in ['TRAIN','VAL']:
        for method in ['official_txyz','matched_translation','matched_rigid']:
            x=summary['rigid'][role][method]
            rigid_rows.append([role,method,f"{x['median_mm']['identity_equal_mean']:.3f}",
                f"{x['p95_mm']['identity_equal_mean']:.3f}",f"{x['coverage_50mm']['identity_equal_mean']*100:.2f}%",
                11 if method=='official_txyz' and role=='TRAIN' else 0 if method=='official_txyz' else x['fallback_frames']])
    root=summary['native_root']['aggregation']
    rootrows=[[name,f"{root[key]['identity_equal_mean']:.3f}"] for key,name in [
        ('official','Official 原始参数'),('true_t_only','仅换真值平移'),('true_R_only','仅换真值整体旋转'),('true_R_true_t','同时换真值旋转、平移'),
        ('centered_official','Official 去质心后'),('centered_true_R','换真值旋转后，再去质心')]]
    personrows=[]
    for c in cells:
        if c['dataset']!='real':continue
        for identity in ['p001195','p001196']:
            if identity in c['stages']['final']['median_mm']['per_identity']:
                get=lambda st,k:c['stages'][st][k]['per_identity'][identity]['mean']
                personrows.append([identity,c['role'],c['seed'],f"{get('coarse','median_mm'):.2f} → {get('final','median_mm'):.2f}",
                    f"{get('coarse','p95_mm'):.2f} → {get('final','p95_mm'):.2f}"])
    body=f'''<h1>R5 离线诊断：Fine 在帮忙，但还不是全部答案</h1>
<p class="lead">已完成 2,706 条同模型 Coarse/Fine 对照、232 帧 A-only 旋转对照，以及 400 帧原生 MHR 参数替换。没有训练新模型。完整 GPU 耗时按你的要求暂缓。</p>
<div class="card"><b>先说结论</b><p>保留 Camera/Body 硬解耦，也保留 Fine。它在三份数据上总体有效；问题不是简单的“Fine 没起作用”。但部分更新方向错误、部分样本改坏，真实数据仍未全面超过 Official+Txyz。现在没有证据支持直接上多步展开或复杂旋转网络。</p></div>
<h2>1. 三份数据分别看，毫米数不混在一起</h2>
{table(['数据 / 误差含义','同一 Full 的内部 Coarse','Full 最终 Fine','Official+历史 Txyz'],qrows)}
<p>Full 表中是三个训练 seed 的均值 ± 样本标准差。HuMMan Official+Txyz 是原单一共享缓存的固定参考，并非三次独立推理；BEHAVE Official 有原有三 seed 输出，其微小差异四舍五入为 0.00。Native 是相机平移向量到原生真值的距离；HuMMan 是固定 Camera B 的观测点到预测三角面的单向距离；BEHAVE 是固定映射后对应顶点到拟合参考的平均距离。它们不是同一种误差。</p>
<img src="coarse_fine_summary.png"><h2>2. Fine 具体做了什么</h2>
<p>Native 的 Camera 误差平均从约 47.86 降到 20.61 mm；HuMMan VAL 从约 19.19 降到 14.36 mm；BEHAVE PVE 从约 77.33 降到 61.06 mm。这里比较的始终是同一个 Full Last，不是另一个单独训练的 Coarse 模型。</p>
{table(['数据','角色','seed','Coarse mm','Final mm','改善帧 / 变差帧','Fine 位移中位 mm'],srows)}
<p>Native 三个 seed 各有 29～40/400 帧的 Fine 与真值 Camera 所需修正方向相反；67～72/400 帧的 Camera 误差变大。沿真值方向的投影比例中位数约 0.69～0.72，同时还存在约 8～9 mm 的正交分量。<b>有欠修正现象，但不能把它解释成“方向都对、只差多走几步”。</b></p>
<p>还有 95～102/400 帧出现“Camera 改善但顶点误差变大”。这说明模型位置误差与表面贴合误差确实可能冲突；Txyz 的表面分数更低，不等于它的物理 Camera 一定更真。Native 的最终顶点误差仍约 94.52 mm，去平移后约 76.24 mm，Camera-only 分支没有修复原有身体误差。</p>
<img src="native_camera_vs_surface.png">
<h2>3. 已知失败人物：改善了多少，剩下多少</h2>
{table(['人物','角色','seed','表面 median mm：Coarse → Final','表面 P95 mm：Coarse → Final'],personrows)}
<p>没有删除 p001195 或任何坏帧。全部逐帧变化与负收益都保存在 <a href="ALL_FRAME_CHANGE_INDEX.csv">完整索引</a>。法线特征值、可见 Query 与增益的相关性另存于 FEATURE_ASSOCIATIONS.json，只是描述性线索，不能据此判定遮挡就是原因。</p>
<img src="geometry_case_1.png"><img src="geometry_case_2.png"><p>灰色为缓存 Mesh，彩色为实际 Camera B 点。上排使用真实 B 内参投影，下排明确是 XZ 正交侧视；没有把它们冒充原 RGB 叠图。颜色饱和上限 100 mm，实际误差不截断，图索引保留最大值。</p>
<h2>4. 加旋转有用吗？有小幅平均收益，但不普遍</h2>
{table(['角色','方法','表面 median mm','表面 P95 mm','≤50mm 覆盖率','fallback 帧'],rigid_rows)}
<p>平移与刚体对照使用相同 A 点、16,384 anchors、六轮、80% 对应保留、固定尺度和相同总平移上限。为隔离旋转，新增的匹配平移使用均值更新，与 Kabsch 的平方距离目标配套；历史中位数 Txyz 原样保留，不能混称同一算法。</p>
<p>VAL 上，匹配平移 11.12 → 刚体 10.32 mm；40 帧中 26 帧改善、14 帧变差，四个人中三个改善、一个变差。TRAIN 上 24.23 → 22.71 mm，仍有 11 帧超限回退。<b>这支持保留小型刚体工程对照，不足以单独支持重构 SE(3) 网络，也不能证明旋转无用。</b>Camera B 没有参与拟合或参数选择。</p>
<h2>5. 真值旋转替换为何不能叫“最优上限”</h2>
{table(['Native VAL：固定 Official 身体其余参数','对应顶点误差 mm'],rootrows)}
<p>这是同一原生 MHR 的参数替换，使用 CPU 重新解码；没有手工把旋转重复乘在已旋转的顶点上。400 帧都核验了原输出复现、真值 Euler 与物理相机矩阵关系，以及替换前后的正确刚体关系。</p>
<p>即便如此，真值整体旋转替换仍使顶点误差恶化。<b>这个实验直接说明：在内部关节、体型已经预测错误时，单独换一个真值参数不保证整体误差降低。</b>是否存在局部姿态对整体旋转误差的补偿，仍属于待进一步拆分的解释。不能据此说真实旋转不重要。另一个固定尺度的参考 Kabsch 对齐可把 Native 去质心误差约 76.24 降到 64.04 mm；它用到了参考，只用于诊断，不能当可部署方法。</p>
<h2>6. 全部帧分布，不只看均值</h2><img src="all_frame_cdf.png">
<p>CDF 每条线对应一个 seed 的全部帧，保留长尾。它是帧分布；主表仍按预定受试者聚合，不把三次 seed 当作三倍独立人群。HuMMan 的 P95 是逐帧 P95 经序列、身份平均，不是混合全部点重新求 P95。</p>
<h2>7. 下一步的判断</h2>
<ol><li><b>先不加新模块、不自动重训。</b>这轮已排除“Fine 完全没用”和“只要换真值旋转就好”这两种过度简化。</li>
<li><b>保留现有 R5，集中解决 Fine 的负收益与目标错位。</b>下一项应在固定身体条件下分清 Camera 真值目标与可见表面贴合目标，验证错误对应、域差异与回归方向各占什么作用；不能拿 Txyz 向量直接当真实 Camera 标签。</li>
<li><b>完整速度还没有测。</b>服务器保持无卡模式。以后恢复 GPU 后，再实测整条 RGB-D→Mesh 的延迟和显存，才能讨论相对 Txyz 的效率优势。</li></ol>
<div class="card warn"><b>证据边界</b><p>Native 50 个 VAL 身份 /400 图；HuMMan TRAIN 18 人/192 帧、VAL 4 人/40 帧；BEHAVE 是既有已消费身份的官方 TEST 子集，3 人/90 序列/270 帧。未读取封存 Native/HuMMan TEST。BEHAVE 拟合 SMPL-H 不是裸露皮肤真值，独立点集仍有物体/深度异常限制。本轮不证明穴位精度、不声称超过 M³，也不代表全新泛化验证。</p></div>
<h2>8. 复查入口</h2><p><a href="SUMMARY.json">完整汇总</a> · <a href="PER_FRAME.csv">2,706 条逐帧表</a> · <a href="Q1_RECORDS.json">逐帧完整诊断字段</a> · <a href="RIGID_RECORDS.json">232 帧刚体/平移轨迹</a> · <a href="ALL_FRAME_CHANGE_INDEX.csv">全部正负收益索引</a></p>
<p>原评价器复现：真实 HuMMan/BEHAVE 固定核验样本误差为零；Native 全量 float32/float64 最大差异 {summary['original_final_reproduction_max']['native']:.8f} mm。保存原科学输入实际 SHA，新诊断位于独立目录。未启动训练、未关闭服务器。</p>'''
    style='body{font:16px/1.75 "Microsoft YaHei",sans-serif;color:#203244;background:#f6f8fb;margin:0}main{max-width:1180px;margin:auto;padding:32px}h1{font-size:30px}h2{margin-top:36px}.lead{font-size:19px}table{border-collapse:collapse;background:white;width:100%;font-size:14px;margin:20px 0}th,td{padding:9px 12px;border:1px solid #dce3ec;text-align:left}th{background:#eaf0f7}img{width:100%;background:white;margin:16px 0}.card{background:#e5f1f5;border-left:5px solid #167d9a;padding:18px 24px}.warn{background:#fff4df;border-color:#df9c35}a{color:#176a94}'
    (out/'R5_离线诊断与下一步.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>R5 离线诊断</title><style>'+style+'</style><main>'+body+'</main></html>',encoding='utf-8')
    md='''# R5 集中离线诊断结果

完成同一 Full Last 的 2,706 条 Coarse/Fine 对照、HuMMan 232 帧 Camera A-only 匹配平移/刚体对照、Native 400 帧原生 MHR 真值旋转参数替换。三个 seed 为 11/23/37；没有训练。

|数据 / 指标|Full 内部 Coarse|Full 最终 Fine|Official+历史 Txyz|
|---|---:|---:|---:|
'''+''.join('|'+ '|'.join(map(str,row))+'|\n' for row in qrows)+'''
Fine 总体有效，但并非处处有效。Native 每个 seed 有 67–72/400 帧 Camera 误差变大，29–40/400 帧修正方向与原生 Camera 真值所需方向相反；95–102/400 帧 Camera 改善但顶点误差恶化。不能只归因为步长不足，也不能拿 Txyz 当真实 Camera 标签。

HuMMan VAL：匹配平移 11.122 mm，匹配刚体 10.322 mm；P95 41.855→39.497 mm。26/40 帧改善、14/40 变差；四个身份三个改善、一个变差。历史 Txyz 11.226 mm 保持不变。这是算法与数据条件下的小幅收益，不是全局最优或增加旋转网络的充分证据。

Native 真值参数替换：Official 157.121 mm；仅换平移 100.227 mm；仅换整体旋转 196.021 mm；同时换两者 140.831 mm。正确重新解码并通过 400 帧物理旋转核验，仍可能恶化。固定错误的内部人体参数时，真值参数替换不是表面误差 oracle。局部姿态补偿等解释尚未因果验证。

建议保留硬解耦与 Fine，下一项集中检查 Fine 的负收益以及 Camera 标签与观测表面目标的错位，不直接展开训练、增加多步或旋转模块。完整 GPU 端到端速度按用户要求暂缓，因此尚不能宣称速度优势。

完整逐 seed、逐人、逐帧结果及全部坏帧见 HTML、SUMMARY.json、PER_FRAME.csv、Q1_RECORDS.json、RIGID_RECORDS.json 和 ALL_FRAME_CHANGE_INDEX.csv。

Native/HuMMan 封存 TEST 未读；BEHAVE 为已消费官方 TEST 子集。没有 Camera B 拟合。三个数据集指标不能混成一个总毫米值；不能据此声称 M³ 同协议领先、裸背精度或穴位精度。
'''
    (out/'FINAL_REPORT.md').write_text(md,encoding='utf-8')
    print('REPORT_COMPLETE',out,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args())
