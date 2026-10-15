"""Migration receipt and readable negative-update diagnosis, no new training."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'savefig.dpi':150})


def table(headers,rows):
    return '<table><tr>'+''.join('<th>'+html.escape(str(v))+'</th>' for v in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</table>'


def main(a):
    out=a.root/'reports';query=json.loads((out/'QUERY_AUDIT.json').read_text())
    classified=json.loads((out/'UPDATE_CLASSIFICATION.json').read_text())
    surface=json.loads((out/'NATIVE_CAMERA_SURFACE_TRADEOFF.json').read_text())
    native=[g for g in classified['groups'] if g['dataset']=='native']
    names=['opposite_direction','orthogonal_component_erases_parallel_gain','parallel_overshoot_alone_worsens']
    labels=['朝向与真值所需方向相反','正交分量抵消平行收益','仅平行分量已过冲']
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    x=np.arange(3);bottom=np.zeros(3)
    for name,label,color in zip(names,labels,['#c77676','#d7a355','#788dc0']):
        values=np.array([g['kinds'].get(name,0) for g in native]);axes[0].bar(x,values,bottom=bottom,label=label,color=color)
        for i,v in enumerate(values):axes[0].text(i,bottom[i]+v/2,str(v),ha='center',va='center')
        bottom+=values
    axes[0].set_xticks(x,['seed 11','seed 23','seed 37']);axes[0].set_ylabel('Native Camera 误差变大的帧数 /400');axes[0].set_ylim(0,110);axes[0].legend(fontsize=8)
    metrics=['coarse','final','half_step_camera_mm','oracle_stop_camera_mm'];tick=['Coarse','当前 Fine','固定半步','完美停手*']
    values=np.array([[g['native_counterfactual'][k] for k in metrics] for g in native])
    axes[1].bar(range(4),values.mean(0),yerr=values.std(0,ddof=1),capsize=4,color=['#a8b4c6','#187d99','#cd9271','#74a791'])
    for i,v in enumerate(values.mean(0)):axes[1].text(i,v+2,f'{v:.2f}',ha='center')
    axes[1].set_xticks(range(4),tick);axes[1].set_ylim(0,60);axes[1].set_ylabel('Native Camera 误差 mm，三 seed 均值')
    axes[1].set_title('*使用真值在 Coarse/Final 二选一，仅诊断上限',fontsize=10)
    fig.savefig(out/'native_update_diagnosis.png');plt.close(fig)
    kindrows=[[g['seed'],g['kinds'].get(names[0],0),g['kinds'].get(names[1],0),g['kinds'].get(names[2],0),
        sum(g['kinds'].get(k,0) for k in names)] for g in native]
    feature_rows=[]
    for g in query['groups']:
        if g['dataset']=='real' and g['role']=='TRAIN':continue
        get=lambda name:g['features'][name]
        feature_rows.append([g['dataset']+(' VAL' if g['dataset']=='real' else ''),g['seed'],
            f"{g['eligible']}/{g['total']}",
            f"{get('abs_z_median_mm')['worse_median']:.2f} / {get('abs_z_median_mm')['not_worse_median']:.2f}",
            f"{get('signed_z_std_mm')['worse_median']:.2f} / {get('signed_z_std_mm')['not_worse_median']:.2f}",
            f"{get('local_depth_range_median_mm')['worse_median']:.2f} / {get('local_depth_range_median_mm')['not_worse_median']:.2f}"])
    m=query['excluded_records'][0]
    surface_rows=[[g['seed'],g['camera_worse'],g['camera_worse_full_mask_median_improves'],
        g['camera_worse_both_medians_improve'],g['camera_worse_both_medians_and_hit_iou_nonworse']] for g in surface['groups']]
    surface_metric_rows=[]
    for g in surface['groups']:
        for stage in ['coarse','final']:
            d=g['stage_frame_mean'][stage]
            surface_metric_rows.append([g['seed'],stage,f"{d['full_mask_median_mm']:.2f}",f"{d['common_median_mm']:.2f}",
                f"{d['common_p95_mm']:.2f}",f"{d['hit_rate']*100:.2f}%",f"{d['silhouette_iou']:.4f}",f"{d['full_mask_p95_mm']:.2f}"])
    body=f'''<h1>218 迁移完成：Fine 负收益诊断</h1>
<p class="lead">1,442 个实际缓存文件、15.34 GB 已在218逐个SHA核验。原三个Full Last权重与训练源码匹配。三张2080Ti完成2,706条逐Query重放，没有训练新模型。</p>
<div class="card"><b>这次最重要的结果</b><p>不能把Camera误差变大直接叫作表面坏更新。每seed的67～72个Camera负收益帧中，46～49帧的全目标mask轴向深度中位误差反而下降；其中34～41帧还同时通过共同命中误差下降、命中率与轮廓IoU不下降的检查。</p><p>Native中只有3～9帧属于平行分量本身已过冲；更多是方向相反，或正交分量抵消了Camera指标上的平行收益。使用真值在Coarse/Final中完美挑选，Camera平均仅从20.61降到19.30 mm；统一将Fine减半反而变成31.28 mm。这个Camera止损上限不能代表表面任务上的收益。</p></div>
<h2>1. 在哪里运行</h2><p>工作根：<code>/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1</code><br>Python：<code>/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python</code><br>使用GPU 0/1/2，分别处理seed 11/23/37。原AutoDL仍保留、仍为无卡模式，两个服务器都未关闭。</p>
<p>环境为Python3.10、PyTorch2.5.1+cu118、原nvdiffrast0.4.0源码。与AutoDL的软件版本不同，已通过解析相机Z渲染QA和固定11条样本数值核验。全部数据走直连SFTP或复用218已核验备份，没有经过FlClash。</p>
<h2>2. 坏更新到底是哪一种</h2>
{table(['seed','方向相反','正交分量抵消收益','平行分量本身过冲','合计坏帧 /400'],kindrows)}
<p>只在有原生Camera真值的Native上作这个几何分解。恒等式为 ΔE²=||δ||²−2δ·(t_GT−t_coarse)，1,200条全部满足。它说明误差如何组成，不证明网络为什么产生该向量。真实HuMMan/BEHAVE没有相同Camera真值，不套用这些标签。</p>
<img src="native_update_diagnosis.png">
<p>“完美停手”使用真值逐帧选Coarse和Final较好者，只是保留这两个固定输出时的诊断上限，不是可部署方法，不是全局最优定位上限。三seed反复出现坏更新的Native帧只有19/400；HuMMan VAL没有一帧三seed都变差。因此不能把17%理解成一个固定不变的失败人群。</p>
<h2>3. Camera变差，表面一定变差吗？</h2>
{table(['seed','Camera变差帧','其中full-mask深度median改善','其中full-mask/共同命中median都改善','再要求命中率与IoU都不下降'],surface_rows)}
<p><b>答案是否定的。</b>这是用同一批400张Native合成VAL、真实K与clean GT深度补算的可见表面诊断。它支持“两个目标可能给出不同方向的判断”，不证明某个人体参数一定更准，也不是俯卧后背或穴位精度。</p>
{table(['seed','阶段','full-mask median mm','共同命中median mm','共同命中P95 mm','命中率','IoU','full-mask P95 mm*'],surface_metric_rows)}
<p>先逐帧计算，再在固定400帧取均值；不同seed分别报告。两个方法使用同一GT mask和同一共同命中点集。<b>*未命中像素仍以零渲染深度计入full-mask，因此full-mask P95含数米量级的漏覆盖惩罚，不能当作命中表面的毫米误差。</b>共同命中误差必须连同命中率/IoU阅读。此为新增诊断，不替换旧主分数，完整逐帧值保留在JSON。</p>
<h2>4. Query残差是否支持“异常点带偏”</h2>
{table(['数据','seed','可分析帧 /全部','|Z残差|中位 mm：坏 /未坏','Z残差标准差 mm：坏 /未坏','局部深度范围 mm：坏 /未坏'],feature_rows)}
<p>这是Query输入残差的组统计，<b>不是最终Camera误差、独立B表面距离或穴位误差</b>。先逐帧计算Query特征，再分别取坏帧/未坏帧的中位数。</p>
<p>HuMMan VAL的坏更新组通常已经只有约10～15mm的Query轴向残差；改善组约26～53mm。BEHAVE也有类似分离。Native两组却都约61～62mm：即使Camera参数已接近真值，冻结身体的表面残差仍可能较大。</p>
<p>Query残差方差、局部5×5深度跳变和max-pool通道集中度没有出现统一、跨域稳定的“坏帧更极端”规律。现有证据不足以把少数飞点、物体遮挡或衣褶认定为共同主因；我们也没有相应逐点语义真值。</p>
<h2>5. 看实际输入与位移</h2><img src="query_examples.png">
<p>左：真实Camera A裁剪深度，彩色点是模型实际采用的可见Query，灰叉为未采用Query，黑圈为贡献max-pool通道最多的五点；中：全部可见Query的轴向残差；右：历史Fine的Tx/Ty/Tz。例子按旧误差的最大负收益和预先已知的p001195选取，不按新Query特征挑图。颜色饱和范围±100mm，直方图与数值不截断。</p>
<h2>6. 重放差异如何处理</h2><p>原样Camera头重放在少数边界帧出现微小Coarse差异改变离散可见Query的问题。为恢复原Fine上下文，本轮固定历史Coarse中间值，再通过原Fine权重与原渲染器观察实际输入；没有将这个诊断条件当新模型，也没有替换原始主结果。</p>
<p>2,706条坐标数值重放均通过0.0001m标准；2,705条同时通过Query计数与法线特征值核验。唯一单列帧为seed {m['seed']} / {m['key']}，可见Query {m['observed_queries']} vs历史{m['historical_observed_queries']}，位置最大差异{m['coordinate_reproduction_error_m']*1000:.4f}mm。该帧仍保留在原误差和分类统计，只不进入主要Query关联统计。原逐点mask没有保存，不能用计数匹配冒充独立的历史逐点身份核验。</p>
<h2>7. 下一步的取舍</h2><p><b>先不启动R5.1训练。</b>这轮没有支持一个统一的“方差大就关闭”门控，也不应按Camera标签把所有负收益更新截掉。更值得验证的是：固定身体时，Camera参数监督与可见表面监督如何分别影响Fine，以及小残差起点是否需要更有针对性的校准。门控只作为独立对照，不能依靠Camera B选阈值后再称独立验证。</p>
<p>完整RGB-D→Mesh端到端耗时仍未测：这次使用已缓存的Official Body/Backbone，不能拿本轮重放速度或44MB级Torch张量内存当作完整SAM3D系统的速度/显存。</p>
<p><a href="QUERY_AUDIT.json">完整Query统计与字段</a> · <a href="UPDATE_CLASSIFICATION.csv">全部2,706条分类</a> · <a href="NATIVE_CAMERA_SURFACE_TRADEOFF.json">1,200条Camera/表面对照</a> · <a href="ALL_REPLAY_MISMATCHES.json">全部重放差异</a></p>'''
    style='body{font:16px/1.8 "Microsoft YaHei",sans-serif;background:#f5f8fb;color:#24354b}main{max-width:1200px;margin:auto;padding:30px}h1{font-size:30px}h2{margin-top:34px}.lead{font-size:19px}.card{background:#e6f1f4;padding:18px 24px;border-left:5px solid #187d99}table{border-collapse:collapse;width:100%;background:white;font-size:14px}td,th{border:1px solid #d9e1e9;padding:8px}th{background:#e8edf4}img{width:100%;margin:20px 0}code{font-size:13px;overflow-wrap:anywhere}'
    (out/'218迁移与Fine负收益诊断.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>218迁移与Fine诊断</title><style>'+style+'</style><main>'+body+'</main></html>',encoding='utf-8')
    md='''# 218迁移与Fine负收益诊断

本轮1,442个缓存文件共15,344,760,005字节全部实际SHA通过。Native VAL400、HuMMan232共享缓存，以及BEHAVE270×3seed缓存均已就位。原三个Full Last权重和训练源码SHA匹配，218三张2080Ti已实际运行；未训练、未关闭服务器、未经过FlClash。

2,706条Query重放完成，坐标数值全部在0.0001m范围；2,705条满足主要Query关联标准，一条BEHAVE Query计数差一个，完整保留并单列。为隔离Coarse浮点变化，Fine上下文使用冻结历史Coarse值；这不是新模型、不是新主分数。

Native每seed坏更新分解：

|seed|方向相反|正交分量抵消收益|平行分量本身过冲|总坏帧|
|---|---:|---:|---:|---:|
'''+''.join('|'+ '|'.join(map(str,r))+'|\n' for r in kindrows)+'''
只缩小步长不够：Native固定半步Camera误差31.28mm，高于当前Fine的20.61mm。即使使用真值完美阻止所有Camera坏更新，在Coarse/Final二选一范围内也仅降到19.30mm，平均改善约1.31mm；不能把这个离线oracle当部署方法或表面精度上限。

关键补查：Camera变差不等于表面变差。

|seed|Camera变差帧|其中full-mask深度median改善|full-mask/共同命中median都改善|再要求命中率和IoU不下降|
|---|---:|---:|---:|---:|
'''+''.join('|'+ '|'.join(map(str,r))+'|\n' for r in surface_rows)+'''
这是新增Native clean GT轴向深度诊断，不替换历史主分数，不是俯卧后背或穴位精度。full-mask保留未命中零深度惩罚；完整结果同时保存共同命中误差、命中率、IoU与逐帧值。full-mask P95含数米漏覆盖惩罚，不是纯表面距离。不能按Camera误差上升直接抑制这些更新。

HuMMan VAL坏更新组Query轴向残差较小（约10–15mm），BEHAVE也有类似现象；Native坏/未坏两组均约61–62mm。残差方差、局部深度跳变和max-pool通道集中度没有统一跨域规律，不支持直接把异常点或衣褶当主要原因。

建议先验证Camera参数与可见表面监督的差异，保守门控作为独立对照，不直接按方差设计新架构或启动训练。全部统计为已消费数据上的描述性诊断；Native/HuMMan封存TEST未读取、Camera B未参与拟合，无新训练。BEHAVE仍是已消费的官方TEST子集，不能称全新测试集。

工作根：`/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1`。

Python：`/raid5/xuhd/rgbd_sam3d/runtime218/env/bin/python`。

本轮仅重放缓存后的Camera/Fine，未测完整SAM3D端到端速度或显存。
'''
    (out/'FINAL_REPORT.md').write_text(md,encoding='utf-8')
    print('REPORT_COMPLETE',out,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args())
